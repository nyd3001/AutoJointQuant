import io
from pathlib import Path

from autojoinquant import cli
from autojoinquant.config import UserSettings, load_settings, read_credentials
from autojoinquant.scheduler import ScheduleStatus


def test_config_add_and_remove_without_exposing_password(monkeypatch, tmp_path: Path, capsys):
    config_path = tmp_path / "config.json"
    env_path = tmp_path / "config-home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(env_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data-home"))
    monkeypatch.setattr(cli, "find_node", lambda configured: (Path("/bin/node"), "22.0.0"))
    monkeypatch.setattr(cli, "_diagnose", lambda settings, alias, user: (0, "diagnosis ok"))
    monkeypatch.setattr(
        cli,
        "remove_schedule",
        lambda alias, backend: ScheduleStatus("launchd", False, "removed"),
    )
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("secret-value\n"))

    code = cli.main(
        [
            "--config",
            str(config_path),
            "config",
            "add",
            "main",
            "--username",
            "user@example.com",
            "--password-stdin",
            "--no-schedule",
        ]
    )
    assert code == 0
    settings = load_settings(config_path)
    user = settings.users["main"]
    assert read_credentials(user.env_file)["JOINQUANT_PASSWORD"] == "secret-value"
    output = capsys.readouterr().out
    assert "secret-value" not in output
    assert "us***@example.com" in output

    assert cli.main(["--config", str(config_path), "config", "remove", "main", "--yes"]) == 0
    assert load_settings(config_path).users == {}
    assert not Path(user.env_file).exists()


def test_interactive_password_must_be_confirmed(monkeypatch, tmp_path: Path, capsys):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli.sys, "stdin", type("TTY", (), {"isatty": lambda self: True})())
    values = iter(["first-password", "different-password"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(values))

    code = cli.main(
        [
            "--config",
            str(config_path),
            "config",
            "add",
            "main",
            "--username",
            "user@example.com",
            "--no-schedule",
        ]
    )

    assert code == 2
    assert "passwords do not match" in capsys.readouterr().err
    assert not config_path.exists()


def test_run_executes_by_default_and_dry_run_is_explicit(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.json"
    user = UserSettings(env_file=str(tmp_path / "user.env"), profile_dir=str(tmp_path / "profile"))
    from autojoinquant.config import Settings, save_settings

    save_settings(Settings(users={"main": user}), config_path)
    modes: list[bool] = []

    def fake_run(settings, alias, selected_user, *, execute, diagnose=False, output=None):
        assert alias == "main"
        assert selected_user == user
        assert not diagnose
        modes.append(execute)
        return 0

    monkeypatch.setattr(cli, "run_automation", fake_run)
    assert cli.main(["--config", str(config_path), "run", "main"]) == 0
    assert cli.main(["--config", str(config_path), "run", "main", "--dry-run"]) == 0
    assert modes == [True, False]


def test_parser_has_no_password_argument():
    help_text = cli.build_parser().format_help()
    assert "--password " not in help_text
