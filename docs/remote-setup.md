# Remote Setup (VPS)

One-time provisioning for a production VPS. Operations after the server is live are documented in [`usage.md`](usage.md).

## Requirements

- VPS at a provider that matches your threat model (jurisdiction, data-request policy)
- Provider must allow LUKS full-disk encryption on the root volume
- Debian or Ubuntu (the setup script targets `apt`)
- A domain with a DNS record pointing at the VPS IP

## 1. LUKS (before any data lands on the VPS)

This is the one step nothing else can replace. Most providers allow booting a rescue image and encrypting the root volume from there. Hetzner example:

```bash
cryptsetup luksFormat /dev/sda
cryptsetup luksOpen /dev/sda cryptroot
mkfs.ext4 /dev/mapper/cryptroot
# ... install OS ...
```

Without LUKS, `wipe_data` and `VACUUM` do not guarantee secure deletion on SSDs — flash wear-levelling keeps old data around. `deploy/remote-setup.sh` verifies a LUKS mapping exists and refuses to continue without an explicit override.

## 2. Provision the VPS

Two paths. Pick one.

### Path A — cloud-init (recommended)

1. Edit `deploy/cloud-init.yml` and replace `<REPO_URL>` with the repo's clone URL.
2. Paste the file into the "user data" / "cloud-init" field when creating the VPS. The provider will run it on first boot.
3. Point your domain's A/AAAA record at the new VPS IP. Caddy needs DNS to resolve publicly before it can issue a Let's Encrypt cert.
4. `ssh deploy@<vps-ip>` (the user is created by cloud-init; your SSH key is copied across from root).
5. `cd /opt/mutual-aid && sudo ./deploy/remote-setup.sh`

Cloud-init handles packages, firewall, fail2ban, sysctl hardening, and auto-updates, then pre-marks those steps in `.remote_setup_state`. When `remote-setup.sh` runs it resumes at the interactive steps (LUKS check, `.env`, `Caddyfile`, secrets, DNS, build, timers).

### Path B — manual (no cloud-init)

1. Create the VPS, point DNS at it, `ssh root@<vps-ip>`.
2. `git clone <REPO_URL> /opt/mutual-aid && cd /opt/mutual-aid`
3. `./deploy/remote-setup.sh` — runs all steps from scratch. You must run it as root (or via sudo).

## 3. What `remote-setup.sh` does

The script is checkpointed — progress lives in `.remote_setup_state`. If a step fails, fix the issue and re-run; completed steps skip. Reset with `rm .remote_setup_state`.

| # | step | what happens |
|---|------|--------------|
| 1 | `system_deps` | `apt install` podman, podman-compose, git, sqlite3, age, ufw, fail2ban, unattended-upgrades, … |
| 2 | `luks_verify` | Aborts unless `lsblk` shows a crypt mapping, or you type the override |
| 3 | `swap_disable` | `swapoff -a`, comment `swap` entries in `/etc/fstab` |
| 4 | `firewall` | ufw allow 22/80/443 + podman bridge rules, enable |
| 5 | `fail2ban` | SSH jail (ban after 3 attempts / 1h) |
| 6 | `sysctl_harden` | SYN cookies, ICMP hardening, rp_filter, log_martians, `vm.swappiness=0` |
| 7 | `auto_updates` | unattended-upgrades on, **auto-reboot off** (containers don't survive reboot without re-mounting secrets) |
| 8 | `env` | Opens `.env` in `$EDITOR`; asserts `ALLOWED_HOSTS` is set |
| 9 | `caddy_config` | Substitutes the domain (first entry in `ALLOWED_HOSTS`) into `Caddyfile` |
| 10 | `secrets` | Runs `deploy/setup_secrets.sh`. **Pauses so you can copy `secrets/encryption_keys.txt` offline — losing it destroys all encrypted PII permanently.** Skipped if secrets already exist |
| 11 | `dns_verify` | Confirms `$DOMAIN` resolves to this server's IP before we burn Let's Encrypt rate limits |
| 12 | `build` | `podman compose build` |
| 13 | `start` | `podman compose up -d` (migrations run from the entrypoint) |
| 14 | `timers` | Installs + enables `mutual-aid-deadman.timer` and `mutual-aid-backup.timer` |
| 15 | `verify` | Polls `https://$DOMAIN/` for up to 60s |

Not automated:

- **LUKS configuration** — must be done in rescue mode before the OS is installed.
- **SSH hardening** — disabling password auth is left to the operator; it's too easy to lock yourself out during automated setup.
- **Admin MFA + volunteer accounts + superuser** — interactive, see [`usage.md`](usage.md).
- **`age` keypair for encrypted backups** — generate offline, keep the private key off the server. Write the public key to `/opt/mutual-aid/backup_pubkey.txt`.

## 4. First login

```bash
podman exec -it mutual-aid-web-1 python manage.py createsuperuser
```

Then follow [`usage.md`](usage.md) for MFA enrolment, configuring the dead man switch, generating a remote-wipe token, and onboarding volunteers.
