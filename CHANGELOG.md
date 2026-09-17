# Changelog

## 0.1.6 - 2026-09-17

- Refuse existing credential files when adding an account, including concurrent creation.
- Test preview offset boundaries, CDP drag events, and stopping without a correct-drag retry.
- Identify login versus check-in CAPTCHA stages in preview results and logs.
- Verify the installed wheel CLI in CI and run JavaScript tests in CI and Nix checks.

## 0.1.5 - 2026-09-16

- Added support for JoinQuant's current `#slideVerifyDragControl` CAPTCHA track and `.valid-code__drag-handle` slider while retaining the legacy selectors.
- Made `--dry-run` verify the complete drag path by deliberately choosing a position far from the solved gap; it never attempts to pass the CAPTCHA or check in.

## 0.1.4 - 2026-09-16

- Waited for the rendered slider geometry before dragging and report a configurable page-load timeout instead of failing immediately.

## 0.1.3 - 2026-09-16

- Extended the CAPTCHA solver timeout to use the bounded page-readiness window, avoiding false failures during cold starts.

## 0.1.2 - 2026-09-16

- Added bounded page-readiness waiting with a configurable `JOINQUANT_PAGE_READY_TIMEOUT_MS`; timeout errors now mention slow networks and the retry setting.

## 0.1.1 - 2026-09-16

- Added interactive password confirmation for `config add` and new passwords in `config edit`; mismatches are rejected before any credential file is written.
- Changed `run <alias> --dry-run` to open the sign-in puzzle, parse it, and stop before slider movement or check-in.

## 0.1.0 - 2026-09-15

- Made `nix develop` self-contained for browser-driver development by providing Node.js 22, uv, Python, and the puzzle solver dependencies, with explicit runtime paths.
- Streamlined both READMEs around installation and everyday CLI usage, with platform validation summarized near the introduction.
- Hid the internal `AUTOJOINQUANT_RESULT` bridge line from normal CLI output; structured data remains available through `status --json`.
- Reworked both READMEs into a concise quick-start and command reference, including uninstall and platform caveats.
- Replaced the single-account interface with an alias-based multi-account registry: `config add/list/edit/remove`, `run <alias>`, `status [alias]`, and `schedule start/remove/status <alias>`.
- Made `run <alias>` execute one check-in by default while preserving an explicit `--dry-run` inspection mode.
- Isolated credential files, Chrome profiles, run state, logs, and scheduler identifiers for every account alias.
- Added interactive schedule questions to `config add` and `config edit`; passwords remain hidden and are never accepted as command arguments.
- Added the installable `autojoinquant` CLI and platform-native per-account schedules.
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
