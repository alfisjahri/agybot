# AgyBot

Bot framework sendiri yang memakai **agy CLI** sebagai mesin LLM — dibangun
sebagai pengganti OpenBot yang relay cloud-nya rusak. Terdiri dari server
web (Flask) dengan bot + routine terjadwal + integrasi Google, dan aplikasi
Android pendamping untuk notifikasi routine.

> Repo ini publik. `agy` CLI **bukan** bagian dari repo — itu dependency
> eksternal yang di-install terpisah di server. Repo ini berisi kode AgyBot
> yang **memanggil** `agy` (`agy -p --model ... --output-format json`).

## Isi repo

```
server/            Server Flask (bot, routine, Google, kuota, notifikasi)
  app.py           Aplikasi web + API
  agy_client.py    Pemanggil agy CLI
  routines.py      Mesin routine terjadwal (APScheduler)
  store.py         Akses database bot/pesan
  seed.py          Seed bot + routine awal (hati-hati: menimpa avatar)
  seed_routines.py Seed routine
  google_tools.py  Integrasi Google (Forms via GAS Web App, rekap)
  quota.py         Pembaca kuota agy (/usage lewat PTY)
  verify.py        Verifikasi hasil routine
  avatars.py       Avatar bot (shape + color picker)
  notifications.py Event notifikasi untuk APK
  fcm.py           Firebase Cloud Messaging (server-side, opsional)
  skills/          5 skill lokal (buat-form-kuis, rekap-nilai,
                   cek-belum-mengerjakan, urutan-materi, buat-video)
  templates/       UI web (chat, routines, usage)
  static/          JS/CSS/logo + avatar blob DS-Bot (Apache 2.0)
  requirements.txt Dependensi Python
  run.sh           Helper jalan lokal (venv)
  agybot.service   Unit systemd (sesuaikan path-nya)
apk/               Aplikasi Android pendamping (WebView + polling notifikasi)
  project/         Source Android (Java, manifest, resource XML)
  build.sh         Build manual via aapt2 + d8 (tanpa Gradle)
docs/              Spesifikasi AgyBot
```

## Cara jalan (server)

1. Python 3.12 + `pip install -r server/requirements.txt` (di venv).
2. Install `agy` CLI dan login (token OAuth agy di `~/.gemini/`).
3. Buat direktori `server/data/` (tidak ikut repo) berisi:
   - `secrets.json` — kunci internal (mis. WALI_KEY), permission 600.
   - `firebase-service-account.json` — hanya kalau pakai FCM.
   - Database SQLite (`agybot.db`, `notifications.db`) dibuat otomatis.
   - `rekap/` — file rekap xlsx (data siswa, jangan pernah di-commit).
4. KaTeX lokal (opsional, untuk render rumus): unduh KaTeX 0.16.11 dan
   letakkan di `server/static/katex/` (katex.min.css, katex.min.js, fonts/).
   Tanpa ini, rumus tampil sebagai teks.
5. Jalankan: `cd server && ./run.sh`, atau pasang `agybot.service`
   (sesuaikan `User`, `WorkingDirectory`, dan `ExecStart`).

Aturan penting:
- Setiap ubah template → restart service (cache Jinja).
- Setiap ubah `style.css`/JS → bump `?v=N` di template.

## Aplikasi Android (apk/)

APK adalah WebView ke server + foreground service polling notifikasi
(`PollService`, 30 detik). Build: `./apk/build.sh` (butuh Android SDK:
aapt2, d8, apksigner, dan keystore sendiri).

**Aset biner yang TIDAK ikut repo** (karena connector GitHub hanya menerima
file teks): ikon launcher PNG (`res/mipmap-*/ic_launcher*.png`),
`splash_logo.png`, dan file `.apk` hasil build. Tambahkan sendiri dari
release atau generate ulang sebelum build — tanpa ikon itu, build gagal.

## Keamanan

Jangan pernah commit: `server/data/` (secrets, database, rekap siswa),
file `credentials.json` Google OAuth, `firebase-service-account.json`,
keystore, dan file `.env`. Semua sudah ada di `.gitignore`.
