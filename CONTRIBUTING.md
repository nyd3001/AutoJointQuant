# Contributing

Thanks for helping improve AutoJointQuant.

## Development setup

Use either workflow:

```bash
uv sync
uv run pytest
uv run ruff check .
node --test tests/*.test.mjs
uv build
```

or:

```bash
nix develop
uv sync
uv run pytest
nix flake check
```

## Pull requests

- Keep `run <alias> --dry-run` limited to login and one deliberately offset CAPTCHA drag, with no correct-drag retry. It may stop at a login CAPTCHA before reaching check-in.
- Keep credentials, Chrome profiles, state, logs, and scheduler identifiers isolated by alias.
- Do not add credentials, cookies, CAPTCHA images, or browser profiles to commits.
- Update both `README.md` and `README.en.md` when user-facing behavior changes.
- Add or update tests for solver and parsing changes.
- Keep launchd, systemd, cron, uv-tool, and Nix-package behavior aligned when changing CLI paths.
- Do not claim live JoinQuant success without a controlled verification record.

## Live testing

Live execution changes an external account state and must not run in CI. Use a dedicated account alias, review the diff, run `autojoinquant run <alias> --dry-run`, and execute `autojoinquant run <alias>` only when ready for one real check-in.
