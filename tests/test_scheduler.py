import plistlib
from pathlib import Path

from autojoinquant.config import UserSettings, alias_key
from autojoinquant.scheduler import render_launchd, render_systemd_service, render_systemd_timer


def test_systemd_units_contain_alias_schedule_and_config_path():
    executable = Path("/opt/tools/autojoinquant")
    config_path = Path("/home/test/.config/autojoinquant/config.json")
    service = render_systemd_service(executable, "main", config_path)
    timer = render_systemd_timer("main", "08:45")
    assert (
        'ExecStart="/opt/tools/autojoinquant" "--config" '
        '"/home/test/.config/autojoinquant/config.json" "run" "main"'
    ) in service
    assert "OnCalendar=*-*-* 08:45:00" in timer
    assert f"Unit=autojoinquant-{alias_key('main')}.service" in timer
    assert "Persistent=true" in timer


def test_launchd_plist_contains_account_and_exact_schedule(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    user = UserSettings(
        env_file=str(tmp_path / "main.env"),
        profile_dir=str(tmp_path / "profile"),
        schedule_time="06:05",
    )
    payload = plistlib.loads(
        render_launchd(
            user,
            "私人账号",
            Path("/usr/local/bin/autojoinquant"),
            tmp_path / "config.json",
        )
    )
    assert payload["StartCalendarInterval"] == {"Hour": 6, "Minute": 5}
    assert payload["ProgramArguments"][-2:] == ["run", "私人账号"]
    assert payload["ProgramArguments"][1:3] == ["--config", str(tmp_path / "config.json")]
    assert alias_key("私人账号") in payload["Label"]
    assert "EnvironmentVariables" not in payload
