# AutoJointQuant

[中文 README](README.md)

AutoJointQuant is an installable, schedulable CLI for JoinQuant's daily check-in. It controls a dedicated Chrome/Chromium profile through the Chrome DevTools Protocol. A local Python matcher locates the puzzle gap, and the program performs the slider action over CDP—Computer Use is never involved.

The scope is intentionally narrow: daily check-in only. It does not claim other tasks, browse articles, redeem points, or change account settings.

## Command map

| Command | Mutates site state | Purpose |
| --- | --- | --- |
| `autojoinquant init --time 09:00` | Yes | Prompt securely for credentials, detect the host, and install a daily timer |
| `autojoinquant run` | No | Dry-run by default; never logs in, checks in, or moves the slider |
| `autojoinquant run --execute` | Yes | Perform one login/CAPTCHA/check-in workflow |
| `autojoinquant diagnose` | No | Validate Node, browser, Python, and config without visiting JoinQuant |
| `autojoinquant status` | No | Show timer state and the last points result without credentials |
| `autojoinquant schedule install --time 08:30` | Yes | Install or update the daily timer |
| `autojoinquant schedule remove` | Yes | Remove only this project's managed timer |

## Install a global command

### uv on macOS or general Linux

Python 3.10+, uv, Node.js 22+, and Chrome/Chromium are required:

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
autojoinquant diagnose
```

Upgrade from the current checkout with `uv tool install --force .`.

The CLI searches every `PATH` entry, skips old Node installations, and selects the first Node.js 22+ runtime. `JOINQUANT_NODE_BIN` can override detection. This handles macOS machines whose first `node` is old while Homebrew, Conda, or Nix provides a newer one elsewhere.

### Nix and NixOS

The Nix package includes Node.js and all Python solver dependencies. Linux/NixOS builds also include Chromium:

```bash
nix profile install .
autojoinquant diagnose
```

For a temporary run:

```bash
nix run . -- diagnose
```

Use `nix profile install .` for scheduling so the executable remains rooted. On macOS, the Nix package still uses a system-installed Chrome/Chromium.

### Development

```bash
nix develop
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs
```

uv alone is also supported, but it does not install Node or a browser.

## Initialize credentials and schedule

```bash
autojoinquant init --time 09:00
```

`init`:

1. reads the password with hidden input and deliberately has no `--password` option;
2. writes credentials to `~/.config/autojoinquant.env` with mode `0600`;
3. writes the time, Node path, and dedicated profile to `~/.config/autojoinquant/config.json`;
4. performs an offline runtime diagnosis;
5. installs launchd, a systemd user timer, or cron only after diagnosis passes.

Use `--no-schedule` to save configuration without installing a timer. For a non-interactive secret source:

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant init --username "$JOINQUANT_USERNAME" --password-stdin --time 09:00
```

Never put the real password directly in command arguments. The Node driver reads the protected env file itself; `.zprofile` is not required, and sourcing the credential file is discouraged. Existing process variables take precedence over file values.

Direct environment variables remain supported:

```bash
export JOINQUANT_USERNAME='phone number'
export JOINQUANT_PASSWORD='password'
autojoinquant run --execute
```

## Platform selection

| Host | Browser | Scheduler | Behavior |
| --- | --- | --- | --- |
| macOS | Auto-detected system Chrome/Chromium | launchd LaunchAgent | Headed by default; headless can be explicit |
| Linux desktop | Auto-detected Chrome/Chromium | systemd user, then cron fallback | Uses the current X11/Wayland display |
| Headless Linux | Auto-detected Chrome/Chromium | systemd user, then cron fallback | Headless is automatic without DISPLAY/Wayland |
| NixOS | Chromium supplied by the flake | systemd user | CLI-only hosts commonly need user lingering |

For a desktop-less NixOS user service, enable lingering:

```nix
users.users.<name>.linger = true;
```

If Chromium is not supplied by this flake, it can be installed system-wide:

```nix
environment.systemPackages = with pkgs; [ chromium ];
```

`nix develop` and `nix run` export the exact Chromium path automatically; manual `JOINQUANT_CHROME_BIN="$(command -v chromium)"` setup is normally unnecessary.

Firefox is not currently supported. The implementation uses CDP, whereas Firefox requires a separate WebDriver BiDi/Marionette backend; pointing `JOINQUANT_CHROME_BIN` at Firefox cannot work.

## Run and points output

Dry-run after every upgrade:

```bash
autojoinquant run
```

Then perform one controlled execution:

```bash
autojoinquant run --execute
```

