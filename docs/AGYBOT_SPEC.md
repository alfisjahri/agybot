# AgyBot — Spec (v1, 28 Okt 2026)

Bot framework sendiri Alfi, pakai `agy` CLI (Antigravity) sebagai model LLM.
Alasan: OpenBot sering reconnect + lambat (CEK 5 menit/kelas, BUAT SOAL 43 menit)
+ haus resource (idle ~844 MB / ~21% CPU). DS-Bot ringan tapi pakai DeepSeek
berbayar dan tidak punya routines. AgyBot = ringan + routines + token Pro gratis.

## Prinsip

- Model = `agy` CLI (Antigravity Pro Alfi, OAuth di /home/ubuntu/.gemini/).
  `agy -p` non-interaktif, `--output-format json`, `--model`, `--effort`,
  `--dangerously-skip-permissions` untuk tool use.
- `agy` eksekusi tool secara INTERNAL (tidak return tool_use block). Jadi
  AgyBot adalah WRAPPER TIPIS: routing pesan + memori + routines + UI.
  `agy` yang mengerjakan tugas (baca file, jalanin script, panggil API) lewat
  bash/file tools-nya sendiri.
- TIDAK perlu setara DS-Bot. Fokus ke workflow Alfi saja.
- Maksimal 5 bot, TANPA default Chief.
- Deploy di VPS Oracle (129.225.15.95), ringan (idle ~nol, on-demand).
  Direktori: /home/ubuntu/agybot. Domain (nanti): agybot.alfisjahri.my.id.

## Tech stack (rekomendasi)

- Backend: Python + Flask (konsisten dengan helper Google yang sudah Python),
  SQLite untuk config/memori/usage. Frontend: HTML/CSS/JS polos.
- `agy` dipanggil sebagai subprocess: `agy -p "<prompt>" --model <m>
  --effort <e> --output-format json --dangerously-skip-permissions`.
  Parse JSON output (conversation_id, status, response, usage).
- Routines: scheduler internal (APScheduler / node-cron setara Python) +
  trigger via API, mirip cron DS-Bot tapi built-in.
- Google: pakai helper yang sudah ada di /home/ubuntu/guru-tools/
  (gas_webapp.py, forms_api.py, credentials.json) — mount/read-only.
- Video: pakai /home/ubuntu/video-maker/ (HyperFrames) — mount read/write.

## 5 Bot (diatur Muse, Alfi bisa ubah)

| # | Nama | Peran | Model | Effort | Avatar |
|---|------|-------|-------|--------|--------|
| 1 | Guru Mapel | Materi + Form (GAS Web App) + CEK 3 aturan + rekap | gemini-3.8-flash | high | Template 1 (buku/pensil, teal) |
| 2 | Wali Kelas | Rekap absensi 8A via /api/wali/data, 07:35 + 13:35, verifikasi total = 18 | gemini-3.8-flash | low | Template 2 (clipboard, biru) |
| 3 | Video Maker | Video HyperFrames dari /video-maker/, narasi Orus | gemini-3.8-flash | high | Template 3 (play/film, koral) |
| 4 | Asisten | Helper umum: jadwal, pengingat, admin, tanya-jawab | gemini-3.8-flash | medium | Template 4 (sparkle, ungu) |
| 5 | (slot fleksibel) | Cadangan — Alfi tentukan nanti (mis. Montir coding) | gemini-3.8-flash | medium | Template 5 (gear, hijau) |

- Instruksi tiap bot disimpan sebagai file/config (mirip state.json DS-Bot).
- Per-bot model & effort bisa diubah dari UI.
- Avatar: 5 template bawaan + warna custom bebas + bisa upload gambar/foto.

## Fitur (sesuai diskusi 28 Okt)

1. Chat web UI (kirim pesan ke bot, terima balasan; bisa kirim gambar).
2. Menu Usage: token per bot + total, per hari; tampilkan juga kuota
   Antigravity (Flash 5-jam + mingguan, Argon mingguan) bila bisa dibaca.
3. Pilihan model & effort lengkap seperti `agy` (model list + effort
   low/medium/high/xhigh/max), per bot.
4. Avatar: 5 template + warna custom + upload gambar/foto.
5. Routines (seperti OpenBot, yang tidak ada di DS-Bot): jadwalkan tugas
   bot (BUAT SOAL 1 jam sebelum kelas, CEK 10 menit sebelum selesai,
   rekap absensi 07:35 + 13:35, PTMT, Kokurikuler). Trigger + laporan ke Alfi.
6. Integrasi Google: Forms (GAS Web App + forms_api.py), Drive, Sheets/rekap.
7. Verifikasi ringan (bukan Chief utuh): tiap routine punya langkah verify
   (cek link Form hidup, cross-check submit+belum = roster).
8. Memori per bot (instruksi + konteks, seperti OpenBot/DS-Bot).
9. Logo: mirip agy tapi ada mata (lihat files/agybot-logo.svg).

## Fase build

- Fase 1 (inti): server + config 5 bot + integrasi `agy` + chat UI +
  usage tracking. SATU bot end-to-end (Guru Mapel: CEK satu kelas).
- Fase 2: routines engine + integrasi Google + menu Usage.
- Fase 3: avatar, model/effort picker, kuota display, verifikasi, image input.
- Fase 4: tes end-to-end di VPS + deploy + serah terima ke Alfi.

## Batasan yang diketahui (dari PoC 28 Okt)

- `agy -p` ~8–12 detik/call; overhead input ~6.767 token (system prompt).
- `agy` tidak return tool_use block — framework tidak bisa kontrol tool
  secara terstruktur. Verifikasi harus dilakukan dengan memeriksa OUTPUT
  (link hidup, angka cocok) bukan dengan mengontrol tool call.
- Model Pro yang tersedia: gemini-4-argon, gemini-3.8-flash,
  claude-opus-5.5, claude-sonnet-5.5, gpt-oss-120b (masing-masing low/med/high).
- `agy` v1.4.8 di /home/ubuntu/.local/bin/agy (user ubuntu).
- Token Muse untuk build: estimasi maksimal ~3,4 juta token (0,34% dari 1B).

## Referensi

- PoC agy: /tmp/agy-poc-test.txt (BUKUKU-77), `agy models`, `agy -p` JSON.
- DS-Bot (pembanding): /home/ubuntu/ds-bot, https://ds-bot.alfisjahri.my.id.
- OpenBot (yang diganti): systemd openbot.service, agen Guru Mapel/Wali
  Kelas/Video Maker. GAS Web App: scriptId 1yHDSCl2CecG4YH0GQ0SSSS5kcztf9uAdiQcAYMo9KCX4nRSRu7YiIBaS.
- Aturan rekap: skor PERTAMA, susulan kolom tanggal asal + kuning, CEK 3 aturan.
