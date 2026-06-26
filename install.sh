#!/usr/bin/env bash
# ============================================================================
#  Cloudflare Email Manager Bot - one-shot installer for Ubuntu/Debian VPS.
#
#  Does everything in a single run:
#    1. installs Docker + the compose plugin (if missing)
#    2. creates / fills .env (interactive on first run)
#    3. pulls images, builds the bot, and starts the whole stack
#       (bot + Local Bot API server + Redis)
#
#  Usage:
#    chmod +x install.sh
#    sudo ./install.sh
# ============================================================================
set -euo pipefail

# --- pretty output ----------------------------------------------------------
c_green="\033[0;32m"; c_yellow="\033[1;33m"; c_red="\033[0;31m"; c_reset="\033[0m"
info()  { echo -e "${c_green}[INFO]${c_reset} $*"; }
warn()  { echo -e "${c_yellow}[WARN]${c_reset} $*"; }
err()   { echo -e "${c_red}[ERR ]${c_reset} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- must be root (for installing docker) -----------------------------------
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    err "Jalankan sebagai root atau pasang sudo terlebih dahulu."
    exit 1
  fi
fi

# --- 1. Docker --------------------------------------------------------------
# Wait until no other process (e.g. unattended-upgrades) holds the apt/dpkg
# locks. Avoids the "Could not get lock /var/lib/apt/lists/lock" error.
wait_for_apt() {
  local tries=0
  while $SUDO fuser /var/lib/dpkg/lock-frontend \
        /var/lib/dpkg/lock /var/lib/apt/lists/lock >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ "$tries" -gt 60 ]; then
      warn "apt masih terkunci setelah ~5 menit; melanjutkan dan berharap lock sudah lepas."
      break
    fi
    info "Menunggu proses apt/dpkg lain selesai (auto-update?)... ($tries)"
    sleep 5
  done
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    info "Docker sudah terpasang ($(docker --version))."
  else
    info "Memasang Docker..."
    wait_for_apt
    $SUDO apt-get update -y
    $SUDO apt-get install -y ca-certificates curl
    curl -fsSL https://get.docker.com | $SUDO sh
    info "Docker terpasang."
  fi

  if docker compose version >/dev/null 2>&1; then
    info "Docker Compose plugin tersedia."
  else
    warn "Plugin 'docker compose' tidak ditemukan, mencoba memasang..."
    wait_for_apt
    $SUDO apt-get install -y docker-compose-plugin || true
  fi
}

# helper: set KEY=value in .env (replace existing line or append)
set_env() {
  local key="$1"; local value="$2"; local file=".env"
  if grep -qE "^${key}=" "$file"; then
    # use a safe delimiter (|) and escape it in the value
    local esc="${value//|/\\|}"
    sed -i "s|^${key}=.*|${key}=${esc}|" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
}

prompt_default() {
  # prompt_default "Label" "current_default" -> echoes chosen value
  local label="$1"; local def="$2"; local input=""
  if [ -n "$def" ]; then
    read -r -p "$label [$def]: " input || true
    echo "${input:-$def}"
  else
    read -r -p "$label: " input || true
    echo "$input"
  fi
}

# --- 2. .env ----------------------------------------------------------------
configure_env() {
  if [ ! -f ".env" ]; then
    cp .env.example .env
    info "Membuat .env dari .env.example."
  else
    info ".env sudah ada, melewati pembuatan."
  fi

  if [ ! -t 0 ]; then
    warn "Mode non-interaktif: edit .env secara manual lalu jalankan ulang."
    return
  fi

  echo
  info "Isi konfigurasi bot (tekan Enter untuk memakai nilai default):"

  local cur_token cur_owner cur_cf_token cur_cf_acc cur_dest cur_api_id cur_api_hash
  cur_token=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2-)
  cur_owner=$(grep -E '^TELEGRAM_OWNER_ID=' .env | cut -d= -f2-)
  cur_cf_token=$(grep -E '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2-)
  cur_cf_acc=$(grep -E '^CLOUDFLARE_ACCOUNT_ID=' .env | cut -d= -f2-)
  cur_dest=$(grep -E '^DEFAULT_DESTINATION_EMAIL=' .env | cut -d= -f2-)
  cur_api_id=$(grep -E '^TELEGRAM_API_ID=' .env | cut -d= -f2-)
  cur_api_hash=$(grep -E '^TELEGRAM_API_HASH=' .env | cut -d= -f2-)

  # sensible defaults for the Local Bot API credentials (override anytime)
  cur_api_id="${cur_api_id:-32773999}"
  cur_api_hash="${cur_api_hash:-d2eb7260911dbce615a1fb27f36d4b12}"

  set_env TELEGRAM_BOT_TOKEN        "$(prompt_default 'Telegram Bot Token' "$cur_token")"
  set_env TELEGRAM_OWNER_ID         "$(prompt_default 'Telegram Owner ID' "$cur_owner")"
  set_env CLOUDFLARE_API_TOKEN      "$(prompt_default 'Cloudflare API Token' "$cur_cf_token")"
  set_env CLOUDFLARE_ACCOUNT_ID     "$(prompt_default 'Cloudflare Account ID' "$cur_cf_acc")"
  set_env DEFAULT_DESTINATION_EMAIL "$(prompt_default 'Default Destination Email' "$cur_dest")"
  set_env TELEGRAM_API_ID           "$(prompt_default 'Telegram API ID (my.telegram.org)' "$cur_api_id")"
  set_env TELEGRAM_API_HASH         "$(prompt_default 'Telegram API Hash (my.telegram.org)' "$cur_api_hash")"
  set_env USE_PREMIUM_EMOJI         "$(prompt_default 'Aktifkan premium emoji? (1/0)' "$(grep -E '^USE_PREMIUM_EMOJI=' .env | cut -d= -f2- || echo 0)")"

  info ".env tersimpan."
}

# --- 3. up ------------------------------------------------------------------
start_stack() {
  info "Menarik image terbaru (telegram-bot-api & redis)..."
  $SUDO docker compose pull telegram-bot-api redis || true
  info "Membangun & menjalankan stack..."
  $SUDO docker compose up -d --build
  echo
  $SUDO docker compose ps
  echo
  info "Selesai! Lihat log dengan:"
  echo "    $SUDO docker compose logs -f bot"
}

main() {
  install_docker
  configure_env
  start_stack
}

main "$@"
