# Contributing

Thanks for helping improve AutoJointQuant.

## Development setup

Use either workflow:

```bash
uv sync
uv run pytest
uv run ruff check .
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

- Keep the default dry-run behavior intact.
- Do not add credentials, cookies, CAPTCHA images, or browser profiles to commits.
- Update both `README.md` and `README.en.md` when user-facing behavior changes.
- Add or update tests for solver and parsing changes.
- Keep launchd, systemd, cron, uv-tool, and Nix-package behavior aligned when changing CLI paths.
- Do not claim live JoinQuant success without a controlled verification record.

## Live testing

Live execution changes an external account state and must not run in CI. Use a dedicated Chrome profile, review the diff first, and run `node checkin.mjs --execute` only when you are ready to perform one real check-in.
