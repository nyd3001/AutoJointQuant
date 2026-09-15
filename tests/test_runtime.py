import io
from pathlib import Path

from autojoinquant import runtime
from autojoinquant.config import Settings, UserSettings
from autojoinquant.runtime import find_node


def _fake_node(path: Path, version: str) -> None:
    path.write_text(f"#!/bin/sh\necho v{version}\n")
    path.chmod(0o755)


def test_find_node_skips_old_path_entry(tmp_path: Path, monkeypatch):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    _fake_node(old / "node", "18.20.0")
    _fake_node(new / "node", "22.14.0")
    monkeypatch.setenv("PATH", f"{old}:{new}")
    monkeypatch.delenv("JOINQUANT_NODE_BIN", raising=False)
    executable, version = find_node()
    assert executable == (new / "node").resolve()
    assert version == "22.14.0"


class _FakeProcess:
    def __init__(self, lines: list[str], return_code: int = 0):
        self.stdout = iter(lines)
        self.return_code = return_code

    def wait(self) -> int:
        return self.return_code


def test_internal_result_marker_is_parsed_but_not_printed(tmp_path: Path, monkeypatch):
    marker = (
        'AUTOJOINQUANT_RESULT={"status":"already-checked-in","pointsAwarded":0,'
        '"pointsAvailable":50,"pointsTotal":50}\n'
    )
    process = _FakeProcess(["[joinquant] 积分结果：本次=0，可用=50，累计=50\n", marker])
    monkeypatch.setattr(runtime, "find_node", lambda configured: (Path("/bin/node"), "22.0.0"))
    monkeypatch.setattr(runtime, "automation_script", lambda: tmp_path / "checkin.mjs")
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    output = io.StringIO()
    user = UserSettings(env_file=str(tmp_path / "user.env"), profile_dir=str(tmp_path / "profile"))

    code = runtime.run_automation(
        Settings(),
        "main",
        user,
        execute=False,
        output=output,
    )

    assert code == 0
    assert "积分结果：本次=0，可用=50，累计=50" in output.getvalue()
    assert "AUTOJOINQUANT_RESULT" not in output.getvalue()


def test_missing_internal_result_changes_false_success_to_failure(tmp_path: Path, monkeypatch):
    process = _FakeProcess(["[joinquant] 页面确认今日已经签到，无需重复操作\n"])
    monkeypatch.setattr(runtime, "find_node", lambda configured: (Path("/bin/node"), "22.0.0"))
    monkeypatch.setattr(runtime, "automation_script", lambda: tmp_path / "checkin.mjs")
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    output = io.StringIO()
    user = UserSettings(env_file=str(tmp_path / "user.env"), profile_dir=str(tmp_path / "profile"))

    code = runtime.run_automation(
        Settings(),
        "main",
        user,
        execute=False,
        output=output,
    )

    assert code == 1
    assert "内部结果缺失" in output.getvalue()
