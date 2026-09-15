<div align="center">
  <h1>AutoJointQuant</h1>
  <p>Automated multi-account JoinQuant check-in with scheduling, puzzle solving, and point reporting—without Computer Use.</p>
  <p><strong>macOS:</strong> verified · <strong>Linux/NixOS:</strong> pending · <strong>Browser:</strong> Chrome/Chromium</p>
  <p>
    <a href="https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg"></a>
    <a href="CHANGELOG.md"><img alt="Version 0.3.0" src="https://img.shields.io/badge/version-0.3.0-blue.svg"></a>
    <a href="LICENSE"><img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
  </p>
  <p><a href="README.md">中文</a></p>
</div>

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
# Add an account; follow the prompts for credentials and scheduling
autojoinquant config add main

# Preview, check in, and inspect status
autojoinquant run main --dry-run
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

<div align="center">
  <a href="CHANGELOG.md">Changelog</a> · <a href="SECURITY.md">Security</a> · <a href="CONTRIBUTING.md">Contributing</a> · <a href="LICENSE">MIT License</a>
</div>
