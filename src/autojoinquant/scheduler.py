"""Cross-platform daily scheduler installation."""

from __future__ import annotations

import os
import platform
import plistlib
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings, config_home, default_env_path, default_state_dir, validate_time

LABEL = "io.github.autojoinquant.checkin"
SYSTEMD_NAME = "autojoinquant"
CRON_BEGIN = "# BEGIN AUTOJOINQUANT MANAGED BLOCK"
CRON_END = "# END AUTOJOINQUANT MANAGED BLOCK"


class SchedulerError(ValueError):
    """The platform scheduler cannot be configured."""


@dataclass(frozen=True)
class ScheduleStatus:
    backend: str
    installed: bool
    detail: str


def system_name() -> str:
    name = platform.system()
    if name == "Linux":
        try:
            values = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            values = ""
        if "ID=nixos" in values or 'ID="nixos"' in values:
            return "NixOS"
    return name


def select_backend(requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    name = platform.system()
    if name == "Darwin":
        return "launchd"
    if name == "Linux":
        if shutil.which("systemctl"):
            return "systemd"
        if shutil.which("crontab"):
            return "cron"
        raise SchedulerError("neither systemd user services nor crontab is available")
    raise SchedulerError(f"automatic scheduling is unsupported on {name}")


def _run(command: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=check,
            input=input_text,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise SchedulerError(f"{' '.join(command)} failed: {detail}") from exc
    except OSError as exc:
        raise SchedulerError(f"cannot run {command[0]}: {exc}") from exc


def _atomic_bytes(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def render_systemd_service(executable: Path) -> str:
    command = " ".join(_systemd_quote(part) for part in (str(executable), "run", "--execute"))
    return f"""[Unit]
Description=AutoJointQuant daily check-in
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart={command}
TimeoutStartSec=180
"""


def render_systemd_timer(schedule_time: str) -> str:
    validate_time(schedule_time)
    return f"""[Unit]
Description=Run AutoJointQuant every day

[Timer]
OnCalendar=*-*-* {schedule_time}:00
Persistent=true
Unit={SYSTEMD_NAME}.service

[Install]
WantedBy=timers.target
"""


def install_systemd(settings: Settings, executable: Path) -> ScheduleStatus:
    unit_dir = config_home() / "systemd/user"
    service = unit_dir / f"{SYSTEMD_NAME}.service"
    timer = unit_dir / f"{SYSTEMD_NAME}.timer"
    _atomic_bytes(service, render_systemd_service(executable).encode())
    _atomic_bytes(timer, render_systemd_timer(settings.schedule_time).encode())
    _run(["systemctl", "--user", "daemon-reload"])
    try:
        _run(["systemctl", "--user", "enable", "--now", timer.name])
    except SchedulerError as exc:
        if system_name() == "NixOS":
            raise SchedulerError(
                f"{exc}. On a CLI-only NixOS host, enable user lingering with "
                "'users.users.<name>.linger = true' and try again"
            ) from exc
        raise
    return ScheduleStatus("systemd", True, f"{timer} at {settings.schedule_time}")


def remove_systemd() -> ScheduleStatus:
    unit_dir = config_home() / "systemd/user"
    timer = unit_dir / f"{SYSTEMD_NAME}.timer"
    service = unit_dir / f"{SYSTEMD_NAME}.service"
    _run(["systemctl", "--user", "disable", "--now", timer.name], check=False)
    for path in (timer, service):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    _run(["systemctl", "--user", "daemon-reload"], check=False)
    return ScheduleStatus("systemd", False, "systemd user units removed")


def status_systemd() -> ScheduleStatus:
    timer = config_home() / "systemd/user" / f"{SYSTEMD_NAME}.timer"
    if not timer.exists():
        return ScheduleStatus("systemd", False, f"{timer} is absent")
    result = _run(["systemctl", "--user", "is-enabled", timer.name], check=False)
    enabled = result.returncode == 0 and result.stdout.strip() == "enabled"
    detail = result.stdout.strip() or result.stderr.strip() or str(timer)
    return ScheduleStatus("systemd", enabled, detail)


def _launchd_path() -> Path:
    return Path("~/Library/LaunchAgents").expanduser() / f"{LABEL}.plist"


def render_launchd(settings: Settings, executable: Path) -> bytes:
    hour, minute = (int(value) for value in validate_time(settings.schedule_time).split(":"))
    state_dir = default_state_dir()
    payload = {
        "Label": LABEL,
        "ProgramArguments": [str(executable), "run", "--execute"],
        "EnvironmentVariables": {
            "JOINQUANT_ENV_FILE": str(default_env_path()),
            "JOINQUANT_PROFILE_DIR": settings.profile_dir,
        },
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "ProcessType": "Background",
        "StandardOutPath": str(state_dir / "launchd.out.log"),
        "StandardErrorPath": str(state_dir / "launchd.err.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


def install_launchd(settings: Settings, executable: Path) -> ScheduleStatus:
    path = _launchd_path()
    default_state_dir().mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, render_launchd(settings, executable))
    domain = f"gui/{os.getuid()}"
    _run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False)
    _run(["launchctl", "bootstrap", domain, str(path)])
    return ScheduleStatus("launchd", True, f"{path} at {settings.schedule_time}")


def remove_launchd() -> ScheduleStatus:
    path = _launchd_path()
    domain = f"gui/{os.getuid()}"
    _run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return ScheduleStatus("launchd", False, "LaunchAgent removed")


def status_launchd() -> ScheduleStatus:
    path = _launchd_path()
    if not path.exists():
        return ScheduleStatus("launchd", False, f"{path} is absent")
    result = _run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], check=False)
    loaded = result.returncode == 0
    return ScheduleStatus("launchd", loaded, "loaded" if loaded else "plist exists but is not loaded")


def _read_crontab() -> str:
    result = _run(["crontab", "-l"], check=False)
    return result.stdout if result.returncode == 0 else ""


def _without_cron_block(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    inside = False
    for line in lines:
        if line == CRON_BEGIN:
            inside = True
            continue
        if line == CRON_END:
            inside = False
            continue
        if not inside:
            output.append(line)
    return "\n".join(output).strip()


def install_cron(settings: Settings, executable: Path) -> ScheduleStatus:
    hour, minute = validate_time(settings.schedule_time).split(":")
    log_path = default_state_dir() / "cron.log"
    default_state_dir().mkdir(parents=True, exist_ok=True)
    command = " ".join(shlex.quote(value) for value in (str(executable), "run", "--execute"))
    block = f"{CRON_BEGIN}\n{int(minute)} {int(hour)} * * * {command} >> {shlex.quote(str(log_path))} 2>&1\n{CRON_END}"
    previous = _without_cron_block(_read_crontab())
    content = f"{previous}\n{block}\n" if previous else f"{block}\n"
    _run(["crontab", "-"], input_text=content)
    return ScheduleStatus("cron", True, f"daily at {settings.schedule_time}; log={log_path}")


def remove_cron() -> ScheduleStatus:
    remaining = _without_cron_block(_read_crontab())
    _run(["crontab", "-"], input_text=(remaining + "\n") if remaining else "")
    return ScheduleStatus("cron", False, "managed crontab block removed")


def status_cron() -> ScheduleStatus:
    installed = CRON_BEGIN in _read_crontab()
    return ScheduleStatus("cron", installed, "managed block found" if installed else "managed block absent")


def install_schedule(settings: Settings, executable: Path, backend: str = "auto") -> ScheduleStatus:
    selected = select_backend(backend)
    if selected == "launchd":
        return install_launchd(settings, executable)
    if selected == "systemd":
        return install_systemd(settings, executable)
    if selected == "cron":
        return install_cron(settings, executable)
    raise SchedulerError(f"unknown scheduler backend: {selected}")


def remove_schedule(backend: str = "auto") -> ScheduleStatus:
    selected = select_backend(backend)
    if selected == "launchd":
        return remove_launchd()
    if selected == "systemd":
        return remove_systemd()
    if selected == "cron":
        return remove_cron()
    raise SchedulerError(f"unknown scheduler backend: {selected}")


def schedule_status(backend: str = "auto") -> ScheduleStatus:
    selected = select_backend(backend)
    if selected == "launchd":
        return status_launchd()
    if selected == "systemd":
        return status_systemd()
    if selected == "cron":
        return status_cron()
    raise SchedulerError(f"unknown scheduler backend: {selected}")
