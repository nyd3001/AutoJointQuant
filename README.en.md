# AutoJointQuant

[中文说明](README.md)

AutoJointQuant is a globally installable, multi-account CLI for JoinQuant's daily check-in. Each local account alias has its own protected credentials, Chrome/Chromium profile, last result, logs, and timer.

The browser workflow uses the Chrome DevTools Protocol. A local Python image-matching solver locates the puzzle gap, and the program moves the slider through CDP. Computer Use is never part of the check-in path.

The project is deliberately limited to the daily check-in. It does not claim other tasks, browse articles, redeem points, or change account settings.

## Command model

```text
config add/list/edit/remove   Manage local account aliases
run <alias>                   Perform one check-in now
status [alias]                Check the environment, accounts, timers, and results
schedule start/remove/status  Manage one account's timer
```

| Command | Website state | Purpose |
| --- | --- | --- |
| `autojoinquant config add main` | Unchanged | Add an alias, username, password, and optional daily schedule |
| `autojoinquant config list` | Not accessed | List aliases, masked usernames, and schedule settings |
| `autojoinquant config edit main` | Unchanged | Edit credentials or schedule settings |
| `autojoinquant config remove main` | Not accessed | Remove the registry entry, credentials, and timer; retain profile and history |
| `autojoinquant run main` | Changed | Perform one login, CAPTCHA, and check-in for `main` |
| `autojoinquant run main --dry-run` | Unchanged | Inspect page state without login, CAPTCHA, or check-in |
| `autojoinquant status` | Not accessed | Check the environment and report all accounts, timers, and last results |
| `autojoinquant status main` | Not accessed | Report only `main` |
| `autojoinquant schedule start main --time 08:30` | Not accessed | Diagnose and install or update `main`'s timer |
| `autojoinquant schedule remove main` | Not accessed | Remove only `main`'s timer |

`run <alias>` performs a real check-in by default because both the action and account are explicit. After an upgrade, on a new host, or while investigating a page change, run `run <alias> --dry-run` first.

## Global installation

### uv on macOS or general Linux

Install Python 3.10+, uv, Node.js 22+, and Chrome or Chromium:

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
autojoinquant status
```

Upgrade from the current checkout with:

```bash
uv tool install --force .
```

The CLI searches every `PATH` entry, skips old Node versions, and chooses the first Node.js 22+ runtime. `JOINQUANT_NODE_BIN` can override discovery.

### Nix and NixOS

The Nix package includes Node.js and the Python solver dependencies. Linux/NixOS builds also include Chromium:

```bash
nix profile install .
autojoinquant status
```

Temporary use is also available:

```bash
nix run . -- status
```

Use `nix profile install .` for scheduled jobs so they do not depend on a temporary `nix run` store path that may be garbage-collected. The macOS Nix package uses a system Chrome/Chromium installation.

### Development

```bash
nix develop
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs
```

## Account management

The simplest setup command is:

```bash
autojoinquant config add main
```

It prompts for:

1. the JoinQuant username;
2. the JoinQuant password, without terminal echo;
3. whether daily automatic check-in is required;
4. the daily local time when enabled.

There is deliberately no `--password` argument, keeping secrets out of shell history, process listings, and scheduler files. Non-interactive environments can supply one password line through standard input:

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main \
    --username "$JOINQUANT_USERNAME" \
    --password-stdin \
    --schedule \
    --time 09:00
```

List or edit accounts:

```bash
autojoinquant config list
autojoinquant config list --json
autojoinquant config edit main
```

During interactive editing, Enter keeps the current username or password. Remove an account with:

```bash
autojoinquant config remove main
```

Removal requires confirmation and deletes the registry entry, protected credential file, and corresponding timer. The isolated browser profile and historical result are retained to avoid irreversible data loss; their paths are printed.

## Isolation and storage

The default registry is:

```text
~/.config/autojoinquant/config.json
```

Each alias maps to a stable hash that does not reveal its username:

```text
~/.config/autojoinquant/users/<account-hash>.env
~/.local/share/autojoinquant/profiles/<account-hash>/
~/.local/state/autojoinquant/users/<account-hash>/last-run.json
```

The registry and credential files use mode `0600`. `config list` and `status` mask usernames; passwords are never printed. When running a named account, the CLI removes inherited `JOINQUANT_USERNAME` and `JOINQUANT_PASSWORD` values so another shell account cannot be used accidentally.

Version 0.3 uses a new registry and does not automatically migrate the 0.2 single-account `config.json`. Back up an old file before adding aliases:

```bash
mv ~/.config/autojoinquant/config.json ~/.config/autojoinquant/config.v1.backup.json
autojoinquant config add main
```

The old `~/.config/autojoinquant.env` is not read automatically by new accounts.

## Check-in and point results

Inspect a first or upgraded run safely:

```bash
autojoinquant run main --dry-run
```

Then perform one check-in:

```bash
autojoinquant run main
```

