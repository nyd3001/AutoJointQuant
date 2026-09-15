"""AutoJointQuant command-line entry point."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

from . import __version__
from .config import (
    ConfigError,
    Settings,
    default_env_path,
    default_settings_path,
    load_settings,
    read_credentials,
    read_last_result,
    save_settings,
    validate_time,
    write_credentials,
)
from .runtime import RuntimeError, current_executable, find_node, run_automation
from .scheduler import (
    SchedulerError,
    install_schedule,
    remove_schedule,
    schedule_status,
    system_name,
)

BACKENDS = ("auto", "launchd", "systemd", "cron")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autojoinquant",
        description="Safe, cross-platform JoinQuant daily check-in automation.",
        epilog=(
            "Examples: autojoinquant init --time 09:00; "
            "autojoinquant run; autojoinquant run --execute; autojoinquant status"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help=f"settings JSON (default: {default_settings_path()})")
    parser.add_argument("--env-file", help=f"protected credential file (default: {default_env_path()})")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="configure credentials, daily time, and scheduler")
    init.add_argument("--username", help="JoinQuant username; password is never accepted as an argument")
    init.add_argument("--password-stdin", action="store_true", help="read one password line from stdin")
    init.add_argument("--time", default=None, help="daily local time in HH:MM format")
    init.add_argument("--no-schedule", action="store_true", help="save config without installing a timer")
    init.add_argument("--backend", choices=BACKENDS, default="auto")

    run = commands.add_parser("run", aliases=["checkin"], help="dry-run or execute one check-in")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="perform login, CAPTCHA, and check-in")
    mode.add_argument("--dry-run", action="store_true", help="inspect state only (default)")

    commands.add_parser("diagnose", help="validate runtimes and browser without visiting JoinQuant")
    status = commands.add_parser("status", help="show config, timer, and the last recorded result")
    status.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    status.add_argument("--backend", choices=BACKENDS, default="auto")

    schedule = commands.add_parser("schedule", help="manage the platform-native daily timer")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    install = schedule_commands.add_parser("install", help="install or update the daily timer")
    install.add_argument("--time", help="replace the configured HH:MM time")
    install.add_argument("--backend", choices=BACKENDS, default="auto")
    remove = schedule_commands.add_parser("remove", help="remove the managed daily timer")
    remove.add_argument("--backend", choices=BACKENDS, default="auto")
    schedule_status_parser = schedule_commands.add_parser("status", help="show timer state")
    schedule_status_parser.add_argument("--backend", choices=BACKENDS, default="auto")

    help_parser = commands.add_parser("help", help="show general or command help")
    help_parser.add_argument("topic", nargs="?")
    return parser


def _topic_help(parser: argparse.ArgumentParser, topic: str | None) -> int:
    if not topic:
        parser.print_help()
        return 0
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    topic_parser = subparsers.choices.get(topic)
    if topic_parser is None:
        raise ConfigError(f"unknown help topic: {topic}")
    topic_parser.print_help()
    return 0


def _prompt_username(existing: str) -> str:
    if not sys.stdin.isatty():
        if existing:
            return existing
        raise ConfigError("--username is required when init is not interactive")
    suffix = " [press Enter to keep the current value]" if existing else ""
    value = input(f"JoinQuant username{suffix}: ").strip()
    return value or existing


def _prompt_password(existing: str, password_stdin: bool) -> str:
    if password_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
    elif sys.stdin.isatty():
        suffix = " (press Enter to keep the current password)" if existing else ""
        value = getpass.getpass(f"JoinQuant password{suffix}: ")
    elif existing:
        return existing
    else:
        raise ConfigError("use --password-stdin when init is not interactive")
    return value or existing


def _prompt_time(existing: str, provided: str | None) -> str:
    if provided:
        return validate_time(provided)
    if not sys.stdin.isatty():
        return validate_time(existing)
    value = input(f"Daily check-in time [{existing}]: ").strip() or existing
    return validate_time(value)


def _run_init(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    credentials = read_credentials(args.env_file)
    username = args.username or _prompt_username(credentials.get("JOINQUANT_USERNAME", ""))
    password = _prompt_password(credentials.get("JOINQUANT_PASSWORD", ""), args.password_stdin)
    schedule_time = _prompt_time(settings.schedule_time, args.time)
    if not username or not password:
        raise ConfigError("username and password are required")
    node, node_version = find_node(settings.node_bin)
    updated = replace(settings, schedule_time=schedule_time, node_bin=str(node))
    config_path = save_settings(updated, args.config)
    env_path = write_credentials(username, password, args.env_file)
    print(f"Configuration: {config_path}")
    print(f"Credentials: {env_path} (mode 0600; values hidden)")
    print(f"Runtime: Node.js {node_version} at {node}")
    diagnose_code = run_automation(updated, execute=False, diagnose=True)
    if diagnose_code != 0:
        print("Configuration was saved, but runtime diagnosis failed; scheduler was not installed.", file=sys.stderr)
        return diagnose_code
    if args.no_schedule:
        print("Scheduler: skipped (--no-schedule)")
        return 0
    installed = install_schedule(updated, current_executable(), args.backend)
    print(f"Scheduler: {installed.backend}, {installed.detail}")
    return 0


def _status_payload(settings: Settings, backend: str) -> dict[str, object]:
    credentials = read_credentials()
    timer = schedule_status(backend)
    return {
        "platform": system_name(),
        "scheduler": asdict(timer),
        "scheduleTime": settings.schedule_time,
        "profileDir": settings.profile_dir,
        "nodeBin": settings.node_bin,
        "credentialsConfigured": bool(
            credentials.get("JOINQUANT_USERNAME") and credentials.get("JOINQUANT_PASSWORD")
        ),
        "lastResult": read_last_result(),
    }


def _print_status(payload: dict[str, object]) -> None:
    scheduler = payload["scheduler"]
    assert isinstance(scheduler, dict)
    print(f"Platform: {payload['platform']}")
    print(f"Credentials: {'configured' if payload['credentialsConfigured'] else 'incomplete'}")
    print(f"Schedule: {payload['scheduleTime']} via {scheduler['backend']} ({scheduler['detail']})")
    print(f"Profile: {payload['profileDir']}")
    last = payload["lastResult"]
    if isinstance(last, dict):
        print(
            "Last result: "
            f"status={last.get('status', 'unknown')}, "
            f"awarded={last.get('pointsAwarded', 'unknown')}, "
            f"available={last.get('pointsAvailable', 'unknown')}, "
            f"total={last.get('pointsTotal', 'unknown')}, "
            f"at={last.get('recordedAt', 'unknown')}"
        )
    else:
        print("Last result: none")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.config:
        os.environ["AUTOJOINQUANT_CONFIG"] = str(Path(args.config).expanduser())
    if args.env_file:
        os.environ["JOINQUANT_ENV_FILE"] = str(Path(args.env_file).expanduser())
    try:
        if args.command == "help":
            return _topic_help(parser, args.topic)
        if args.command == "init":
            return _run_init(args)

        settings = load_settings(args.config)
        if args.command in {"run", "checkin"}:
            return run_automation(settings, execute=args.execute)
        if args.command == "diagnose":
            node, version = find_node(settings.node_bin)
            print(f"Detected platform: {system_name()}; Node.js {version}: {node}")
            return run_automation(settings, execute=False, diagnose=True)
        if args.command == "status":
            payload = _status_payload(settings, args.backend)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_status(payload)
            return 0
        if args.command == "schedule":
            if args.schedule_command == "install":
                if args.time:
                    settings = replace(settings, schedule_time=validate_time(args.time))
                    save_settings(settings, args.config)
                result = install_schedule(settings, current_executable(), args.backend)
            elif args.schedule_command == "remove":
                result = remove_schedule(args.backend)
            else:
                result = schedule_status(args.backend)
            print(f"Scheduler: {result.backend}; installed={result.installed}; {result.detail}")
            return 0
        raise ConfigError(f"unknown command: {args.command}")
    except KeyboardInterrupt:
        return 130
    except (ConfigError, RuntimeError, SchedulerError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
