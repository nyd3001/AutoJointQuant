import json
import os
from pathlib import Path

import pytest

from autojoinquant.config import (
    ConfigError,
    Settings,
    UserSettings,
    alias_key,
    load_settings,
    read_credentials,
    read_last_result,
    save_settings,
    user_env_path,
    user_profile_path,
    validate_alias,
    validate_time,
    write_credentials,
    write_last_result,
)


def test_settings_round_trip_multiple_users(tmp_path: Path):
    path = tmp_path / "config.json"
    expected = Settings(
        node_bin="/bin/node",
        users={
            "main": UserSettings(
                env_file="/tmp/main.env",
                profile_dir="/tmp/main-profile",
                schedule_enabled=True,
                schedule_time="07:35",
                schedule_backend="launchd",
            ),
            "work": UserSettings(
                env_file="/tmp/work.env",
                profile_dir="/tmp/work-profile",
            ),
        },
    )
    save_settings(expected, path)
    assert load_settings(path) == expected
    assert json.loads(path.read_text())["version"] == 2


def test_old_config_version_is_rejected(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text('{"version": 1, "schedule_time": "09:00"}')
    with pytest.raises(ConfigError, match="unsupported config version"):
        load_settings(path)


def test_alias_paths_are_isolated_and_do_not_expose_alias(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert alias_key("私人账号") == alias_key("私人账号")
    assert alias_key("私人账号") != alias_key("工作账号")
    assert "私人账号" not in str(user_env_path("私人账号"))
    assert user_env_path("私人账号") != user_env_path("工作账号")
    assert user_profile_path("私人账号") != user_profile_path("工作账号")
    for value in ("", ".", "..", "bad/name", "bad\nname"):
        with pytest.raises(ConfigError):
            validate_alias(value)


def test_validate_time_rejects_invalid_values():
    for value in ["9:00", "24:00", "12:60", "noon"]:
        with pytest.raises(ConfigError):
            validate_time(value)


def test_credentials_round_trip_and_permissions(tmp_path: Path):
    path = tmp_path / "credentials.env"
    write_credentials("user@example.com", 'p$a\\ss"word', path)
    values = read_credentials(path)
    assert values["JOINQUANT_USERNAME"] == "user@example.com"
    assert values["JOINQUANT_PASSWORD"] == 'p$a\\ss"word'
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_credentials_preserve_unrelated_options(tmp_path: Path):
    path = tmp_path / "credentials.env"
    path.write_text("JOINQUANT_HEADLESS=1\nJOINQUANT_USERNAME=old\n")
    path.chmod(0o600)
    write_credentials("new", "secret", path)
    content = path.read_text()
    assert "JOINQUANT_HEADLESS=1" in content
    assert "JOINQUANT_USERNAME=old" not in content


def test_last_results_are_isolated_by_alias(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    write_last_result("main", {"pointsAvailable": 10})
    write_last_result("work", {"pointsAvailable": 20})
    assert read_last_result("main") == {"pointsAvailable": 10}
    assert read_last_result("work") == {"pointsAvailable": 20}
