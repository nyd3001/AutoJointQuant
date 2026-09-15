# Changelog

## Unreleased

- Added the installable `autojoinquant` 0.2.0 CLI with `init`, `run`, `diagnose`, `status`, and platform-native `schedule` commands.
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