The final output contains both a human-readable line and a machine-readable record:

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
AUTOJOINQUANT_RESULT={"status":"checked-in","pointsAwarded":5,"pointsAvailable":55,"pointsTotal":55}
```

- `pointsAwarded`: points added by this check-in; `0` when today was already complete; `null` in dry-run.
- `pointsAvailable`: currently spendable points.
- `pointsTotal`: lifetime points earned.

The CLI records the last structured result at `~/.local/state/autojoinquant/last-run.json`; inspect it with `autojoinquant status`. Success requires real page evidence such as a success message, an already-checked-in control, awarded-points text, or a disabled check-in button. A missing button alone is never considered success.

## Scheduler management

`init` installs the timer by default. It can also be managed separately:

```bash
autojoinquant schedule install --time 08:30
autojoinquant schedule status
autojoinquant schedule remove
```

Managed files:

- macOS: `~/Library/LaunchAgents/io.github.autojoinquant.checkin.plist`;
- systemd user: `~/.config/systemd/user/autojoinquant.{service,timer}`;
- cron: one block marked `AUTOJOINQUANT MANAGED BLOCK`.

macOS logs are under `~/.local/state/autojoinquant/launchd.*.log`; cron uses `~/.local/state/autojoinquant/cron.log`; systemd uses `journalctl --user -u autojoinquant.service`. The machine must be powered on, and a sleeping Mac is not guaranteed to run exactly on time.

## Configuration variables

| Variable | Purpose |
| --- | --- |
| `JOINQUANT_USERNAME` / `JOINQUANT_PASSWORD` | Login credentials |
| `JOINQUANT_ENV_FILE` | Credential file; defaults to `~/.config/autojoinquant.env`; `-` disables it |
| `AUTOJOINQUANT_CONFIG` | CLI settings JSON path |
| `JOINQUANT_NODE_BIN` | Node.js 22+ executable |
| `JOINQUANT_CHROME_BIN` | Chrome/Chromium executable; auto-detected by default |
| `JOINQUANT_PROFILE_DIR` | Dedicated browser profile |
| `JOINQUANT_DEBUG_PORT` | `auto` (default) or a fixed port from 1–65535 |
| `JOINQUANT_HEADLESS` | `1` forces headless; `0` forces a visible browser |
| `JOINQUANT_TIMEOUT_MS` | Page, CDP, and solver timeout; default 15000 |
| `JOINQUANT_PYTHON` | Python with Pillow/numpy/scipy installed |
| `JOINQUANT_UV` | uv executable for direct `checkin.mjs` use |
| `JOINQUANT_ALLOW_NO_SANDBOX` | Explicitly permits `--no-sandbox` as Linux root; discouraged |

An automatically assigned debug port avoids collisions. A still-running dedicated profile from older 9223-based releases is reused safely. Only JoinQuant targets are selected, so ordinary browser tabs are never navigated or overwritten. A per-profile process lock prevents overlapping timer runs.

## Validation status

| Area | Current evidence |
| --- | --- |
| macOS login, puzzle, and real check-in | Successfully exercised on a real account |
| macOS 0.2 diagnosis, dry-run, legacy 9223 reuse, and points reading | Exercised locally; the read-only run returned current available and total points |
| launchd firing at the configured time | Rendering and unit tests pass; the next real timed invocation has not been observed yet |
| Linux | Ubuntu CI covers Python, Node syntax, and packaging; real browser check-in is pending |
| NixOS | All four flake outputs evaluate; real systemd/headless check-in is pending |
| Desktop-less headless login, CAPTCHA, and check-in | Not yet validated on a real host |

A successful package build or flake evaluation is not website acceptance. On a new Linux/NixOS or headless host, run `diagnose`, then dry-run, then supervise the first `--execute`.

## Exit codes

- `0`: dry-run succeeded, or both check-in state and points were confirmed;
- `1`: browser, configuration, or another general runtime error;
- `2`: login is required but credentials are unavailable;
- `3`: login, CAPTCHA, click, or check-in success evidence failed;
- `4`: check-in state was confirmed but points extraction was incomplete. Do not blindly retry an ambiguous external write.

## Repository layout

```text
.
├── src/autojoinquant/       # installable CLI, config, runtime detection, schedulers
├── checkin.mjs              # CDP login, check-in, slider, and points reader
├── captcha_solver.py        # local image-matching solver
├── tests/                   # solver, config, Node discovery, scheduler tests
├── pyproject.toml / uv.lock # uv package and lock
├── flake.nix / flake.lock   # nix run / profile / develop / checks
└── README.md                # Chinese documentation
```

CAPTCHA endpoints and page DOM can change. On failure, the program stops with diagnostics; it never switches to Computer Use or retries indefinitely. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md).

Licensed under MIT. The CAPTCHA layout and points selectors were informed by public page behavior and a [public reference project](https://github.com/youngyunxing/joinquant-auto-skill), but AutoJointQuant does not implement that project's additional points tasks.
