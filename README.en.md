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

# Preview check-in and reading puzzles after login: one wrong drag per stage
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

Run `--dry-run` before first use or after environment changes. After login it previews check-in, then reading: visit an article, open its reward CAPTCHA, calculate the gap, and drag once at least 64px away without attempting to pass. Already-completed tasks are skipped. A login CAPTCHA preview stops before either task; any failure stops without retry. Preview visits pages and clicks buttons, cannot guarantee unchanged site state, and never overwrites real-run history. Use `autojoinquant <command> --help` for all options.

`run` (including scheduled runs) picks a random community article, avoids the previous title when possible, stays **45–90 seconds** after content loads, and claims the reading reward. A locally recorded completion skips today's task; pending rewards need no new visit. Check-in and reading points are reported separately. Preview uses the same random browsing flow; set `JOINQUANT_READING_MIN_MS` / `JOINQUANT_READING_MAX_MS` to change the interval.

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
