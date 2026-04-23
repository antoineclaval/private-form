#!/bin/bash
# Mutual Aid Form — VPS setup orchestrator.
#
# Runs end-to-end production setup: host hardening, secrets, container build,
# systemd timers. Checkpointed via .remote_setup_state — re-run to resume from
# the last failed step. Reset with: rm .remote_setup_state
#
# Target OS: Debian / Ubuntu (apt).
# Usage: sudo ./deploy/remote-setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STATE_FILE="$PROJECT_ROOT/.remote_setup_state"

# Containers, secrets, and repo-file edits must happen as a non-root user so
# rootless podman works (design intent). Prefer $SUDO_USER; fall back to the
# owner of the repo dir (which cloud-init always sets to `deploy`).
TARGET_USER="${SUDO_USER:-$(stat -c '%U' "$PROJECT_ROOT")}"

print_status()  { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error()   { echo -e "${RED}[✗]${NC} $1"; }
print_info()    { echo -e "${BLUE}[i]${NC} $1"; }
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This step requires root. Re-run the script with sudo."
        exit 1
    fi
}

# Run a command as $TARGET_USER via a login shell so the user's XDG_RUNTIME_DIR
# and systemd-user session are set up — required for rootless podman.
run_as_user() {
    sudo --login --user="$TARGET_USER" --preserve-env=EDITOR -- "$@"
}

# -- Checkpoint helpers --------------------------------------------------------

step_done() { [ -f "$STATE_FILE" ] && grep -qxF "$1" "$STATE_FILE"; }
mark_done() { echo "$1" >> "$STATE_FILE"; }

run_step() {
    local num="$1" total="$2" step_id="$3" step_desc="$4" step_fn="$5"
    if step_done "$step_id"; then
        print_info "[$num/$total] $step_desc — already done, skipping"
        return 0
    fi
    echo ""
    echo -e "${BLUE}━━━ [$num/$total] $step_desc ━━━${NC}"
    echo ""
    "$step_fn"
    mark_done "$step_id"
    print_status "[$num/$total] $step_desc — done"
}

# -- Steps ---------------------------------------------------------------------

step_system_deps() {
    require_root
    apt-get update -y
    apt-get upgrade -y
    apt-get install -y \
        podman podman-compose aardvark-dns uidmap passt \
        git sqlite3 age cryptsetup-bin curl \
        ufw fail2ban unattended-upgrades
}

step_luks_verify() {
    # Warn-only: LUKS must be set up at provisioning time; can't enable it live.
    if lsblk -o TYPE 2>/dev/null | grep -qx "crypt"; then
        print_status "LUKS mapping detected on this host"
        return 0
    fi
    print_warning "No LUKS crypt mapping found on this host."
    print_warning "Full-disk encryption is required by the threat model — wipe_data"
    print_warning "and VACUUM do NOT give secure deletion on SSDs without LUKS."
    echo ""
    read -rp "Type 'continue-without-luks' to proceed anyway: " ack
    if [ "$ack" != "continue-without-luks" ]; then
        print_error "Aborting. Reboot into rescue mode and enable LUKS, then re-run."
        exit 1
    fi
    print_warning "Continuing without LUKS — you have been warned."
}

step_swap_disable() {
    require_root
    swapoff -a || true
    # Comment any active swap entries in /etc/fstab so they don't come back on reboot
    sed -i.bak -E 's|^([^#].*\sswap\s.*)$|# \1|' /etc/fstab || true
    print_status "Swap disabled and /etc/fstab entries commented (backup at /etc/fstab.bak)"
}

step_firewall() {
    require_root
    ufw allow 22
    ufw allow 80
    ufw allow 443
    ufw --force enable

    # Allow container traffic on podman bridges so aardvark-dns (container DNS)
    # can answer queries. UFW's default INPUT DROP blocks this otherwise.
    if ! grep -q 'podman+' /etc/ufw/before.rules 2>/dev/null; then
        sed -i '/^COMMIT$/i # Allow podman bridge traffic (aardvark-dns + container routing)\n-A ufw-before-input -i podman+ -j ACCEPT\n-A ufw-before-forward -i podman+ -j ACCEPT\n-A ufw-before-forward -o podman+ -j ACCEPT' \
            /etc/ufw/before.rules
        ufw reload
    fi

    print_status "Firewall: SSH, HTTP, HTTPS open; podman bridges unrestricted"
}

