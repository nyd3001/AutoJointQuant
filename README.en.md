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

## Uninstall

Remove every account timer before uninstalling:

```bash
autojoinquant config list
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

For Nix, locate the entry with `nix profile list`, then run `nix profile remove <name>`. Uninstalling the command does not remove `~/.config/autojoinquant`, browser profiles, or result history.

Current version: `v0.3.0`. Run `autojoinquant --version` to inspect the installed version. See [CHANGELOG.md](CHANGELOG.md), [SECURITY.md](SECURITY.md), and [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
