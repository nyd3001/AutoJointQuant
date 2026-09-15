# AutoJointQuant

[![CI](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[中文说明](README.md)

AutoJointQuant is a multi-account JoinQuant daily check-in CLI with scheduling. It logs in, solves the puzzle, checks in, and reports points without Computer Use.
It performs only the daily check-in. macOS is validated live; Linux and NixOS are configured but not yet validated on real systems.
Chrome/Chromium is supported; Firefox is not currently supported.

## Installation

Clone the project first:

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
```

### Option 1: Nix (recommended)

```bash
nix profile install .
```

The Nix package includes Node.js and the puzzle-solver dependencies. Linux/NixOS packages also include Chromium.

### Option 2: uv

```bash
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