step_fail2ban() {
    require_root
    cat > /etc/fail2ban/jail.d/mutual-aid.local << 'EOF'
# Mutual Aid Form — fail2ban jails
# Written by deploy/remote-setup.sh

[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled  = true
port     = ssh
maxretry = 3
EOF
    systemctl enable fail2ban
    systemctl restart fail2ban
    print_status "fail2ban enabled — SSH jail active (ban after 3 attempts / 1h)"
}

step_sysctl_harden() {
    require_root
    cat > /etc/sysctl.d/99-mutual-aid-hardening.conf << 'EOF'
# Mutual Aid Form — Kernel hardening
# Written by deploy/remote-setup.sh

# Decrypted PII lives in Python strings in RAM. Never page it to disk.
vm.swappiness = 0

# NOTE: net.ipv4.ip_forward is intentionally NOT set here.
# Podman needs it enabled for bridge networking; the distro default is fine.

# Rootless podman binds :80 and :443 for Caddy. Default kernel threshold is
# 1024; lower it to 80 so the deploy user can publish those ports.
net.ipv4.ip_unprivileged_port_start = 80

# SYN flood protection
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# ICMP hardening
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Disable ICMP redirects (not a router)
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Source routing (spoofing)
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# Reverse path filtering (anti-spoofing)
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Log packets with impossible source addresses
net.ipv4.conf.all.log_martians = 1
EOF
    sysctl --system > /dev/null
    print_status "Kernel hardening applied (/etc/sysctl.d/99-mutual-aid-hardening.conf)"
}

step_auto_updates() {
    require_root
    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    # NEVER auto-reboot — decrypted PII in RAM is lost on reboot, and more
    # importantly containers won't come back up without the encryption_keys
    # secret being re-mounted. Operators reboot manually during maintenance.
    if [ -f /etc/apt/apt.conf.d/50unattended-upgrades ]; then
        sed -i 's|//Unattended-Upgrade::Automatic-Reboot ".*";|Unattended-Upgrade::Automatic-Reboot "false";|' \
            /etc/apt/apt.conf.d/50unattended-upgrades
        sed -i 's|Unattended-Upgrade::Automatic-Reboot "true";|Unattended-Upgrade::Automatic-Reboot "false";|' \
            /etc/apt/apt.conf.d/50unattended-upgrades
    fi

    systemctl enable unattended-upgrades
    systemctl restart unattended-upgrades
    print_status "Security auto-updates on; auto-reboot off (reboot manually after kernel updates)"
}

step_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        run_as_user cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        print_status "Created .env from .env.example"
    fi

    print_info "Opening .env in ${EDITOR:-nano}. Set ALLOWED_HOSTS to your real domain(s)."
    read -rp "Press Enter to continue..."
    run_as_user "${EDITOR:-nano}" "$PROJECT_ROOT/.env"

    set -a
    # shellcheck source=/dev/null
    . "$PROJECT_ROOT/.env"
    set +a

    if [ -z "${ALLOWED_HOSTS:-}" ] || [[ "$ALLOWED_HOSTS" == *yourdomain.org* ]]; then
        print_error "ALLOWED_HOSTS is empty or still set to the placeholder. Re-run to fix."
        exit 1
    fi

    print_status "ALLOWED_HOSTS=$ALLOWED_HOSTS"
}

step_caddy_config() {
    set -a
    # shellcheck source=/dev/null
    . "$PROJECT_ROOT/.env"
    set +a
    local domain
    domain="$(echo "$ALLOWED_HOSTS" | cut -d',' -f1 | tr -d ' ')"

    if ! grep -q 'yourdomain.org' "$PROJECT_ROOT/Caddyfile"; then
        print_info "Caddyfile already customized — skipping substitution"
        return 0
    fi

    run_as_user sed -i.bak "s/yourdomain.org/$domain/g" "$PROJECT_ROOT/Caddyfile"
    print_status "Caddyfile: yourdomain.org → $domain (backup at Caddyfile.bak)"
}

step_secrets() {
    if [ -f "$PROJECT_ROOT/secrets/encryption_keys.txt" ]; then
        print_warning "secrets/ already populated — NOT regenerating (would destroy all PII)"
        return 0
    fi

    run_as_user sh "$PROJECT_ROOT/deploy/setup_secrets.sh"

    echo ""
    print_error "=============================================================="
    print_error "  BACK UP secrets/encryption_keys.txt TO AN OFFLINE LOCATION"
    print_error "  RIGHT NOW. Losing this file destroys all encrypted PII."
    print_error "=============================================================="
    echo ""
    read -rp "Press Enter once you have copied encryption_keys.txt off this server..."
}

step_dns_verify() {
    set -a
    # shellcheck source=/dev/null
    . "$PROJECT_ROOT/.env"
    set +a
    local domain
    domain="$(echo "$ALLOWED_HOSTS" | cut -d',' -f1 | tr -d ' ')"

    local ipv4 ipv6
    ipv4="$(curl -sf --ipv4 --max-time 5 https://ifconfig.me 2>/dev/null)" || true
    ipv6="$(curl -sf --ipv6 --max-time 5 https://ifconfig.me 2>/dev/null)" || true

    if [ -z "$ipv4" ] && [ -z "$ipv6" ]; then
        print_error "Could not determine this server's public IP (ifconfig.me unreachable)"
        exit 1
    fi

    local resolved
    resolved="$(getent ahosts "$domain" 2>/dev/null | awk '{ print $1 }' | sort -u)" || true

    if [ -z "$resolved" ]; then
        print_error "DNS: '$domain' does not resolve."
        [ -n "$ipv4" ] && print_error "  Add A record:    $domain → $ipv4"
        [ -n "$ipv6" ] && print_error "  Add AAAA record: $domain → $ipv6"
        exit 1
    fi

    local matched=""
    while IFS= read -r ip; do
        if [ "$ip" = "$ipv4" ] || [ "$ip" = "$ipv6" ]; then
            matched="$ip"
            break
        fi
    done <<< "$resolved"

    if [ -z "$matched" ]; then
        print_error "DNS mismatch: '$domain' resolves to:"
        while IFS= read -r ip; do echo "    $ip"; done <<< "$resolved"
        print_error "This server's IPs:"
        [ -n "$ipv4" ] && print_error "  IPv4: $ipv4"
        [ -n "$ipv6" ] && print_error "  IPv6: $ipv6"
        print_error "Fix DNS before continuing — wrong DNS burns Let's Encrypt rate limits."
        exit 1
    fi

    print_status "DNS OK: $domain → $matched"
}

