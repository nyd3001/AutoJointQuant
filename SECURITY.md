# Security Policy

## Reporting a vulnerability

Please do not open a public issue for credential leaks, authentication bypasses, or unintended account actions. Contact the repository owner privately with a minimal reproduction and the affected commit.

## Credential handling

- Never commit `.env`, passwords, cookies, tokens, or a Chrome profile.
- Prefer `autojoinquant init`, which uses hidden password input and writes `~/.config/autojoinquant.env` with mode `0600`.
- Do not pass passwords as command arguments or source the credential file into an interactive shell. A short-lived environment or secret-manager pipe to `--password-stdin` is also supported.
- The script intentionally does not export or print cookies, passwords, or CAPTCHA image data.

The Chrome remote-debugging endpoint is bound to loopback and always uses a dedicated profile. Never point `JOINQUANT_PROFILE_DIR` at a normal daily-browser profile.

## Scope

The project is intended for the user's own JoinQuant account and daily check-in only. Do not use it to access another person's account or to bypass account controls.

Running Chromium as root is rejected by default. `JOINQUANT_ALLOW_NO_SANDBOX=1` exists only for controlled containers and weakens browser isolation.
