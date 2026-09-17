<h1 align="center">AutoJointQuant</h1>
<p align="center">Automated multi-account JoinQuant check-in with scheduling, puzzle solving, and point reporting—without Computer Use.</p>
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

# Check in and inspect status
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

For slow pages, increase the wait: `JOINQUANT_PAGE_READY_TIMEOUT_MS=90000 autojoinquant run main --dry-run`

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
