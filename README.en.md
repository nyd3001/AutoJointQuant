<h1 align="center">AutoJointQuant</h1>
<p align="center">Multi-account JoinQuant check-in and community reading rewards, with scheduling and point reporting—without Computer Use.</p>
<p align="center"><strong>Verified:</strong> macOS · Linux · NixOS · <strong>Browser:</strong> Chrome/Chromium</p>
<p align="center"><a href="README.md">中文</a></p>

## Installation

### Option 1: Nix (recommended)

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
nix profile install .
```

The Nix package includes Node.js and the puzzle-solver dependencies. Linux/NixOS packages also include Chromium.

### Option 2: uv

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
```

The uv installation requires Python 3.10+, uv, Node.js 22+, and Chrome/Chromium.

## Quick start

```bash
# Add an account; confirm the password when prompted
autojoinquant config add main

# Parse the puzzle, drag away from the solved position, and stop
autojoinquant run main --dry-run

# Check in, read a random article, claim points, and inspect status
autojoinquant run main
autojoinquant status main

# Manage accounts
autojoinquant config list
autojoinquant config edit main
autojoinquant config remove main

# Manage schedules
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

Run `--dry-run` before first use or after environment changes. Output distinguishes login and check-in puzzles; preview interacts with the site and cannot guarantee unchanged account state. Use `autojoinquant <command> --help` for all options.

`run` (including scheduled runs) picks a random community article, avoids the previous title when possible, stays **45–90 seconds** after content loads, and claims the reading reward. A locally recorded completion skips today's task; pending rewards are claimed without another visit. Check-in and reading points are reported separately. `--dry-run` does not read articles or claim reading rewards. Set `JOINQUANT_READING_MIN_MS` / `JOINQUANT_READING_MAX_MS` to change the interval; waiting does not guarantee rewards, and unconfirmed results fail without automatic retries.

After upgrading, rerun `schedule start <alias>` for existing systemd timers to apply the longer 15-minute execution limit.

For slow pages, set `JOINQUANT_PAGE_READY_TIMEOUT_MS=90000`. Login submission, check-in clicks, puzzle capture, and dragging each wait 0.7–1.3 seconds; `JOINQUANT_ACTION_DELAY_MS=2000` changes this to 1.4–2.6 seconds. Drag duration and step intervals also vary.

## Uninstall

### Nix

```bash
autojoinquant schedule remove main
nix profile remove autojoinquant
```

### uv

```bash
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

Uninstalling does not remove account data or result history.
