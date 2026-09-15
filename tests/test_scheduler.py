import plistlib
from pathlib import Path

from autojoinquant.config import Settings
from autojoinquant.scheduler import render_launchd, render_systemd_service, render_systemd_timer


def test_systemd_units_contain_exact_schedule_and_command():
    executable = Path("/opt/tools/autojoinquant")
    service = render_systemd_service(executable)
    timer = render_systemd_timer("08:45")
    assert 'ExecStart="/opt/tools/autojoinquant" "run" "--execute"' in service
    assert "OnCalendar=*-*-* 08:45:00" in timer
    assert "Persistent=true" in timer


def test_launchd_plist_contains_exact_schedule(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = Settings(schedule_time="06:05", profile_dir=str(tmp_path / "profile"))
    payload = plistlib.loads(render_launchd(settings, Path("/usr/local/bin/autojoinquant")))
    assert payload["StartCalendarInterval"] == {"Hour": 6, "Minute": 5}
    assert payload["ProgramArguments"][-2:] == ["run", "--execute"]
