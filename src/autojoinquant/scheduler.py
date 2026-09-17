"""Per-account cross-platform daily scheduler installation."""

from __future__ import annotations

import os
import platform
import plistlib
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import (
    UserSettings,
    alias_key,
    config_home,
    default_settings_path,
    default_state_dir,
    validate_time,
)

LABEL_PREFIX = "io.github.autojoinquant.checkin"
SYSTEMD_PREFIX = "autojoinquant"


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


def _run(
    command: list[str],
    *,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
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


def _schedule_id(alias: str) -> str:
    return alias_key(alias)


def _systemd_name(alias: str) -> str:
    return f"{SYSTEMD_PREFIX}-{_schedule_id(alias)}"


def _launchd_label(alias: str) -> str:
    return f"{LABEL_PREFIX}.{_schedule_id(alias)}"


def _scheduled_command(executable: Path, alias: str, config_path: Path) -> tuple[str, ...]:
    return (str(executable), "--config", str(config_path), "run", alias)


def render_systemd_service(
    executable: Path,
    alias: str,
    config_path: Path | None = None,
) -> str:
    command = " ".join(
        _systemd_quote(part)
        for part in _scheduled_command(executable, alias, config_path or default_settings_path())
    )
    return f"""[Unit]
Description=AutoJointQuant daily check-in for {alias}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart={command}
TimeoutStartSec=900
"""


def render_systemd_timer(alias: str, schedule_time: str) -> str:
    validate_time(schedule_time)
    return f"""[Unit]
Description=Run AutoJointQuant every day for {alias}

[Timer]
OnCalendar=*-*-* {schedule_time}:00
Persistent=true
Unit={_systemd_name(alias)}.service

[Install]
WantedBy=timers.target
"""


def install_systemd(
    user: UserSettings,
    alias: str,
    executable: Path,
    config_path: Path,
) -> ScheduleStatus:
    unit_dir = config_home() / "systemd/user"
    name = _systemd_name(alias)
    service = unit_dir / f"{name}.service"
    timer = unit_dir / f"{name}.timer"
    _atomic_bytes(service, render_systemd_service(executable, alias, config_path).encode())
    _atomic_bytes(timer, render_systemd_timer(alias, user.schedule_time).encode())
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
    return ScheduleStatus("systemd", True, f"{timer} at {user.schedule_time}")


def remove_systemd(alias: str) -> ScheduleStatus:
    unit_dir = config_home() / "systemd/user"
    name = _systemd_name(alias)
    timer = unit_dir / f"{name}.timer"
    service = unit_dir / f"{name}.service"
    _run(["systemctl", "--user", "disable", "--now", timer.name], check=False)
    for path in (timer, service):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    _run(["systemctl", "--user", "daemon-reload"], check=False)
    return ScheduleStatus("systemd", False, f"schedule removed for {alias}")


def status_systemd(alias: str) -> ScheduleStatus:
    timer = config_home() / "systemd/user" / f"{_systemd_name(alias)}.timer"
    if not timer.exists():
        return ScheduleStatus("systemd", False, f"{timer} is absent")
    result = _run(["systemctl", "--user", "is-enabled", timer.name], check=False)
    enabled = result.returncode == 0 and result.stdout.strip() == "enabled"
    detail = result.stdout.strip() or result.stderr.strip() or str(timer)
    return ScheduleStatus("systemd", enabled, detail)


def _launchd_path(alias: str) -> Path:
    return Path("~/Library/LaunchAgents").expanduser() / f"{_launchd_label(alias)}.plist"


def render_launchd(
    user: UserSettings,
    alias: str,
    executable: Path,
    config_path: Path | None = None,
) -> bytes:
    hour, minute = (int(value) for value in validate_time(user.schedule_time).split(":"))
    state_dir = default_state_dir() / "users" / _schedule_id(alias)
    payload = {
        "Label": _launchd_label(alias),
        "ProgramArguments": list(
            _scheduled_command(executable, alias, config_path or default_settings_path())
        ),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "ProcessType": "Background",
        "StandardOutPath": str(state_dir / "launchd.out.log"),
        "StandardErrorPath": str(state_dir / "launchd.err.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


def install_launchd(
    user: UserSettings,
    alias: str,
    executable: Path,
    config_path: Path,
) -> ScheduleStatus:
    path = _launchd_path(alias)
    (default_state_dir() / "users" / _schedule_id(alias)).mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, render_launchd(user, alias, executable, config_path))
    domain = f"gui/{os.getuid()}"
    label = _launchd_label(alias)
    _run(["launchctl", "bootout", f"{domain}/{label}"], check=False)
    _run(["launchctl", "bootstrap", domain, str(path)])
    return ScheduleStatus("launchd", True, f"{path} at {user.schedule_time}")


def remove_launchd(alias: str) -> ScheduleStatus:
    path = _launchd_path(alias)
    domain = f"gui/{os.getuid()}"
    _run(["launchctl", "bootout", f"{domain}/{_launchd_label(alias)}"], check=False)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return ScheduleStatus("launchd", False, f"schedule removed for {alias}")


def status_launchd(alias: str) -> ScheduleStatus:
    path = _launchd_path(alias)
    if not path.exists():
        return ScheduleStatus("launchd", False, f"{path} is absent")
    result = _run(
        ["launchctl", "print", f"gui/{os.getuid()}/{_launchd_label(alias)}"],
        check=False,
    )
    loaded = result.returncode == 0
    return ScheduleStatus(
        "launchd",
        loaded,
        "loaded" if loaded else "plist exists but is not loaded",
    )


def _cron_begin(alias: str) -> str:
    return f"# BEGIN AUTOJOINQUANT {_schedule_id(alias)}"


def _cron_end(alias: str) -> str:
    return f"# END AUTOJOINQUANT {_schedule_id(alias)}"


def _read_crontab() -> str:
    result = _run(["crontab", "-l"], check=False)
    return result.stdout if result.returncode == 0 else ""


def _without_cron_block(content: str, alias: str) -> str:
    begin = _cron_begin(alias)
    end = _cron_end(alias)
    lines = content.splitlines()
    output: list[str] = []
    inside = False
    for line in lines:
        if line == begin:
            inside = True
            continue
        if line == end:
            inside = False
            continue
        if not inside:
            output.append(line)
    return "\n".join(output).strip()


def install_cron(
    user: UserSettings,
    alias: str,
    executable: Path,
    config_path: Path,
) -> ScheduleStatus:
    hour, minute = validate_time(user.schedule_time).split(":")
    state_dir = default_state_dir() / "users" / _schedule_id(alias)
    log_path = state_dir / "cron.log"
    state_dir.mkdir(parents=True, exist_ok=True)
    command = " ".join(
        shlex.quote(value) for value in _scheduled_command(executable, alias, config_path)
    )
    block = (
        f"{_cron_begin(alias)}\n"
        f"{int(minute)} {int(hour)} * * * {command} >> {shlex.quote(str(log_path))} 2>&1\n"
        f"{_cron_end(alias)}"
    )
    previous = _without_cron_block(_read_crontab(), alias)
    content = f"{previous}\n{block}\n" if previous else f"{block}\n"
    _run(["crontab", "-"], input_text=content)
    return ScheduleStatus("cron", True, f"daily at {user.schedule_time}; log={log_path}")


def remove_cron(alias: str) -> ScheduleStatus:
    remaining = _without_cron_block(_read_crontab(), alias)
    _run(["crontab", "-"], input_text=(remaining + "\n") if remaining else "")
    return ScheduleStatus("cron", False, f"schedule removed for {alias}")


def status_cron(alias: str) -> ScheduleStatus:
    installed = _cron_begin(alias) in _read_crontab()
    return ScheduleStatus(
        "cron",
        installed,
        "managed block found" if installed else "managed block absent",
    )


def install_schedule(
    user: UserSettings,
    alias: str,
    executable: Path,
    config_path: Path | str | None = None,
    backend: str = "auto",
) -> ScheduleStatus:
    selected = select_backend(backend)
    resolved_config = Path(config_path or default_settings_path()).expanduser().absolute()
    if selected == "launchd":
        return install_launchd(user, alias, executable, resolved_config)
    if selected == "systemd":
        return install_systemd(user, alias, executable, resolved_config)
    if selected == "cron":
        return install_cron(user, alias, executable, resolved_config)
    raise SchedulerError(f"unknown scheduler backend: {selected}")


def remove_schedule(alias: str, backend: str = "auto") -> ScheduleStatus:
    selected = select_backend(backend)
    if selected == "launchd":
        return remove_launchd(alias)
    if selected == "systemd":
        return remove_systemd(alias)
    if selected == "cron":
        return remove_cron(alias)
    raise SchedulerError(f"unknown scheduler backend: {selected}")


def schedule_status(alias: str, backend: str = "auto") -> ScheduleStatus:
    selected = select_backend(backend)
    if selected == "launchd":
        return status_launchd(alias)
    if selected == "systemd":
        return status_systemd(alias)
    if selected == "cron":
        return status_cron(alias)
    raise SchedulerError(f"unknown scheduler backend: {selected}")
