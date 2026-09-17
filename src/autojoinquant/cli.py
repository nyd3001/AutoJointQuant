"""AutoJointQuant multi-account command-line entry point."""

from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

from . import __version__
from .config import (
    ConfigError,
    Settings,
    UserSettings,
    default_settings_path,
    get_user,
    load_settings,
    read_credentials,
    read_last_result,
    remove_credentials,
    replace_user,
    save_settings,
    user_state_dir,
    validate_alias,
    validate_time,
    without_user,
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


def _add_credential_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username", help="JoinQuant username; prompts when omitted")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read one password line from stdin; passwords are never accepted as arguments",
    )


def _add_schedule_choice(parser: argparse.ArgumentParser) -> None:
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--schedule", action="store_true", help="enable and install a schedule")
    choice.add_argument("--no-schedule", action="store_true", help="disable the schedule")
    parser.add_argument("--time", help="daily local time in HH:MM format; implies --schedule")
    parser.add_argument("--backend", choices=BACKENDS, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autojoinquant",
        description="Multi-account JoinQuant daily check-in automation.",
        epilog=(
            "Examples: autojoinquant config add main; autojoinquant run main; "
            "autojoinquant status; autojoinquant schedule start main --time 09:00"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help=f"account registry (default: {default_settings_path()})")
    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config", help="add, list, edit, or remove account aliases")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    add = config_commands.add_parser("add", help="add a JoinQuant account")
    add.add_argument("alias", help="local account alias")
    _add_credential_arguments(add)
    _add_schedule_choice(add)

    list_parser = config_commands.add_parser("list", help="list configured accounts")
    list_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    edit = config_commands.add_parser("edit", help="edit credentials or schedule settings")
    edit.add_argument("alias", help="configured account alias")
    _add_credential_arguments(edit)
    _add_schedule_choice(edit)

    remove = config_commands.add_parser("remove", help="remove an account and its credentials")
    remove.add_argument("alias", help="configured account alias")
    remove.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    remove.add_argument("--backend", choices=BACKENDS, default=None)

    run = commands.add_parser("run", help="check in and complete one community reading task")
    run.add_argument("alias", help="configured account alias")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="parse CAPTCHA, drag to an intentionally wrong position, and stop",
    )

    status = commands.add_parser("status", help="check environment, accounts, timers, and results")
    status.add_argument("alias", nargs="?", help="limit output to one account")
    status.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    status.add_argument("--backend", choices=BACKENDS, default=None)

    schedule = commands.add_parser("schedule", help="manage per-account daily timers")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    start = schedule_commands.add_parser("start", help="install or update an account timer")
    start.add_argument("alias", help="configured account alias")
    start.add_argument("--time", help="daily local time in HH:MM format")
    start.add_argument("--backend", choices=BACKENDS, default=None)
    stop = schedule_commands.add_parser("remove", help="remove an account timer")
    stop.add_argument("alias", help="configured account alias")
    stop.add_argument("--backend", choices=BACKENDS, default=None)
    schedule_status_parser = schedule_commands.add_parser("status", help="show account timer state")
    schedule_status_parser.add_argument("alias", help="configured account alias")
    schedule_status_parser.add_argument("--backend", choices=BACKENDS, default=None)
    return parser


def _config_path(value: str | None) -> Path:
    return Path(value or default_settings_path()).expanduser().absolute()


def _prompt_username(existing: str, provided: str | None) -> str:
    if provided is not None:
        return provided.strip()
    if not sys.stdin.isatty():
        if existing:
            return existing
        raise ConfigError("--username is required when input is not interactive")
    suffix = f" [{existing}]" if existing else ""
    return input(f"JoinQuant username{suffix}: ").strip() or existing


def _prompt_password(existing: str, password_stdin: bool) -> str:
    if password_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
    elif sys.stdin.isatty():
        suffix = " (press Enter to keep the current password)" if existing else ""
        value = getpass.getpass(f"JoinQuant password{suffix}: ")
        if value:
            confirmation = getpass.getpass("Confirm JoinQuant password: ")
            if value != confirmation:
                raise ConfigError("passwords do not match")
    elif existing:
        return existing
    else:
        raise ConfigError("use --password-stdin when input is not interactive")
    return value or existing


