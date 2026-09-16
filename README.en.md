<h1 align="center">AutoJointQuant</h1>
<p align="center">Automated multi-account JoinQuant check-in with scheduling, puzzle solving, and point reporting—without Computer Use.</p>
<p align="center"><strong>macOS:</strong> verified · <strong>Linux/NixOS:</strong> pending · <strong>Browser:</strong> Chrome/Chromium</p>
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

# Log in, open, and parse the puzzle (no slider drag or check-in)
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

Run `--dry-run` before first use or after environment changes. Use `autojoinquant <command> --help` for all options.

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
