# AutoJointQuant

[![CI](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[中文说明](README.md)

AutoJointQuant is a multi-account JoinQuant daily check-in CLI with scheduling. It logs in, solves the puzzle, checks in, and reports points without Computer Use.
It performs only the daily check-in. macOS is validated live; Linux and NixOS are configured but not yet validated on real systems.
Chrome/Chromium is supported; Firefox is not currently supported.

## Installation

The uv installation requires Python 3.10+, uv, Node.js 22+, and Chrome/Chromium.

Install globally from this checkout:

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
```

Update the installed checkout:

```bash
uv tool install --force .
```

With Nix/NixOS:

```bash
nix profile install .
autojoinquant --version
```

No system Node.js installation is required. The three Nix entry points have different scopes:

| Entry point | Scope | Use case |
| --- | --- | --- |
| `nix develop` | Current development shell only | Provides Node.js 22, uv, Python, and puzzle-solver dependencies |
| `nix run . -- <command>` | One process | Runs the CLI temporarily without installing it |
| `nix profile install .` | Persistent for the current user | Recommended for normal use and schedulers |

Run without installing:

```bash
nix run . -- status
```

Scheduled jobs should use the stable global command produced by `uv tool install` or `nix profile install`, not a temporary `nix run` store path.

## Quick start

```bash
# 1. Add an account; prompts cover username, hidden password, schedule, and time
autojoinquant config add main

# 2. Preview first: visit the page without login, check-in, or slider movement
autojoinquant run main --dry-run

# 3. Perform one real check-in
autojoinquant run main

# 4. Inspect the environment, scheduler, and last points
autojoinquant status main
```

`run <alias>` changes website state by default. Use `--dry-run` after an upgrade, on a new host, or when page behavior changes.

## Configuration

The default registry is `~/.config/autojoinquant/config.json`. Override it by placing `--config PATH` before the command, or set `AUTOJOINQUANT_CONFIG`.

```bash
autojoinquant --config /path/to/config.json status
```

Each alias maps to a stable hash used to isolate local files and scheduler entries:

```text
~/.config/autojoinquant/config.json
~/.config/autojoinquant/users/<account-hash>.env
~/.local/share/autojoinquant/profiles/<account-hash>/
~/.local/state/autojoinquant/users/<account-hash>/last-run.json
```

The registry stores paths and scheduler settings, not plaintext passwords:

```json
{
  "version": 2,
  "node_bin": "/path/to/node",
  "users": {
    "main": {
      "env_file": "/home/user/.config/autojoinquant/users/<account-hash>.env",
      "profile_dir": "/home/user/.local/share/autojoinquant/profiles/<account-hash>",
      "schedule_enabled": true,
      "schedule_time": "09:00",
      "schedule_backend": "systemd"
    }
  }
}
```

The CLI normally owns this file. Manage accounts with:

```bash
autojoinquant config add main
autojoinquant config list
autojoinquant config edit main
autojoinquant config remove main
```

`config list` and `status` mask usernames. `config remove` deletes the registry entry, credentials, and timer, but retains the browser profile and result history and prints their locations.

Non-interactive setup can read one password line from stdin. There is deliberately no `--password` argument:

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main \
  --username "$JOINQUANT_USERNAME" \
  --password-stdin --schedule --time 09:00
```

### Upgrading from 0.2

Version 0.3 does not migrate the old single-account registry. Back it up, then add the account again:

```bash
mv ~/.config/autojoinquant/config.json \
  ~/.config/autojoinquant/config.v1.backup.json
autojoinquant config add main
```

New aliases do not load the old `~/.config/autojoinquant.env` automatically.

## Commands

```text
autojoinquant config add <alias>
autojoinquant config list [--json]
autojoinquant config edit <alias>
autojoinquant config remove <alias> [--yes]

autojoinquant run <alias> [--dry-run]
autojoinquant status [alias] [--json]

autojoinquant schedule start <alias> [--time HH:MM]
autojoinquant schedule status <alias>
autojoinquant schedule remove <alias>
```

Use `autojoinquant <command> --help` for complete options.

### `run`

`run <alias>` opens the account's dedicated browser profile. When login is required it fills the credentials, solves the puzzle, and performs only the daily check-in. The program selects JoinQuant tabs only and does not navigate normal browser tabs.

Normal output is human-readable:

```text
[joinquant] 页面确认今日已经签到，无需重复操作
[joinquant] 积分结果：本次=0，可用=50，累计=50
```

The internal structured result is not printed twice. Read it with:

```bash
autojoinquant status main --json
```

A run succeeds only after real page evidence such as a success message, an already-checked-in state, reward text, or a disabled check-in control. Incomplete point extraction exits with code `4`; do not retry automatically.

### `status`

`status` checks the platform, Node, browser, Python solver, credential completeness, actual timer state, and last point result. It does not open a browser or visit JoinQuant.

```bash
autojoinquant status
autojoinquant status main
autojoinquant status --json
```

### `schedule`

Each account can use an independent time:

```bash
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

Platform artifacts:

- macOS: `~/Library/LaunchAgents/io.github.autojoinquant.checkin.<hash>.plist`
- systemd user: `~/.config/systemd/user/autojoinquant-<hash>.{service,timer}`
- cron: one `AUTOJOINQUANT <hash>` managed block per account

macOS and cron logs live under `~/.local/state/autojoinquant/users/<hash>/`; inspect systemd logs with `journalctl --user`.

## Uninstall

Remove every account timer before uninstalling:

```bash
autojoinquant config list
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

For Nix, locate the entry with `nix profile list`, then run `nix profile remove <name>`. Uninstalling the command does not remove `~/.config/autojoinquant`, browser profiles, or result history.

Current version: `v0.3.0`. Run `autojoinquant --version` to inspect the installed version. See [CHANGELOG.md](CHANGELOG.md), [SECURITY.md](SECURITY.md), and [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
