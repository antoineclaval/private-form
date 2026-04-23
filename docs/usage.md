# Operations

Day-to-day and break-glass operations on a running production instance. For the initial VPS build, see [`remote-setup.md`](remote-setup.md).

Most commands run inside the web container:

```bash
podman exec -it mutual-aid-web-1 python manage.py <command>
```

## Import existing CSV data

One-time import from a legacy system.

```bash
# From your local machine
scp "my-datas.csv" user@vps:/tmp/import.csv

# On the VPS
podman exec mutual-aid-web-1 python manage.py import_airtable /tmp/import.csv --dry-run
podman exec mutual-aid-web-1 python manage.py import_airtable /tmp/import.csv
rm /tmp/import.csv
```

## Configure the dead man switch

1. Log into the admin → **Security Configuration** → Add.
2. Enable the dead man switch.
3. Set the warn threshold (e.g. 7 days) and the wipe threshold (e.g. 14 days).

The `mutual-aid-deadman.timer` installed during setup runs `check_deadman` every 12 h against these thresholds.

## Remote wipe token

Generates a token that can trigger `wipe_data` via HTTP when SSH is unavailable.

```bash
podman exec mutual-aid-web-1 python manage.py generate_wipe_token
```

The command prints the token (use it) and a hash (store it). Put the **hash** into Security Configuration → Remote Wipe Token Hash. Keep the **token** somewhere offline.

To trigger:

```bash
curl -X POST https://yourdomain.org/security/wipe/YOUR_TOKEN_HERE/
```

Tokens are single-use and time-limited. Regenerate periodically.

## Admin MFA

Every volunteer must enrol TOTP before doing real work.

1. Log in at `https://yourdomain.org/account/login/`.
2. **Account Security → Enable TOTP.**
3. Scan the QR code with an authenticator (Aegis, Raivo, …).

Superusers can enforce MFA for all staff through the admin.

## Volunteer accounts and scoped access

Create a user:

```bash
podman exec -it mutual-aid-web-1 python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.create_user('volunteer1', password='changeme123!')
u.is_staff = True
u.save()
"
```

Then in admin → **Groups**, assign the user to exactly one of:

- **Food Volunteers** — permissions on `FoodRequest` (proxy model, food/supply rows only)
- **Dispatch Volunteers** — permissions on `TransportRequest` (proxy model, ride rows only)
- **Full Admin** — permissions on `AidRequest` (everything)

For CSV export of PII, grant the `requests_app | aid request | Can export records with PII` permission individually to trusted users only. Every PII export is logged.

## Encryption key rotation

1. Generate a new Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
2. Prepend it to `secrets/encryption_keys.txt` (comma-separated, newest first).
3. `podman compose restart web`.
4. `podman exec mutual-aid-web-1 python manage.py rotate_encryption` — re-encrypts every row with the new key.
5. Remove the old key from `secrets/encryption_keys.txt`.
6. `podman compose restart web` again.

## Updating the application

```bash
cd /opt/mutual-aid
git pull
podman compose build
podman compose up -d      # rolling restart; Caddy stays up
```

Migrations run from the entrypoint on container start.

## Emergency migration ("grab and run")

Entire state = `db.sqlite3` + three secret files + the git repo.

```bash
# From your LOCAL machine
sh deploy/emergency_migrate.sh user@new-vps-ip /opt/mutual-aid
```

On the new VPS:

```bash
cd /opt/mutual-aid
nano .env              # update ALLOWED_HOSTS if domain changed
nano Caddyfile         # update domain if changed
podman compose up -d
```

Update DNS to point to the new VPS IP, then destroy the old VPS.

## Emergency data wipe

### With SSH

```bash
podman exec mutual-aid-web-1 python manage.py wipe_data --confirm
```

### Without SSH (remote wipe webhook)

```bash
curl -X POST https://yourdomain.org/security/wipe/YOUR_OFFLINE_TOKEN/
```

Either path zeroes encrypted fields, clears free-text fields, deletes history records, `VACUUM`s SQLite, and destroys the encryption key. Combined with LUKS, the data is unrecoverable.

## Monitoring

```bash
podman compose ps
podman compose logs web --tail 50

systemctl status mutual-aid-deadman.timer
systemctl status mutual-aid-backup.timer
journalctl -u mutual-aid-deadman.service -n 20
```