def _prompt_yes_no(prompt: str, default: bool) -> bool:
    if not sys.stdin.isatty():
        return default
    marker = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{marker}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _schedule_choice(args: argparse.Namespace, existing: bool) -> bool:
    if args.no_schedule and args.time:
        raise ConfigError("--time cannot be combined with --no-schedule")
    if args.schedule or args.time:
        return True
    if args.no_schedule:
        return False
    return _prompt_yes_no("Enable daily automatic check-in?", existing)


def _schedule_time(existing: str, supplied: str | None, enabled: bool) -> str:
    if supplied:
        return validate_time(supplied)
    if not enabled or not sys.stdin.isatty():
        return validate_time(existing)
    value = input(f"Daily check-in time [{existing}]: ").strip() or existing
    return validate_time(value)


def _masked_username(username: str) -> str:
    if not username:
        return "not-configured"
    if "@" in username:
        local, domain = username.split("@", 1)
        visible = local[:2] if len(local) > 1 else local[:1]
        return f"{visible}***@{domain}"
    if len(username) <= 4:
        return username[:1] + "***"
    return f"{username[:2]}***{username[-2:]}"


def _diagnose(settings: Settings, alias: str, user: UserSettings) -> tuple[int, str]:
    output = io.StringIO()
    code = run_automation(
        settings,
        alias,
        user,
        execute=False,
        diagnose=True,
        output=output,
    )
    return code, output.getvalue().strip()


def _install_for_user(
    settings: Settings,
    alias: str,
    user: UserSettings,
    config_path: Path,
    backend: str,
) -> tuple[Settings, str]:
    result = install_schedule(user, alias, current_executable(), config_path, backend)
    updated_user = replace(user, schedule_enabled=True, schedule_backend=result.backend)
    updated = replace_user(settings, alias, updated_user)
    save_settings(updated, config_path)
    return updated, f"{result.backend}; {result.detail}"


def _run_config_add(args: argparse.Namespace) -> int:
    alias = validate_alias(args.alias)
    config_path = _config_path(args.config)
    settings = load_settings(config_path)
    if alias in settings.users:
        raise ConfigError(f"user alias {alias!r} already exists; use 'config edit'")
    user = UserSettings.defaults(alias)
    if os.path.lexists(user.env_file):
        raise ConfigError(f"credentials already exist: {user.env_file}; choose another alias")
    username = _prompt_username("", args.username)
    password = _prompt_password("", args.password_stdin)
    if not username or not password:
        raise ConfigError("username and password are required")
    schedule_enabled = _schedule_choice(args, False)
    schedule_time = _schedule_time(user.schedule_time, args.time, schedule_enabled)
    backend = args.backend or "auto"
    node, node_version = find_node(settings.node_bin)
    user = replace(
        user,
        schedule_enabled=False,
        schedule_time=schedule_time,
        schedule_backend=backend,
    )
    settings = replace(settings, node_bin=str(node))
    settings = replace_user(settings, alias, user)
    credential_path = write_credentials(username, password, user.env_file, overwrite=False)
    save_settings(settings, config_path)
    print(f"Added user: {alias} ({_masked_username(username)})")
    print(f"Credentials: {credential_path} (mode 0600; password hidden)")
    print(f"Runtime: Node.js {node_version} at {node}")
    diagnose_code, diagnose_output = _diagnose(settings, alias, user)
    if diagnose_output:
        print(diagnose_output)
    if diagnose_code != 0:
        print(
            "Account was saved, but environment diagnosis failed; no timer was installed.",
            file=sys.stderr,
        )
        return diagnose_code
    if schedule_enabled:
        _, detail = _install_for_user(settings, alias, user, config_path, backend)
        print(f"Schedule: {detail}")
    else:
        print("Schedule: disabled")
    return 0


