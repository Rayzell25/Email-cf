# Cloudflare Email Manager Bot

Bot Telegram pribadi (satu pemilik) untuk mengelola **Cloudflare Email Routing**
lewat **satu pesan dashboard**: buat email manual, buat 1–15 email random
sekaligus, lihat & hapus email per domain, dan lihat daftar domain. Semua
navigasi meng-*edit* pesan yang sama (chat tidak penuh pesan baru).

Bot ini **tidak** membaca inbox / isi email — hanya mengelola alamat routing.

---

## Daftar Isi
1. [Fitur](#fitur)
2. [Teknologi](#teknologi)
3. [Prasyarat](#prasyarat)
4. [Langkah 1 — Cloudflare API Token](#langkah-1--cloudflare-api-token)
5. [Langkah 2 — Account ID](#langkah-2--account-id)
6. [Langkah 3 — Verifikasi email tujuan (penting!)](#langkah-3--verifikasi-email-tujuan-penting)
7. [Langkah 4 — Telegram Bot Token & Owner ID](#langkah-4--telegram-bot-token--owner-id)
8. [Instalasi cepat (install.sh)](#instalasi-cepat-installsh)
9. [Mengisi/menyunting .env dengan nano](#mengisimenyunting-env-dengan-nano)
10. [Perintah Docker penting](#perintah-docker-penting)
11. [Update ke versi terbaru](#update-ke-versi-terbaru)
12. [Troubleshooting (kasus nyata)](#troubleshooting-kasus-nyata)
13. [Pengembangan & test](#pengembangan--test)
14. [Keamanan](#keamanan)

---

## Fitur
- Owner-only (hanya `TELEGRAM_OWNER_ID` yang bisa memakai).
- Satu pesan dashboard; `/start` ulang menghapus menu lama → tetap 1 pesan.
- Buat email **manual** (validasi nama) & **random 1–15** sekaligus (tombol 2 kolom).
- Generator nama Eropa ~261rb+ kombinasi, **unik global** (nama lama / yang sudah
  dihapus tidak pernah dipakai ulang).
- Reservasi nama + cek ganda (DB + Cloudflare) sebelum create; **aman dari double-click**.
- List & hapus email per domain, paginasi (tombol **Next** muncul saat perlu).
- UI Bahasa Inggris, Local Bot API + Redis untuk respon cepat.
- Docker Compose + `install.sh` sekali jalan (otomatis di dalam `screen`).

## Teknologi
Python 3.11 · aiogram 3 · httpx · SQLAlchemy 2 (async) + aiosqlite ·
pydantic-settings · Redis · Docker.

## Prasyarat
- VPS Ubuntu/Debian (akses root / sudo).
- Akun Cloudflare dengan domain yang **Email Routing**-nya sudah aktif.
- Bot Telegram (token dari @BotFather) dan Telegram user ID kamu.

---

## Langkah 1 — Cloudflare API Token

1. Buka **https://dash.cloudflare.com/profile/api-tokens**
   (ikon profil kanan-atas → **My Profile** → **API Tokens**).
2. **Create Token** → **Create Custom Token** (Get started).
3. Beri nama, misal `Email Bot`.
4. **Permissions** — tambahkan **3 baris** (klik **+ Add more**):

   | Scope | Permission | Level |
   |-------|------------|-------|
   | **Zone** | Email Routing Rules | **Edit** ← wajib Edit, bukan Read |
   | **Zone** | Zone | **Read** |
   | **Account** | Email Routing Addresses | **Read** |

   > ⚠️ Paling sering salah di sini: kalau **Email Routing Rules** cuma **Read**,
   > dashboard tampil "Connected" tapi **buat email gagal 401/403**. Harus **Edit**.

5. **Account Resources**: `Include` → akun kamu.
6. **Zone Resources**: `Include` → **All zones** (atau domain tertentu).
7. **Continue to summary** → **Create Token** → **COPY** token-nya (muncul sekali).

Token ini → `CLOUDFLARE_API_TOKEN`.

## Langkah 2 — Account ID (dan Zone ID)

`CLOUDFLARE_ACCOUNT_ID` dipakai bot untuk membaca daftar alamat tujuan. Ada 3
cara mengambilnya — pilih yang paling gampang:

**Cara A — dari URL dashboard (paling cepat):**
Login ke https://dash.cloudflare.com lalu klik salah satu domainmu. Perhatikan
URL di browser, formatnya:
```
https://dash.cloudflare.com/<ACCOUNT_ID>/<nama-domain>
```
Bagian setelah `dash.cloudflare.com/` itulah **Account ID** (deretan ~32 karakter
huruf+angka). Copy.

**Cara B — dari halaman Overview domain:**
Dashboard → klik domain → menu **Overview** → scroll ke bawah, lihat panel kanan
bagian **API**. Di situ ada:
- **Account ID** → ini untuk `CLOUDFLARE_ACCOUNT_ID`
- **Zone ID** → ID khusus per-domain (tidak wajib untuk bot, hanya untuk diagnostik)

Klik tombol **Click to copy** di sebelahnya.

**Cara C — lewat API (pakai token dari Langkah 1):**
```bash
curl -s -H "Authorization: Bearer TOKEN_KAMU" \
  "https://api.cloudflare.com/client/v4/accounts" \
  | grep -oE '"id":"[a-f0-9]{32}"|"name":"[^"]*"' | head -4
```
`"id"` pertama = Account ID.

> Catatan: Account ID **berbeda** dari Zone ID. Account ID untuk seluruh akun;
> Zone ID khusus satu domain. Bot butuh **Account ID**.

## Langkah 3 — Verifikasi email tujuan (PENTING!)
`DEFAULT_DESTINATION_EMAIL` adalah alamat tujuan forwarding, dan **harus sudah
diverifikasi** di Cloudflare, kalau tidak create gagal dengan **code 2054
"Destination address is not verified"**.

1. Cloudflare → domain → **Email** → **Email Routing** → tab **Destination addresses**.
2. **Add destination address** → masukkan email kamu → buka inbox email itu →
   klik link verifikasi dari Cloudflare sampai statusnya **Verified**.
3. Destination address bersifat **level akun** — sekali verified, bisa dipakai
   untuk semua domain di akun itu.

Cek daftar email tujuan yang sudah verified (jalankan di VPS setelah bot jalan):
```bash
cd ~/Email-cf
TOKEN=$(docker compose exec -T bot printenv CLOUDFLARE_API_TOKEN)
ACC=$(docker compose exec -T bot printenv CLOUDFLARE_ACCOUNT_ID)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$ACC/email/routing/addresses" \
  | grep -oE '"email":"[^"]*"|"verified":"[^"]*"|"verified":null'
```
`"verified":"<tanggal>"` = sudah; `"verified":null` = belum. Pastikan
`DEFAULT_DESTINATION_EMAIL` sama persis dengan salah satu yang sudah verified.

## Langkah 4 — Telegram Bot Token & Owner ID
- **Bot Token**: chat @BotFather → `/newbot` → salin token → `TELEGRAM_BOT_TOKEN`.
- **Owner ID**: chat @userinfobot → salin angka ID kamu → `TELEGRAM_OWNER_ID`.

---

## Instalasi cepat (install.sh)

```bash
git clone https://github.com/Rayzell25/Email-cf.git
cd Email-cf
chmod +x install.sh
sudo ./install.sh
```

`install.sh` otomatis: pasang Docker (kalau belum), buat & isi `.env` interaktif,
lalu menjalankan seluruh stack (bot + telegram-bot-api + redis).

Catatan:
- Installer berjalan di dalam **`screen`** bernama `emailcf`. Kalau SSH putus saat
  mengisi konfigurasi, prosesnya tetap jalan — sambung lagi: `screen -r emailcf`
  (atau `screen -d -r emailcf`). Nonaktifkan screen: `NO_SCREEN=1 sudo ./install.sh`.
- Kalau muncul error **apt lock** (`Could not get lock`), itu karena auto-update
  Ubuntu sedang jalan; installer otomatis menunggu sampai lepas.
- Saat ditanya **Telegram API ID/Hash**, langsung **Enter** (sudah ada default).
  Yang wajib diisi: Bot Token, Owner ID, Cloudflare API Token, Account ID,
  Default Destination Email (yang sudah **verified**).

---

## Mengisi/menyunting .env dengan nano

```bash
cd ~/Email-cf
nano .env
```
Edit baris berikut (yang **wajib**):
```
TELEGRAM_BOT_TOKEN=8xxxxx:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_OWNER_ID=6259964934
CLOUDFLARE_API_TOKEN=token_yang_permissionnya_Email_Routing_Rules_EDIT
CLOUDFLARE_ACCOUNT_ID=c8555ac7bbedb1cb6fc08c678f303702
DEFAULT_DESTINATION_EMAIL=emailkamu_yang_sudah_verified@gmail.com
```
Biarkan **kosong** (sudah di-handle docker-compose):
```
BOT_API_ROOT=
REDIS_URL=
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```
`TELEGRAM_API_ID` / `TELEGRAM_API_HASH` sudah terisi default — biarkan.

Simpan di nano: **Ctrl+O** → Enter → **Ctrl+X**.

> ⚠️ Setiap habis mengubah `.env`, **wajib** recreate container agar terbaca:
> ```bash
> docker compose up -d --force-recreate bot
> ```
> Cek nilai yang benar-benar dipakai container:
> ```bash
> docker compose exec -T bot printenv DEFAULT_DESTINATION_EMAIL
> ```

---

## Perintah Docker penting
```bash
cd ~/Email-cf
docker compose ps                      # status container
docker compose logs -f bot             # lihat log bot (ikuti)
docker compose logs --tail=50 bot      # 50 baris terakhir
docker compose up -d --build           # build + jalan
docker compose up -d --force-recreate bot   # paksa muat ulang .env
docker compose restart bot             # restart cepat (tidak reload .env)
docker compose down                    # stop semua
```
Cek Local Bot API kepakai (kunci respon cepat):
```bash
docker compose logs bot | grep -i "Bot API"
# harus: Using Local Bot API server at http://telegram-bot-api:8081
```

---

## Update ke versi terbaru
Cara normal:
```bash
cd ~/Email-cf
git pull
docker compose up -d --build
```
Cara "100% persis seperti GitHub" (kalau pernah edit file / bentrok):
```bash
cd ~/Email-cf
git fetch origin
git reset --hard origin/main
docker compose build --no-cache bot
docker compose up -d --force-recreate bot
```
> Aman: `.env` dan folder `data/` **tidak terhapus** (gitignored) — token,
> konfigurasi, dan database email tetap utuh.

Setelah update, tekan `/start` di Telegram untuk dashboard baru.

---

## Troubleshooting (kasus nyata)

### 1. "🟢 Connected" tapi buat email gagal **401/403**
Token punya **Zone:Read** (jadi Connected) tapi **tidak punya Email Routing Rules:
Edit**. Read bisa lihat/list, tapi create butuh **Edit (write)**.
**Fix:** edit token (Langkah 1) → ubah **Email Routing Rules** ke **Edit** → Save.
Mengedit permission tidak mengubah nilai token, jadi `.env` tak perlu diubah.

Pastikan token yang dipakai bot = token yang kamu edit:
```bash
docker compose exec -T bot printenv CLOUDFLARE_API_TOKEN | cut -c1-12
```

### 2. Bisa lihat detail email, tapi create 401/403
Sama seperti #1: read jalan, write tidak. Naikkan ke **Edit**.

### 3. Create gagal **code 2054 — Destination address is not verified**
`DEFAULT_DESTINATION_EMAIL` belum diverifikasi (atau beda dari yang verified).
**Fix:** verifikasi email tujuan (Langkah 3), ATAU ganti ke email yang sudah
verified, lalu:
```bash
nano .env       # samakan DEFAULT_DESTINATION_EMAIL ke yang verified
docker compose up -d --force-recreate bot
```

### 4. Klik tombol jumlah tidak respon / create diam
Versi lama punya bug async (`MissingGreenlet`). Sudah diperbaiki. Pastikan pakai
kode terbaru:
```bash
git fetch origin && git reset --hard origin/main
docker compose build --no-cache bot && docker compose up -d --force-recreate bot
```

### 5. Pesan error masih versi lama / fitur baru belum muncul
Container masih image lama. Rebuild bersih:
```bash
docker compose build --no-cache bot && docker compose up -d --force-recreate bot
```

### 6. `.env` sudah diedit tapi tidak berubah
Container belum reload. `docker compose up -d --force-recreate bot`, lalu cek
dengan `docker compose exec -T bot printenv NAMA_VAR`.

### 7. apt lock saat install (`Could not get lock`)
Auto-update Ubuntu sedang jalan. Tunggu, atau:
```bash
while sudo fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock >/dev/null 2>&1; do sleep 3; done
sudo ./install.sh
```

### 8. Respon bot lambat
Cek Local Bot API kepakai (lihat bagian Perintah Docker). Kalau muncul "cloud"
bukan `telegram-bot-api:8081`, berarti `BOT_API_ROOT` tidak terbaca. Update
server lokal bila perlu:
```bash
docker compose pull telegram-bot-api && docker compose up -d --force-recreate telegram-bot-api
```

### Diagnostik cepat (uji token yang dipakai bot)
```bash
cd ~/Email-cf
TOKEN=$(docker compose exec -T bot printenv CLOUDFLARE_API_TOKEN)
ZID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?per_page=1" \
  | grep -o '"id":"[a-f0-9]\{32\}"' | head -1 | cut -d'"' -f4)
echo "Zone: $ZID"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZID/email/routing/rules" | head -c 300
```
`success:true` = token OK baca rules. Kalau create masih gagal → cek destination (#3).

---

## Pengembangan & test
```bash
python -m compileall app            # cek sintaks semua modul
python -m pytest -q                 # unit + smoke (subprocess)
python -m tests.smoke.run_smoke     # smoke end-to-end alur asli
```
Catatan: sandbox tanpa akses PyPI tidak bisa menjalankan aiogram/SQLAlchemy
asli; smoke test memakai stub + DB tiruan, jadi bug khusus runtime DB asli
(mis. async lazy-load) hanya terlihat saat dijalankan via Docker di VPS.

## Keamanan
- Token & API key hanya dari `.env` (gitignored), tidak di-log (logger redaksi),
  tidak di callback, tidak ditampilkan ke pengguna.
- Bot hanya menerima perintah dari `TELEGRAM_OWNER_ID`.
- Pakai API Token dengan permission minimum (bukan Global API Key).

---

## Struktur folder (ringkas)
```
app/
  main.py            entry (router wiring, middleware, polling)
  config.py          baca env via pydantic-settings
  bot.py             Bot/Dispatcher/storage (Local Bot API + Redis)
  handlers/          start, menu, domains, create_random, create_manual,
                     email_list, email_delete, render, states
  keyboards/         main_menu, domains, random_email, email_list, common
  services/          cloudflare, name_generator, reservation_service,
                     email_service, dashboard
  database/          models, session, repositories/
  middlewares/       owner_only, dependencies, error_handler
  utils/             validators, pagination, callbacks, logger, emoji, ui
tests/               unit + tests/smoke (harness end-to-end)
Dockerfile · docker-compose.yml · install.sh · .env.example
```
