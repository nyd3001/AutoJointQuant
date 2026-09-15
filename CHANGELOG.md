# Changelog

## Unreleased

- Hid the internal `AUTOJOINQUANT_RESULT` bridge line from normal CLI output; structured data remains available through `status --json`.
- Reworked both READMEs into a concise quick-start and command reference, including uninstall and platform caveats.
- Replaced the single-account interface with an alias-based multi-account registry: `config add/list/edit/remove`, `run <alias>`, `status [alias]`, and `schedule start/remove/status <alias>`.
- Made `run <alias>` execute one check-in by default while preserving an explicit `--dry-run` inspection mode.
- Isolated credential files, Chrome profiles, run state, logs, and scheduler identifiers for every account alias.
- Added interactive schedule questions to `config add` and `config edit`; passwords remain hidden and are never accepted as command arguments.
- Added the installable `autojoinquant` 0.3.0 CLI and platform-native per-account schedules.
- Added secure 0600 credential/config files, hidden password input, runtime discovery, last-result state, and global installs through `uv tool` or `nix profile`.
- Added launchd, systemd user timer, and cron backends with automatic macOS/Linux/NixOS selection.
- Added structured `pointsAwarded`, `pointsAvailable`, and `pointsTotal` results; point balances are read from the credits page after Vue finishes loading.
- Prevented false success when no check-in button or success evidence exists; an ambiguous successful check-in with incomplete point extraction now exits with code 4.
- Switched the default CDP port to automatic allocation, added per-profile run locking, cleaned only verified stale Chrome locks, and retained compatibility with an active legacy port-9223 profile.
- The browser driver now selects only JoinQuant targets and closes only browser processes it started.
- Added macOS/Linux CI, wheel/sdist builds, Nix apps/packages/checks, Node engine metadata, and unit coverage for configuration, runtime selection, and timer rendering.
- Added a CDP-based JoinQuant check-in script with an explicit dry-run/execute boundary.
- Added an image-based slider-gap solver with synthetic-image tests.
- Synchronized the CAPTCHA piece image with the same challenge response and hardened CDP login navigation handling.
- Added cross-platform browser auto-detection and an explicit missing-Chromium installation hint.
- Documented Firefox as unsupported until a WebDriver BiDi backend is implemented.
- Added explicit and Linux auto-detected headless Chromium mode for CLI-only hosts.
- Marked desktop-less Linux/NixOS headless login and CAPTCHA execution as pending real-host validation.
- Added uv locking, a Nix development shell, bilingual documentation, CI, and security guidance.
