# Private Form

A self-hosted Django form for collecting data from people whose records need privacy.

## Features

- **Cookieless public form.** No sessions, no JS. CSRF is a signed hidden-field token. Conditional fieldsets via CSS `:checked` only — degrades to "show everything" if stylesheets fail.
- **Encrypted PII at rest.** Phone + secure-messaging username stored as Fernet. Meaning: no plaintext column, ever.
- **Request-pipeline scrubbing.** Middleware zeroes client IPs on public routes and redacts POST bodies from exception reports. gunicorn + Caddy configured not to log bodies or client IPs.
- **Dead-man switch + remote wipe.** Configurable inactivity thresholds auto-wipe the database; a single-use webhook token wipes on demand when SSH is gone. `wipe_data` zeroes encrypted fields, clears history, `VACUUM`s SQLite, destroys the key.
- **Scoped admin via proxy models + Django groups.** Volunteers see only their request subset.
- **i18n.** Two languages, routes are `/<lang>/form/`. No `Accept-Language` sniffing (fingerprinting).

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.13 |
| Framework | Django 5.2 LTS |
| DB | SQLite (WAL mode) |
| Templates | Django templates + Pico CSS, zero JS on the public form |
| WSGI | gunicorn (3 sync workers) |
| Reverse proxy | Caddy 2 (auto-HTTPS via Let's Encrypt) |
| Containers | Podman Compose, rootless |
| Deps | `uv` |

## Deployment

Single VPS, rootless Podman pod: Caddy -> gunicorn -> SQLite. Secrets in `/run/secrets/`. systemd timers on the host run the dead-man check and SQLite backups.

VPS provisioning is scripted: `deploy/cloud-init.yml` handles first-boot hardening, `deploy/remote-setup.sh` is a checkpointed orchestrator.

## Docs

- [`docs/dev-onboarding.md`](docs/dev-onboarding.md) : project layout
- [`docs/local-setup.md`](docs/local-setup.md) : run it locally
- [`docs/remote-setup.md`](docs/remote-setup.md) : deploy to a VPS
- [`docs/usage.md`](docs/usage.md) : operate a running instance