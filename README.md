# Cloudflare Email Manager Bot

Bot Telegram pribadi (satu pemilik) untuk mengelola **Cloudflare Email Routing**:
buat email manual, buat 1-10 email random sekaligus, lihat & hapus email per
domain, dan lihat daftar domain — semuanya lewat **satu pesan dashboard** yang
selalu di-edit (chat tidak penuh pesan baru).

Bot ini **tidak** membaca inbox / isi email. Hanya mengelola alamat routing.

## Fitur

- Owner-only (hanya `TELEGRAM_OWNER_ID` yang bisa memakai).
- Satu pesan dashboard, semua navigasi pakai `editMessageText`.
- Buat email **manual** (validasi nama) & **random** (1-10 sekaligus).
- Generator nama Eropa dengan ratusan ribu kombinasi, **unik global**
  (nama lama / yang sudah dihapus tidak pernah dipakai ulang).
- Reservasi nama + cek ganda (DB + Cloudflare) sebelum create.
- Aman dari double-click (lock per batch + transaksi DB).
- List & hapus email per domain, paginasi 20 per halaman.
- Premium / custom emoji (opsional) + **Local Bot API** + **Redis** untuk respon cepat.
- Docker Compose + `install.sh` satu kali jalan.

## Teknologi

Python 3.11 - aiogram 3 - httpx - SQLAlchemy 2 (async) + aiosqlite -
pydantic-settings - Redis - Docker.

## Persiapan Cloudflare

Buat **API Token** (bukan Global API Key) dengan permission minimum:

- Zone - Email Routing Rules - **Edit**
- Zone - Zone - **Read**
- Account - Email Routing Addresses - **Read**

Pastikan **Email Routing aktif** di tiap domain dan **Destination Address**
(`DEFAULT_DESTINATION_EMAIL`) sudah **terverifikasi** di Cloudflare.

## Instalasi cepat (VPS Ubuntu/Debian)

```bash
git clone https://github.com/Rayzell25/Email-cf.git
cd Email-cf
chmod +x install.sh
sudo ./install.sh
```

`install.sh` akan: memasang Docker (jika belum ada), membuat & mengisi `.env`
secara interaktif, lalu menjalankan seluruh stack (bot + telegram-bot-api + redis).

Lihat log:

```bash
sudo docker compose logs -f bot
```

## Instalasi manual (Docker)

```bash
cp .env.example .env   # isi nilainya
docker compose pull && docker compose up -d --build
```

## Menjalankan tanpa Docker (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # isi nilainya, kosongkan BOT_API_ROOT & REDIS_URL bila tidak dipakai
python -m app.main
```

## Konfigurasi `.env`

| Variabel | Wajib | Keterangan |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ya | Token dari @BotFather |
| `TELEGRAM_OWNER_ID` | ya | Telegram ID pemilik (satu-satunya yang diizinkan) |
| `CLOUDFLARE_API_TOKEN` | ya | API Token (permission minimum di atas) |
| `CLOUDFLARE_ACCOUNT_ID` | - | Untuk membaca destination addresses |
| `DEFAULT_DESTINATION_EMAIL` | ya | Tujuan forwarding (harus terverifikasi) |
| `DATABASE_URL` | - | Default sqlite di `data/bot.db` |
| `BOT_API_ROOT` | - | URL Local Bot API (kosong = pakai cloud Telegram) |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | - | Dari my.telegram.org (untuk Local Bot API) |
| `REDIS_URL` | - | Cache FSM (kosong = in-memory) |
| `USE_PREMIUM_EMOJI` | - | `1` untuk premium emoji, `0` untuk unicode biasa |

## Premium / custom emoji

- Teks pesan memakai `<tg-emoji emoji-id="...">fallback</tg-emoji>`.
- Tombol memakai field `icon_custom_emoji_id` (Bot API 9.4+).
- **Syarat**: pemilik bot punya Telegram Premium **dan** server Bot API mendukung
  (server Local Bot API harus versi 9.4+ — server lama mengabaikannya diam-diam).
- Default `USE_PREMIUM_EMOJI=0` → unicode biasa. Isi `custom_emoji_id` Anda
  sendiri di `app/utils/emoji.py` (cara dapat id: kirim premium emoji ke bot lalu
  baca `message.entities[].custom_emoji_id`), lalu set `USE_PREMIUM_EMOJI=1`.
- Jika emoji ditolak server, bot otomatis fallback ke unicode (tidak error).

## Keamanan

- Token & API key hanya dibaca dari `.env` (gitignored), tidak pernah di-log,
  tidak di callback, tidak ditampilkan ke pengguna.
- Logger memfilter pola yang menyerupai token.
- Bot hanya menerima perintah dari owner.

## Pengembangan

```bash
python -m compileall app          # cek sintaks semua modul
python -m pytest -q                # unit test + smoke test (18 test)
python -m tests.smoke.run_smoke    # smoke test end-to-end (alur asli, 43 cek)
```

Smoke test menjalankan alur asli handler+service (start -> buat random ->
konfirmasi -> anti double-click -> partial+retry -> list -> hapus -> manual ->
owner-only) memakai stub ringan untuk library eksternal dan fake in-memory untuk
DB & Cloudflare, sehingga bug logika/alur terdeteksi tanpa koneksi nyata.
Verifikasi runtime penuh (aiogram/SQLAlchemy asli) tetap dilakukan saat deploy
Docker di VPS.
