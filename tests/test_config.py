import json
import os
from pathlib import Path

import pytest

from autojoinquant.config import (
    ConfigError,
    Settings,
    load_settings,
    read_credentials,
    save_settings,
    validate_time,
    write_credentials,
)


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "config.json"
    expected = Settings(schedule_time="07:35", node_bin="/bin/node", profile_dir="/tmp/profile")
    save_settings(expected, path)
    assert load_settings(path) == expected
    assert json.loads(path.read_text())["version"] == 1


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
