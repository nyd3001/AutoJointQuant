# AutoJointQuant

[中文](README.md)

A multi-account CLI for JoinQuant's daily check-in. It uses a dedicated Chrome/Chromium profile and CDP to log in, solve the puzzle, and move the slider without Computer Use. It does not claim other tasks or modify account settings.

## Quick start

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/), Node.js 22+, and Chrome/Chromium.

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .

autojoinquant config add main
autojoinquant run main --dry-run  # Preview first
autojoinquant run main            # Perform one check-in
autojoinquant status main         # Environment, timer, and points
```

`config add` prompts for a password without echo, then asks whether to schedule the account and at what time. Passwords are never accepted as command arguments.

## Commands

| Command | Purpose |
| --- | --- |
| `config add <alias>` | Add an account and optionally schedule it |
| `config list` | List aliases, masked usernames, and schedules |
| `config edit <alias>` | Edit credentials or schedule settings |
| `config remove <alias>` | Remove the account, credentials, and timer; retain profile and history |
| `run <alias>` | Perform one real check-in |
| `run <alias> --dry-run` | Inspect the page without login, check-in, or slider movement |
| `status [alias]` | Check Node, browser, solver, accounts, timers, and points |
| `schedule start <alias> --time HH:MM` | Install or update a timer |
| `schedule remove <alias>` | Remove that account's timer |

Examples:

```bash
autojoinquant config list
autojoinquant config edit main
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

`run <alias>` changes website state by default. Use `--dry-run` after upgrades, on a new host, or while investigating page changes.

## Install and uninstall

Update a uv installation:

```bash
uv tool install --force .
```

The Nix/NixOS package includes Node and Python dependencies, plus Chromium on Linux:

```bash
nix profile install .
nix run . -- status       # Temporary run
```

Scheduled jobs should use a globally installed command from `uv tool install` or `nix profile install`. Remove account timers before uninstalling the uv version:

```bash
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

Uninstalling the command does not delete account configuration or Chrome profiles.

## Accounts and security

Every alias has isolated credentials, browser profile, result state, and scheduler:

```text
~/.config/autojoinquant/config.json
~/.config/autojoinquant/users/<account-hash>.env
~/.local/share/autojoinquant/profiles/<account-hash>/
~/.local/state/autojoinquant/users/<account-hash>/last-run.json
```

- Registry and credential files use mode `0600`; passwords are hidden and usernames are masked.
- Never commit credentials, `.env` files, logs, or Chrome profiles.
- `config remove` retains the profile and history to avoid accidental browser-data loss.
- Version 0.3 does not migrate the 0.2 single-account config. Back it up first:

```bash
mv ~/.config/autojoinquant/config.json ~/.config/autojoinquant/config.v1.backup.json
```

Then run `autojoinquant config add <alias>`. The old `~/.config/autojoinquant.env` is not loaded automatically.

For non-interactive setup, pass one password line through stdin:

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main --username "$JOINQUANT_USERNAME" \
  --password-stdin --schedule --time 09:00
```

## Point results

Successful output includes awarded, available, and lifetime points:

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
AUTOJOINQUANT_RESULT={"status":"checked-in","pointsAwarded":5,"pointsAvailable":55,"pointsTotal":55}
```

Results are stored per account and shown by `autojoinquant status <alias>`. A run succeeds only with real page evidence. Incomplete point extraction exits with code `4`; do not retry automatically.

## Platforms

| Platform | Browser | Scheduler | Validation |
| --- | --- | --- | --- |
| macOS | System Chrome/Chromium | launchd | Login, puzzle, check-in, and points validated live |
| Linux desktop | Chrome/Chromium | systemd user or cron | CI/package checks pass; live check-in pending |
| Headless Linux/NixOS | Automatic headless Chromium | systemd user or cron | Not yet validated live |

CLI-only NixOS hosts usually need:

```nix
users.users.<name>.linger = true;
```

Firefox is not supported. Chrome/Chromium is auto-detected; override it with `JOINQUANT_CHROME_BIN` when needed. Other useful overrides are `JOINQUANT_NODE_BIN`, `JOINQUANT_HEADLESS`, `JOINQUANT_TIMEOUT_MS`, and `AUTOJOINQUANT_CONFIG`.

## Development

```bash
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs  # Requires Node.js 22+

# Or use the complete Nix environment
nix develop
nix flake check
```

See [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [CHANGELOG.md](CHANGELOG.md). Licensed under MIT.
