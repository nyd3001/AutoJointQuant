"""Configuration and protected credential-file handling."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ASSIGNMENT_PATTERN = re.compile(r"^\s*(?:export\s+)?(JOINQUANT_[A-Z0-9_]+)\s*=")


class ConfigError(ValueError):
    """The local configuration cannot be used safely."""


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()


def state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()


def default_settings_path() -> Path:
    return Path(
        os.environ.get("AUTOJOINQUANT_CONFIG", config_home() / "autojoinquant/config.json")
    ).expanduser()


def default_env_path() -> Path:
    return Path(
        os.environ.get("JOINQUANT_ENV_FILE", config_home() / "autojoinquant.env")
    ).expanduser()


def default_profile_path() -> Path:
    return Path(
        os.environ.get(
            "JOINQUANT_PROFILE_DIR",
            data_home() / "autojoinquant/chrome-profile",
        )
    ).expanduser()


def default_state_dir() -> Path:
    return state_home() / "autojoinquant"


def validate_time(value: str) -> str:
    if not TIME_PATTERN.fullmatch(value):
        raise ConfigError("time must use 24-hour HH:MM format")
    return value


@dataclass(frozen=True)
class Settings:
    version: int = 1
    schedule_time: str = "09:00"
    node_bin: str = ""
    profile_dir: str = ""

    @classmethod
    def defaults(cls) -> Settings:
        return cls(profile_dir=str(default_profile_path()))


def _validate_settings(raw: Any) -> Settings:
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a JSON object")
    if raw.get("version", 1) != 1:
        raise ConfigError("unsupported config version")
    schedule_time = raw.get("schedule_time", "09:00")
    node_bin = raw.get("node_bin", "")
    profile_dir = raw.get("profile_dir", str(default_profile_path()))
    if not isinstance(schedule_time, str):
        raise ConfigError("schedule_time must be a string")
    if not isinstance(node_bin, str) or not isinstance(profile_dir, str) or not profile_dir:
        raise ConfigError("node_bin and profile_dir must be strings")
    return Settings(
        schedule_time=validate_time(schedule_time),
        node_bin=node_bin,
        profile_dir=str(Path(profile_dir).expanduser()),
    )


def load_settings(path: Path | str | None = None, *, required: bool = False) -> Settings:
    config_path = Path(path or default_settings_path()).expanduser()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise ConfigError(f"config not found: {config_path}; run 'autojoinquant init'")
        return Settings.defaults()
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    return _validate_settings(raw)


def _atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
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


def save_settings(settings: Settings, path: Path | str | None = None) -> Path:
    config_path = Path(path or default_settings_path()).expanduser()
    validated = _validate_settings(asdict(settings))
    content = json.dumps(asdict(validated), ensure_ascii=False, indent=2) + "\n"
    _atomic_write(config_path, content)
    return config_path


def _decode_dotenv_value(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigError("invalid double-quoted value in credential file") from exc
        if not isinstance(decoded, str):
            raise ConfigError("credential value must be a string")
        return decoded
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def read_credentials(path: Path | str | None = None) -> dict[str, str]:
    env_path = Path(path or default_env_path()).expanduser()
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    if os.name != "nt" and env_path.stat().st_mode & 0o077:
        raise ConfigError(f"credential file permissions are too broad: chmod 600 '{env_path}'")
    result: dict[str, str] = {}
    for line in lines:
        match = ASSIGNMENT_PATTERN.match(line)
        if match:
            result[match.group(1)] = _decode_dotenv_value(line[match.end() :])
    return result


def write_credentials(username: str, password: str, path: Path | str | None = None) -> Path:
    env_path = Path(path or default_env_path()).expanduser()
    for name, value in (("username", username), ("password", password)):
        if not value:
            raise ConfigError(f"{name} cannot be empty")
        if "\n" in value or "\r" in value or "\0" in value:
            raise ConfigError(f"{name} contains an unsupported control character")
    try:
        old_lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        old_lines = ["# AutoJointQuant credentials. Keep this file private; do not source it."]
    kept = [
        line
        for line in old_lines
        if not (
            (match := ASSIGNMENT_PATTERN.match(line))
            and match.group(1) in {"JOINQUANT_USERNAME", "JOINQUANT_PASSWORD"}
        )
    ]
    kept.extend(
        [
            f"JOINQUANT_USERNAME={json.dumps(username, ensure_ascii=False)}",
            f"JOINQUANT_PASSWORD={json.dumps(password, ensure_ascii=False)}",
        ]
    )
    _atomic_write(env_path, "\n".join(kept).rstrip() + "\n")
    return env_path


def write_last_result(result: dict[str, Any]) -> Path:
    path = default_state_dir() / "last-run.json"
    _atomic_write(path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return path


def read_last_result() -> dict[str, Any] | None:
    path = default_state_dir() / "last-run.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
