"""Node.js runtime discovery and execution bridge."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .config import Settings, UserSettings, read_last_result, write_last_result

RESULT_PREFIX = "AUTOJOINQUANT_RESULT="


class RuntimeError(ValueError):
    """A required local runtime is unavailable."""


def _node_candidates(configured: str = "") -> Iterable[Path]:
    seen: set[Path] = set()
    raw: list[Path] = []
    for value in (os.environ.get("JOINQUANT_NODE_BIN", ""), configured):
        if value:
            raw.append(Path(value).expanduser())
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if directory:
            raw.append(Path(directory).expanduser() / ("node.exe" if os.name == "nt" else "node"))
    if sys.platform == "darwin":
        raw.extend(
            Path(value).expanduser()
            for value in (
                "/opt/homebrew/bin/node",
                "/usr/local/bin/node",
                "~/miniforge3/bin/node",
                "~/miniconda3/bin/node",
            )
        )
    else:
        raw.extend(
            Path(value).expanduser()
            for value in (
                "~/.nix-profile/bin/node",
                "/run/current-system/sw/bin/node",
                "/nix/var/nix/profiles/default/bin/node",
                "/usr/bin/node",
                "/usr/local/bin/node",
            )
        )
    for candidate in raw:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved not in seen:
            seen.add(resolved)
            yield resolved


def node_version(executable: Path) -> tuple[int, str] | None:
    if not executable.is_file() or not os.access(executable, os.X_OK):
        return None
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        text = result.stdout.strip().lstrip("v")
        return int(text.split(".", 1)[0]), text
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def find_node(configured: str = "") -> tuple[Path, str]:
    rejected: list[str] = []
    for candidate in _node_candidates(configured):
        version = node_version(candidate)
        if version and version[0] >= 22:
            return candidate, version[1]
        if version:
            rejected.append(f"{candidate} (v{version[1]})")
    detail = f"; ignored old versions: {', '.join(rejected)}" if rejected else ""
    raise RuntimeError("Node.js 22+ was not found. Install it or set JOINQUANT_NODE_BIN" + detail)


def automation_script() -> Path:
    source_root = Path(__file__).resolve().parents[2]
    source_script = source_root / "checkin.mjs"
    if source_script.is_file():
        return source_script
    installed = Path(sys.prefix) / "share" / "autojoinquant" / "checkin.mjs"
    if installed.is_file():
        return installed
    raise RuntimeError("installed checkin.mjs resource was not found")


def run_automation(
    settings: Settings,
    alias: str,
    user: UserSettings,
    *,
    execute: bool,
    diagnose: bool = False,
    output: TextIO | None = None,
) -> int:
    node, _ = find_node(settings.node_bin)
    command = [str(node), str(automation_script())]
    if diagnose:
        command.append("--diagnose")
    elif execute:
        command.append("--execute")
    else:
        command.append("--dry-run")
    environment = os.environ.copy()
    # A named account must never inherit credentials for a different shell user.
    environment.pop("JOINQUANT_USERNAME", None)
    environment.pop("JOINQUANT_PASSWORD", None)
    credential_path = Path(user.env_file).expanduser()
    environment["JOINQUANT_ENV_FILE"] = (
        "-" if diagnose and not credential_path.is_file() else str(credential_path)
    )
    environment["JOINQUANT_PROFILE_DIR"] = user.profile_dir
    environment["JOINQUANT_PYTHON"] = sys.executable
    environment["AUTOJOINQUANT_ALIAS"] = alias
    previous = read_last_result(alias) if execute and not diagnose else None
    environment["AUTOJOINQUANT_PREVIOUS_READING"] = json.dumps(
        (previous or {}).get("reading") or {}
    )

    process = subprocess.Popen(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    result: dict[str, object] | None = None
    destination = output or sys.stdout
    assert process.stdout is not None
    for line in process.stdout:
        if line.startswith(RESULT_PREFIX):
            try:
                parsed = json.loads(line[len(RESULT_PREFIX) :])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                result = parsed
            continue
        print(line, end="", file=destination)
    return_code = process.wait()
    if not diagnose and result is None and return_code == 0:
        print("[joinquant] 内部结果缺失，无法确认本次运行状态", file=destination)
        return_code = 1
    if execute and result is not None:
        result["recordedAt"] = datetime.now(timezone.utc).isoformat()
        result["exitCode"] = return_code
        write_last_result(alias, result)
    return return_code


def current_executable() -> Path:
    override = os.environ.get("AUTOJOINQUANT_EXECUTABLE")
    if override:
        path = Path(override).expanduser().absolute()
        if path.is_file():
            return path
    discovered = shutil.which("autojoinquant")
    if discovered:
        return Path(discovered).absolute()
    invoked = Path(sys.argv[0]).expanduser()
    if invoked.is_file() and os.access(invoked, os.X_OK):
        return invoked.absolute()
    raise RuntimeError(
        "cannot resolve the global autojoinquant executable; install with 'uv tool install .' "
        "or 'nix profile install .' first"
    )