Successful output includes:

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
AUTOJOINQUANT_RESULT={"status":"checked-in","pointsAwarded":5,"pointsAvailable":55,"pointsTotal":55}
```

- `pointsAwarded`: added by this run; `0` when already checked in; `null` for a dry-run.
- `pointsAvailable`: current spendable points.
- `pointsTotal`: lifetime points earned.

Results are stored per account and reported by `autojoinquant status main`. Success requires real page evidence such as a success message, an already-checked-in control, awarded-points text, or a disabled check-in control. A missing button alone is not success.

## Status and scheduling

`status` does not open a browser, visit JoinQuant, or check in:

```bash
autojoinquant status
autojoinquant status main
autojoinquant status --json
```

It checks the platform, Node.js 22+, Chrome/Chromium, Python solver, credential completeness, actual scheduler state, and the last point result.

Each account can use a separate time:

```bash
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

Platform artifacts use the account hash:

- macOS: `~/Library/LaunchAgents/io.github.autojoinquant.checkin.<account-hash>.plist`;
- systemd user: `~/.config/systemd/user/autojoinquant-<account-hash>.{service,timer}`;
- cron: one `AUTOJOINQUANT <account-hash>` managed block per account.

## Platform selection

| Host | Browser | Scheduler | Behavior |
| --- | --- | --- | --- |
| macOS | System Chrome/Chromium discovery | launchd LaunchAgent | Visible browser unless headless is requested |
| Linux desktop | Chrome/Chromium discovery | systemd user, then cron | Uses DISPLAY or Wayland |
| CLI-only Linux | Chrome/Chromium discovery | systemd user, then cron | Enables headless automatically without a display |
| NixOS | Chromium included by the flake | systemd user | CLI-only hosts usually need user lingering |

NixOS can enable lingering declaratively:

```nix
users.users.<name>.linger = true;
```

When the project flake is not used, install Chromium system-wide with:

```nix
environment.systemPackages = with pkgs; [ chromium ];
```

`nix develop`, `nix run`, and the Nix package set the Linux Chromium path automatically. A manual `JOINQUANT_CHROME_BIN` export is normally unnecessary.

Firefox is not supported. This implementation uses CDP; Firefox requires a separate WebDriver BiDi or Marionette backend.

## Advanced environment overrides

The registry controls account credentials, profile paths, and state. These variables are for runtime overrides:

| Variable | Purpose |
| --- | --- |
| `AUTOJOINQUANT_CONFIG` | Select another account registry |
| `JOINQUANT_NODE_BIN` | Node.js 22+ executable |
| `JOINQUANT_CHROME_BIN` | Chrome/Chromium executable; normally auto-detected |
| `JOINQUANT_DEBUG_PORT` | `auto` by default, or a fixed port from 1 to 65535 |
| `JOINQUANT_HEADLESS` | `1` forces headless; `0` forces a visible browser |
| `JOINQUANT_TIMEOUT_MS` | Page, CDP, and solver timeout; default 15000 |
| `JOINQUANT_PYTHON` | Python with Pillow, NumPy, and SciPy |
| `JOINQUANT_UV` | uv used only when directly running the internal `checkin.mjs` |
| `JOINQUANT_ALLOW_NO_SANDBOX` | Explicitly allow `--no-sandbox` as Linux root; not recommended |

The debugging port is allocated automatically. The program only selects JoinQuant tabs and never navigates normal browser tabs. Each account profile has its own process lock to prevent overlapping timer runs.

## Validation status

| Item | Current evidence |
| --- | --- |
| macOS login, puzzle, and real check-in | Successfully validated on a real host |
| macOS diagnosis, dry-run, legacy port 9223 handling, and point reading | Validated on a real host |
| Multi-account CLI and per-account schedulers | Unit/static/safe-preview coverage; new real timers not installed yet |
| Linux | Ubuntu CI covers Python, Node, and packaging; real browser check-in pending |
| NixOS | Flake supports four platforms; real systemd/headless check-in pending |
| CLI-only headless login, puzzle, and check-in | Not yet validated on a real host |

A successful package build is not a live website acceptance test. On Linux, NixOS, or a headless host, run `status`, then `run <alias> --dry-run`, and supervise the first `run <alias>`.

## Exit codes

- `0`: successful status/dry-run, or confirmed check-in and points;
- `1`: browser, runtime, or ordinary automation failure;
- `2`: CLI configuration error, or credentials missing when login is required;
- `3`: login, CAPTCHA, click, or success-evidence failure;
- `4`: check-in state confirmed but point extraction incomplete; do not retry automatically.

JoinQuant may change its CAPTCHA API or DOM. Failures stop with a clear error; the program does not switch to Computer Use or retry forever. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md).

This project uses the MIT License. CAPTCHA layout and point selectors were informed by public page behavior and a [public reference project](https://github.com/youngyunxing/joinquant-auto-skill), while this project remains limited to daily check-in.
