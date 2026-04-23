# Local Setup

For development on a workstation. Two paths: plain `uv` (fastest feedback loop) or `podman compose` (closer to production).

## Prerequisites

- Fedora Silverblue users: all commands run inside `toolbox enter private-form`
- [`uv`](https://docs.astral.sh/uv/) for Python dependency management
- Python 3.13 (uv will bootstrap it if missing)
- For the containerised path: `podman` and `podman-compose`

## Path A — direct with `uv` (no containers)

This uses `mutual_aid/settings/development.py`, which ships with a hardcoded dev secret, a dev Fernet key, and `data/dev.sqlite3`. No secret files are needed.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Form: <http://localhost:8000/> (language-prefixed routes) · Admin: <http://localhost:8000/admin/>

Useful variants:

```bash
uv run python manage.py test requests_app.tests      # run app tests
uv run ruff format . && uv run ruff check .          # format + lint
uv run python manage.py check --deploy               # production settings audit
```

If `python manage.py …` raises `ModuleNotFoundError: django`, the system Python is being used instead of the venv. Either prefix commands with `uv run`, or `source .venv/bin/activate` once per shell.

## Path B — `podman compose` (production-shaped)

Mirrors the VPS layout (Caddy → gunicorn, Podman secrets, SQLite volume). Use this before shipping changes that touch the container build, entrypoint, Caddy config, or production settings.

```bash
# 1. Generate local secrets (writes secrets/ — gitignored)
sh deploy/setup_secrets.sh

# 2. Create .env with a hostname Django will accept
cp .env.example .env
# edit .env: ALLOWED_HOSTS=localhost,127.0.0.1

# 3. Build and start
podman compose build
podman compose up -d

# 4. One-time: create an admin user
podman exec -it mutual-aid-web-1 python manage.py createsuperuser
```

Caddy will attempt to obtain a certificate — for local use, edit `Caddyfile` to serve on `:80` plainly or use `localhost` (Caddy issues a local self-signed cert automatically).

Tear down with `podman compose down`; add `-v` to also drop the SQLite + static volumes.

## Data directory

Development DB lives at `data/dev.sqlite3` (Path A) or inside the `db_data` volume (Path B). Both are gitignored. No real CSV export should ever be placed inside the repo — see `.gitignore` (`*.csv`).
