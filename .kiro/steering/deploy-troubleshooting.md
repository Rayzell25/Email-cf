# Email-cf — Deploy & Troubleshooting (catatan internal)

Bot Telegram aiogram 3 untuk Cloudflare Email Routing. Owner-only, satu pesan
dashboard, deploy via Docker Compose (bot + telegram-bot-api lokal + redis).

## Arsitektur singkat
- Entry: `app/main.py` (router wiring, middleware owner_only + dependencies,
  error_handler global, polling).
- Handler per-domain di `app/handlers/` (start, menu, domains, create_random,
  create_manual, email_list, email_delete) + `render.py` (semua teks UI, English)
  + `states.py` (FSM + cache zona/rule).
- Services: `cloudflare.py` (httpx), `name_generator.py`, `reservation_service.py`,
  `email_service.py`, `dashboard.py` (single-message logic).
- DB: SQLAlchemy async + aiosqlite, repositories di `app/database/repositories/`.
- Rahasia HANYA dari `.env` (gitignored); `docker-compose.yml` meng-override
  `BOT_API_ROOT=http://telegram-bot-api:8081`, `REDIS_URL`, `DATABASE_URL`.
- `TELEGRAM_API_ID/HASH` sudah default (untuk Local Bot API server), tidak ditanya.

## Jebakan yang SUDAH dikonfirmasi (jangan ulangi)
1. **401/403 saat create padahal "Connected"** → token kurang permission
   **Zone > Email Routing Rules > EDIT** (Read saja bikin list jalan tapi POST 403).
   Connected hanya cek `GET /zones` (Zone:Read).
2. **code 2054 "Destination address is not verified"** → `DEFAULT_DESTINATION_EMAIL`
   belum diverifikasi / beda dari yang verified. Cek via
   `GET /accounts/{acc}/email/routing/addresses` (`verified` harus ada tanggal).
   Destination = level akun (sekali verified, semua zona bisa).
3. **MissingGreenlet (async lazy-load)** → JANGAN akses atribut relationship
   (mis. `batch.items`) di luar query yang di-await. Pakai `select(...)` eksplisit.
   Sudah diperbaiki di `batches.replace_items`. Smoke test pakai DB tiruan → bug
   DB asli TIDAK ketangkap; verifikasi runtime hanya di VPS.
4. **Container tidak reload `.env`** → setelah edit `.env` WAJIB
   `docker compose up -d --force-recreate bot`; `restart` saja tidak reload env.
5. **Kode lama masih jalan** → `docker compose build --no-cache bot` lalu
   `up -d --force-recreate`. Verifikasi string penanda via `grep` di dalam container.
6. **apt lock saat install** → unattended-upgrades; install.sh sudah auto-wait.
7. **Respon lambat** → pastikan Local Bot API kepakai
   (`docker compose logs bot | grep "Bot API"`). Zona & rule sudah di-cache di FSM
   (menu/pagination tidak refetch; hanya REFRESH yang fetch ulang).

## Aturan kerja
- Test sebelum kirim: `python -m pytest -q` (unit + smoke) harus 0 gagal.
- Jangan buka PR; user deploy dari `main`. Commit kecil & jelas, push ke `main`.
- UI Bahasa Inggris. Tombol: emoji unicode (premium emoji opsional via
  `USE_PREMIUM_EMOJI` + `icon_custom_emoji_id` di `app/utils/emoji.py`).
- Random create: 1–15, tombol angka 2 kolom. Pagination: tombol Prev hanya saat
  ada halaman sebelumnya, Next saat ada halaman berikutnya.
