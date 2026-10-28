# buat-video

Buat video materi pelajaran (Matematika & Koding SMPN 1 Damai) sebagai
**HyperFrames (video-as-code)**: LLM menulis HTML+GSAP, headless Chrome
me-render frame, FFmpeg me-mux dengan narasi TTS. Video portrait 9:16,
ditonton murid di HP. Hanya untuk Alfi; jangan bagikan ke murid sebelum
Alfi setuju.

## Konsep (signature, jangan diubah)

- Portrait 9:16, 720x1280. Palet TVA: latar krim #F6EEDC, oranye #FF7A1A,
  teal #2FA08C, mint #A8D8C8, cokelat gelap #2A1F14 (HANYA SATU oranye
  dan SATU teal). Font Plus Jakarta Sans ExtraBold. Neobrutalism ringan
  (border 3px, hard shadow, tanpa blur). TANPA lingkaran.
- Header band oranye full-width 126px (watermark @alfisjahri kiri, chip
  subjek/kelas kanan, pill di tengah vertikal). Footer band teal
  full-width 126px (sama dengan header), berisi pill subtitle di tengah.
- Subtitle karaoke 1-3 kata, verbatim, sinkron Whisper, TIDAK BOLEH
  melewati batas kalimat (. ! ? mengakhiri potongan).
- Detail lengkap: `/home/ubuntu/video-maker/DESIGN_SYSTEM.md` — BACA DULU
  sebelum membuat video.

## Pipeline

1. Terima topik/materi, tulis storyboard 6 scene + naskah narasi ~180 kata.
2. Tulis HTML HyperFrames.
3. Generate narasi TTS (lihat Suara).
4. faster-whisper untuk timestamp kata.
5. Skala timestamp 1/atempo + potongan karaoke ke HTML.
6. Render HyperFrames (headless Chrome).
7. Mux ffmpeg + kirim MP4 ke Alfi.
8. Alfi review; revisi bila diminta.

Perintah persis + script: `/home/ubuntu/video-maker/bin/`
(`gemini_tts_vps.py`, `whisper_words.py`, `apply_karaoke.py`),
referensi: `/home/ubuntu/video-maker/reference/`.
Kerja di `/home/ubuntu/video-maker/`.

## Suara

- Default **Orus** (Gemini TTS, keputusan Alfi 28 Okt — FINAL).
- Cadangan Puck (Gemini). Alternatif Ardi (Edge TTS, tanpa key).
- Hemat TTS: 1 request per video, JANGAN generate sampel berulang
  (kuota Gemini 10/hari). Kunci Gemini TTS di
  `/home/ubuntu/video-maker/.config/gemini-api-key`.

## Aturan

- Selalu tunjukkan video ke Alfi untuk review SEBELUM dianggap selesai.
- Ekspor dan kirim HANYA format MP4 (tanpa MOV dan ZIP).
- Selalu verifikasi frame hasil render (cek label kepotong / teks
  tumpang tindih) sebelum melapor selesai.
- Jangan karang materi. Kalau ragu, tanya Alfi.
- Jangan ganggu agen Guru Mapel / Wali Kelas dan routine mereka.
