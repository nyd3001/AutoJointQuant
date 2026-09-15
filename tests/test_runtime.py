from pathlib import Path

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
