# Dev Onboarding

Orientation for someone opening this repo for the first time. For how to actually run it, see [`local-setup.md`](local-setup.md).

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.13 |
| Framework | Django 5.2 LTS |
| DB | SQLite (WAL mode) — single file, easy to export/migrate/wipe |
| Templates | Django templates + Pico CSS, zero JS on the public form |
| i18n | Two languages (`LANGUAGE_CODE` default + one alternative), routes are `/<lang>/form/` |
| WSGI | gunicorn (3 sync workers) |
| Reverse proxy | Caddy 2 (auto-HTTPS via Let's Encrypt) |
| Containers | Podman Compose, rootless |
| Deps | `uv` (not pip/poetry) — `pyproject.toml` is the single source of truth |
| Lint / format | `ruff format`, `ruff check`, `shellcheck` for `deploy/*.sh` |

## Top-level layout

```
mutual_aid/        Django project config (settings, urls, wsgi)
requests_app/      Domain app: requests, requesters, form config, public form
security/          Cross-cutting: encryption, middleware, deadman, wipe
templates/         Project-wide templates (base.html, admin overrides)
static/            Pico CSS + custom CSS
deploy/            VPS setup scripts, Containerfile entrypoint, systemd units
docs/              You are here
data/              SQLite file (gitignored)
secrets/           Podman secrets on the VPS (gitignored)
```

## Django apps

| App | Responsibility |
|-----|----------------|
| `mutual_aid` | Project config only. `settings/` split (`base.py`, `development.py`, `production.py`), URL routing, WSGI entrypoint. No models. |
| `requests_app` | The domain. Models (`Requester`, `AidRequest`, `FormConfig`, plus `FoodRequest` / `TransportRequest` proxy models for scoped admin). Admin customization, the public form view, legacy CSV import command. |
| `security` | Everything defensive. Fernet/Argon2id helpers (`encryption.py`), middleware (`PIIScrubMiddleware`, `StripClientIPMiddleware`), `SecurityConfig` model (deadman thresholds, remote wipe token hash), remote-wipe webhook, and the destructive management commands (`wipe_data`, `check_deadman`, `generate_wipe_token`, `rotate_encryption`). |

## Why split this way

`requests_app` is replaceable — a future org could fork the whole repo, swap domain fields, and keep `security` intact. `security` is the part that carries the threat model; it's small and audit-able in isolation. Keeping encryption logic out of model files means one place to review when the crypto story changes.

## Settings split

- `base.py` — shared, includes middleware order (IP stripping early, PII scrub last), CSP, axes, i18n.
- `development.py` — `DEBUG=True`, hardcoded dev secret + Fernet key, `data/dev.sqlite3`. `manage.py` defaults to this.
- `production.py` — reads `DJANGO_SECRET_KEY`, `ENCRYPTION_KEYS`, `PHONE_HASH_SALT`, `ALLOWED_HOSTS` from env (populated from Podman secrets by `deploy/entrypoint.sh`). Enables HSTS, secure cookies, strict CSP.

## Data shape in one paragraph

A `Requester` holds encrypted phone + secure-messaging username and an Argon2id phone hash for dedup lookups. A `Requester` has many `AidRequest`s. An `AidRequest` is a single row with a `request_type` enum and nullable fields for each subtype's data — one wide table rather than polymorphism, because the admin needs cross-type filters and the dataset is small. `FormConfig` is a JSON schema controlling which fields appear on the public form, in what order, with per-language labels.

## Where to read next

- [`implementation.md`](../implementation.md) — original design doc with the full threat model and decision log
- [`local-setup.md`](local-setup.md) — run it locally
- [`remote-setup.md`](remote-setup.md) — deploy it to a VPS
- [`usage.md`](usage.md) — operate a running instance