def _run_config_edit(args: argparse.Namespace) -> int:
    alias = validate_alias(args.alias)
    config_path = _config_path(args.config)
    settings = load_settings(config_path, required=True)
    existing_user = get_user(settings, alias)
    credentials = read_credentials(existing_user.env_file)
    username = _prompt_username(credentials.get("JOINQUANT_USERNAME", ""), args.username)
    password = _prompt_password(credentials.get("JOINQUANT_PASSWORD", ""), args.password_stdin)
    if not username or not password:
        raise ConfigError("username and password are required")
    schedule_enabled = _schedule_choice(args, existing_user.schedule_enabled)
    schedule_time = _schedule_time(existing_user.schedule_time, args.time, schedule_enabled)
    backend = args.backend or existing_user.schedule_backend
    user = replace(
        existing_user,
        schedule_time=schedule_time,
        schedule_backend=backend,
    )
    write_credentials(username, password, user.env_file)
    settings = replace_user(settings, alias, user)
    save_settings(settings, config_path)
    if schedule_enabled:
        diagnose_code, diagnose_output = _diagnose(settings, alias, user)
        if diagnose_output:
            print(diagnose_output)
        if diagnose_code != 0:
            print(
                "Account was updated, but environment diagnosis failed; timer was not changed.",
                file=sys.stderr,
            )
            return diagnose_code
        settings, detail = _install_for_user(settings, alias, user, config_path, backend)
        print(f"Schedule: {detail}")
    elif existing_user.schedule_enabled:
        result = remove_schedule(alias, backend)
        user = replace(user, schedule_enabled=False)
        settings = replace_user(settings, alias, user)
        save_settings(settings, config_path)
        print(f"Schedule: {result.backend}; removed")
    print(f"Updated user: {alias} ({_masked_username(username)})")
    return 0


def _list_payload(settings: Settings) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for alias, user in sorted(settings.users.items()):
        credentials = read_credentials(user.env_file)
        payload.append(
            {
                "alias": alias,
                "username": _masked_username(credentials.get("JOINQUANT_USERNAME", "")),
                "credentialsConfigured": bool(
                    credentials.get("JOINQUANT_USERNAME") and credentials.get("JOINQUANT_PASSWORD")
                ),
                "scheduleEnabled": user.schedule_enabled,
                "scheduleTime": user.schedule_time,
                "scheduleBackend": user.schedule_backend,
            }
        )
    return payload