step_build() {
    run_as_user bash -c "cd '$PROJECT_ROOT' && podman compose build"
}

step_start() {
    run_as_user bash -c "cd '$PROJECT_ROOT' && podman compose up -d"

    # `podman compose up -d` exits 0 even when individual containers fail to
    # start (rootless port bind, image pull error, etc.). Verify each expected
    # service is actually running so we don't false-positive the checkpoint.
    local project name status failed=0
    project="$(basename "$PROJECT_ROOT")"
    for svc in web caddy; do
        name="${project}_${svc}_1"
        status=$(run_as_user podman inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)
        if [ "$status" != "running" ]; then
            print_error "  $name: $status"
            failed=1
        fi
    done
    if [ "$failed" -ne 0 ]; then
        print_error "One or more containers failed to start — check: podman logs <name>"
        exit 1
    fi

    print_info "Migrations run automatically from the container entrypoint"
}

step_timers() {
    require_root
    cp "$PROJECT_ROOT"/deploy/systemd/*.service /etc/systemd/system/
    cp "$PROJECT_ROOT"/deploy/systemd/*.timer   /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now mutual-aid-deadman.timer
    systemctl enable --now mutual-aid-backup.timer
    print_status "Timers installed and running:"
    systemctl list-timers 'mutual-aid-*' --no-pager || true
}

step_verify() {
    set -a
    # shellcheck source=/dev/null
    . "$PROJECT_ROOT/.env"
    set +a
    local domain
    domain="$(echo "$ALLOWED_HOSTS" | cut -d',' -f1 | tr -d ' ')"

    print_info "Polling https://$domain/ for up to 60s (Caddy may still be provisioning TLS)..."
    local i=0
    while [ $i -lt 12 ]; do
        if curl -sfI --max-time 10 "https://$domain/" > /dev/null 2>&1; then
            print_status "https://$domain/ is responding"
            return 0
        fi
        i=$((i + 1))
        echo "  Attempt $i/12 — not ready yet, waiting 5s..."
        sleep 5
    done
    print_warning "https://$domain/ did not respond after 60s."
    print_warning "Normal if Caddy is still getting its cert. Check: curl -I https://$domain/"
}

# -- Orchestrator --------------------------------------------------------------

main() {
    print_header "Mutual Aid Form — VPS Setup"

    if [ "$TARGET_USER" = "root" ]; then
        print_error "Rootless podman needs a non-root user that owns $PROJECT_ROOT."
        print_error "Re-clone as a non-root user, then run: sudo ./deploy/remote-setup.sh"
        exit 1
    fi
    print_info "Rootless podman + file ownership will use user: $TARGET_USER"

    if [ -f "$STATE_FILE" ]; then
        print_info "Resuming. Completed steps:"
        while IFS= read -r s; do echo "  [✓] $s"; done < "$STATE_FILE"
        echo ""
    fi

    trap 'print_error "Step failed. Fix the issue above, then re-run: sudo ./deploy/remote-setup.sh"' ERR

    local steps=(
        "system_deps|Install system packages|step_system_deps"
        "luks_verify|Verify LUKS is active|step_luks_verify"
        "swap_disable|Disable swap|step_swap_disable"
        "firewall|Configure firewall (ufw)|step_firewall"
        "fail2ban|Install & configure fail2ban|step_fail2ban"
        "sysctl_harden|Apply kernel hardening|step_sysctl_harden"
        "auto_updates|Enable security auto-updates|step_auto_updates"
        "env|Configure .env|step_env"
        "caddy_config|Substitute domain in Caddyfile|step_caddy_config"
        "secrets|Generate Podman secrets|step_secrets"
        "dns_verify|Verify DNS resolution|step_dns_verify"
        "build|Build containers|step_build"
        "start|Start containers|step_start"
        "timers|Install systemd timers|step_timers"
        "verify|Smoke-test the site|step_verify"
    )
    local total=${#steps[@]}
    local num=0
    for entry in "${steps[@]}"; do
        num=$((num + 1))
        IFS='|' read -r step_id step_desc step_fn <<< "$entry"
        run_step "$num" "$total" "$step_id" "$step_desc" "$step_fn"
    done

    print_header "Setup complete."
    echo "Next: podman exec -it mutual-aid-web-1 python manage.py createsuperuser"
    echo "Then every volunteer must enrol TOTP (see docs/usage.md)."
    echo ""
    echo "Reset progress: rm $STATE_FILE"
}

main "$@"
