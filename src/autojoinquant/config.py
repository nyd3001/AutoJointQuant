"""Multi-account configuration and protected credential-file handling."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ASSIGNMENT_PATTERN = re.compile(r"^\s*(?:export\s+)?(JOINQUANT_[A-Z0-9_]+)\s*=")
SCHEDULER_BACKENDS = {"auto", "launchd", "systemd", "cron"}


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


def default_state_dir() -> Path:
    return state_home() / "autojoinquant"


def validate_alias(value: str) -> str:
    alias = value.strip()
    if not alias:
        raise ConfigError("alias cannot be empty")
    if len(alias) > 64:
        raise ConfigError("alias must be at most 64 characters")
    forbidden = {"/", "\\", "\0", "\n", "\r", "\t"}
    if alias in {".", ".."} or any(char in alias for char in forbidden):
        raise ConfigError("alias contains an unsupported path or control character")
    if any(ord(char) < 32 for char in alias):
        raise ConfigError("alias contains an unsupported control character")
    return alias


def alias_key(alias: str) -> str:
    """Return a stable filesystem/scheduler-safe key without exposing the alias."""
    return hashlib.sha256(validate_alias(alias).encode("utf-8")).hexdigest()[:16]


def user_env_path(alias: str) -> Path:
    return config_home() / "autojoinquant/users" / f"{alias_key(alias)}.env"


def user_profile_path(alias: str) -> Path:
    return data_home() / "autojoinquant/profiles" / alias_key(alias)


def user_state_dir(alias: str) -> Path:
    return default_state_dir() / "users" / alias_key(alias)


def validate_time(value: str) -> str:
    if not TIME_PATTERN.fullmatch(value):
        raise ConfigError("time must use 24-hour HH:MM format")
    return value


@dataclass(frozen=True)
class UserSettings:
    env_file: str
    profile_dir: str
    schedule_enabled: bool = False
    schedule_time: str = "09:00"
    schedule_backend: str = "auto"

    @classmethod
    def defaults(cls, alias: str) -> UserSettings:
        return cls(
            env_file=str(user_env_path(alias)),
            profile_dir=str(user_profile_path(alias)),
        )


@dataclass(frozen=True)
class Settings:
    version: int = 2
    node_bin: str = ""
    users: dict[str, UserSettings] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> Settings:
        return cls()


def _validate_user(alias: str, raw: Any) -> UserSettings:
    validate_alias(alias)
    if isinstance(raw, UserSettings):
        raw = asdict(raw)
    if not isinstance(raw, dict):
        raise ConfigError(f"user settings for {alias!r} must be an object")
    defaults = UserSettings.defaults(alias)
    env_file = raw.get("env_file", defaults.env_file)
    profile_dir = raw.get("profile_dir", defaults.profile_dir)
    schedule_enabled = raw.get("schedule_enabled", False)
    schedule_time = raw.get("schedule_time", "09:00")
    schedule_backend = raw.get("schedule_backend", "auto")
    if not isinstance(env_file, str) or not env_file:
        raise ConfigError(f"env_file for {alias!r} must be a non-empty string")
    if not isinstance(profile_dir, str) or not profile_dir:
        raise ConfigError(f"profile_dir for {alias!r} must be a non-empty string")
    if not isinstance(schedule_enabled, bool):
        raise ConfigError(f"schedule_enabled for {alias!r} must be a boolean")
    if schedule_backend not in SCHEDULER_BACKENDS:
        raise ConfigError(f"invalid scheduler backend for {alias!r}")
    if not isinstance(schedule_time, str):
        raise ConfigError(f"schedule_time for {alias!r} must be a string")
    return UserSettings(
        env_file=str(Path(env_file).expanduser()),
        profile_dir=str(Path(profile_dir).expanduser()),
        schedule_enabled=schedule_enabled,
        schedule_time=validate_time(schedule_time),
        schedule_backend=schedule_backend,
    )


def _validate_settings(raw: Any) -> Settings:
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a JSON object")
    if raw.get("version") != 2:
        raise ConfigError(
            "unsupported config version; create a fresh registry with "
            "'autojoinquant config add <alias>'"
        )
    node_bin = raw.get("node_bin", "")
    users = raw.get("users", {})
    if not isinstance(node_bin, str):
        raise ConfigError("node_bin must be a string")
    if not isinstance(users, dict):
        raise ConfigError("users must be an object keyed by alias")
    return Settings(
        node_bin=node_bin,
        users={alias: _validate_user(alias, value) for alias, value in users.items()},
    )


def load_settings(path: Path | str | None = None, *, required: bool = False) -> Settings:
    config_path = Path(path or default_settings_path()).expanduser()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise ConfigError(
                f"config not found: {config_path}; run 'autojoinquant config add <alias>'"
            )
        return Settings.defaults()
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    return _validate_settings(raw)


def _atomic_write(
    path: Path, content: str, mode: int = 0o600, *, overwrite: bool = True
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # Publish the complete file atomically, refusing any existing destination.
            os.link(temporary, path)
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


def get_user(settings: Settings, alias: str) -> UserSettings:
    validated = validate_alias(alias)
    try:
        return settings.users[validated]
    except KeyError as exc:
        raise ConfigError(
            f"unknown user alias {validated!r}; run 'autojoinquant config list'"
        ) from exc


def replace_user(settings: Settings, alias: str, user: UserSettings) -> Settings:
    validated = validate_alias(alias)
    users = dict(settings.users)
    users[validated] = _validate_user(validated, user)
    return Settings(node_bin=settings.node_bin, users=users)


def without_user(settings: Settings, alias: str) -> Settings:
    validated = validate_alias(alias)
    if validated not in settings.users:
        raise ConfigError(f"unknown user alias {validated!r}")
    users = dict(settings.users)
    del users[validated]
    return Settings(node_bin=settings.node_bin, users=users)


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


def read_credentials(path: Path | str) -> dict[str, str]:
    env_path = Path(path).expanduser()
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


def write_credentials(
    username: str, password: str, path: Path | str, *, overwrite: bool = True
) -> Path:
    env_path = Path(path).expanduser()
    for name, value in (("username", username), ("password", password)):
        if not value:
            raise ConfigError(f"{name} cannot be empty")
        if "\n" in value or "\r" in value or "\0" in value:
            raise ConfigError(f"{name} contains an unsupported control character")
    try:
        old_lines = env_path.read_text(encoding="utf-8").splitlines() if overwrite else []
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
    try:
        _atomic_write(env_path, "\n".join(kept).rstrip() + "\n", overwrite=overwrite)
    except FileExistsError as exc:
        raise ConfigError(f"credentials already exist: {env_path}; choose another alias") from exc
    return env_path


def remove_credentials(path: Path | str) -> bool:
    try:
        Path(path).expanduser().unlink()
    except FileNotFoundError:
        return False
    return True


def write_last_result(alias: str, result: dict[str, Any]) -> Path:
    path = user_state_dir(alias) / "last-run.json"
    _atomic_write(path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return path


def read_last_result(alias: str) -> dict[str, Any] | None:
    path = user_state_dir(alias) / "last-run.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