def _run_config_list(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    payload = _list_payload(settings)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not payload:
        print("No users configured. Run: autojoinquant config add <alias>")
        return 0
    print("ALIAS\tUSERNAME\tSCHEDULE")
    for item in payload:
        schedule = (
            f"{item['scheduleTime']} ({item['scheduleBackend']})"
            if item["scheduleEnabled"]
            else "disabled"
        )
        print(f"{item['alias']}\t{item['username']}\t{schedule}")
    return 0


def _run_config_remove(args: argparse.Namespace) -> int:
    alias = validate_alias(args.alias)
    config_path = _config_path(args.config)
    settings = load_settings(config_path, required=True)
    user = get_user(settings, alias)
    if not args.yes:
        if not sys.stdin.isatty():
            raise ConfigError("config remove requires --yes when input is not interactive")
        if not _prompt_yes_no(f"Remove user {alias!r}, credentials, and timer?", False):
            print("Cancelled.")
            return 0
    backend = args.backend or user.schedule_backend
    if user.schedule_enabled:
        remove_schedule(alias, backend)
    else:
        try:
            timer = schedule_status(alias, backend)
            if timer.installed:
                remove_schedule(alias, backend)
        except SchedulerError:
            # Removing an unscheduled account must still work on a host without a scheduler.
            pass
    removed_credentials = remove_credentials(user.env_file)
    save_settings(without_user(settings, alias), config_path)
    print(f"Removed user: {alias}")
    print(f"Credentials deleted: {'yes' if removed_credentials else 'already absent'}")
    print(f"Browser profile retained: {user.profile_dir}")
    print(f"Run state retained: {user_state_dir(alias)}")
    return 0


def _account_status(
    alias: str,
    user: UserSettings,
    backend_override: str | None,
) -> dict[str, object]:
    credentials = read_credentials(user.env_file)
    backend = backend_override or user.schedule_backend
    timer = schedule_status(alias, backend)
    return {
        "alias": alias,
        "username": _masked_username(credentials.get("JOINQUANT_USERNAME", "")),
        "credentialsConfigured": bool(
            credentials.get("JOINQUANT_USERNAME") and credentials.get("JOINQUANT_PASSWORD")
        ),
        "scheduleConfigured": user.schedule_enabled,
        "scheduleTime": user.schedule_time,
        "scheduler": asdict(timer),
        "profileDir": user.profile_dir,
        "lastResult": read_last_result(alias),
    }


def _run_status(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.alias:
        aliases = [validate_alias(args.alias)]
        get_user(settings, aliases[0])
    else:
        aliases = sorted(settings.users)
    diagnostic_user = (
        settings.users[aliases[0]] if aliases else UserSettings.defaults("environment-check")
    )
    diagnostic_alias = aliases[0] if aliases else "environment-check"
    code, output = _diagnose(settings, diagnostic_alias, diagnostic_user)
    accounts = [_account_status(alias, settings.users[alias], args.backend) for alias in aliases]
    payload = {
        "platform": system_name(),
        "environment": {"ok": code == 0, "exitCode": code, "details": output.splitlines()},
        "accounts": accounts,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return code
    print(f"Platform: {payload['platform']}")
    print(f"Environment: {'ok' if code == 0 else 'failed'}")
    if output:
        print(output)
    if not accounts:
        print("Accounts: none; run 'autojoinquant config add <alias>'")
        return code
    for account in accounts:
        scheduler = account["scheduler"]
        assert isinstance(scheduler, dict)
        print(f"User: {account['alias']} ({account['username']})")
        print(
            f"  Credentials: {'configured' if account['credentialsConfigured'] else 'incomplete'}"
        )
        print(
            f"  Schedule: {account['scheduleTime']} via {scheduler['backend']}; "
            f"installed={scheduler['installed']} ({scheduler['detail']})"
        )
        last = account["lastResult"]
        if isinstance(last, dict):
            print(
                "  Last result: "
                f"status={last.get('status', 'unknown')}, "
                f"awarded={last.get('pointsAwarded', 'unknown')}, "
                f"available={last.get('pointsAvailable', 'unknown')}, "
                f"total={last.get('pointsTotal', 'unknown')}, "
                f"at={last.get('recordedAt', 'unknown')}"
            )
        else:
            print("  Last result: none")
    return code


def _run_schedule(args: argparse.Namespace) -> int:
    alias = validate_alias(args.alias)
    config_path = _config_path(args.config)
    settings = load_settings(config_path, required=True)
    user = get_user(settings, alias)
    backend = args.backend or user.schedule_backend
    if args.schedule_command == "start":
        if args.time:
            user = replace(user, schedule_time=validate_time(args.time))
        code, output = _diagnose(settings, alias, user)
        if output:
            print(output)
        if code != 0:
            print("Environment diagnosis failed; timer was not installed.", file=sys.stderr)
            return code
        _, detail = _install_for_user(settings, alias, user, config_path, backend)
        print(f"Schedule: {detail}")
        return 0
    if args.schedule_command == "remove":
        result = remove_schedule(alias, backend)
        user = replace(user, schedule_enabled=False, schedule_backend=result.backend)
        save_settings(replace_user(settings, alias, user), config_path)
    else:
        result = schedule_status(alias, backend)
    print(f"Schedule: {result.backend}; installed={result.installed}; {result.detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.config:
        os.environ["AUTOJOINQUANT_CONFIG"] = str(Path(args.config).expanduser())
    try:
        if args.command == "config":
            if args.config_command == "add":
                return _run_config_add(args)
            if args.config_command == "edit":
                return _run_config_edit(args)
            if args.config_command == "list":
                return _run_config_list(args)
            return _run_config_remove(args)
        if args.command == "run":
            settings = load_settings(args.config, required=True)
            alias = validate_alias(args.alias)
            user = get_user(settings, alias)
            return run_automation(settings, alias, user, execute=not args.dry_run)
        if args.command == "status":
            return _run_status(args)
        if args.command == "schedule":
            return _run_schedule(args)
        raise ConfigError(f"unknown command: {args.command}")
    except KeyboardInterrupt:
        return 130
    except (ConfigError, RuntimeError, SchedulerError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
