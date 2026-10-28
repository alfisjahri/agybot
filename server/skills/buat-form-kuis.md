# buat-form-kuis (GAS Web App)

Buat Google Form kuis lewat **GAS Web App** (Google Apps Script), BUKAN lewat browser dan BUKAN lewat Forms API.
Alasan: Form yang dibuat GAS **tidak memunculkan nilai otomatis** ke murid (terbukti dites 2x), dan Web App memberi **short link forms.gle**. Forms API membuat nilai langsung muncul ("Immediately after each submission") — JANGAN pakai Forms API untuk membuat Form.

## Cara membuat Form

1. Tulis spesifikasi kuis sebagai JSON ke file, misal `/tmp/kuis-<topik>.json`:
```json
{
  "title": "Matematika Kelas 8: <Judul Materi>",
  "description": "<deskripsi singkat, bukan untuk murid>",
  "materi": "<nama materi>",
  "kelas": ["8A", "8B"],
  "questions": [
    {"text": "<soal>", "choices": ["A. ...", "B. ...", "C. ...", "D. ..."], "correctIndex": 0, "points": 20}
  ]
}
```
Aturan isi:
- Total poin HARUS 100 (4 soal = 25 tiap soal, 5 soal = 20 tiap soal).
- `correctIndex` = indeks jawaban benar (0 = pilihan pertama).
- `kelas` = kelas yang memakai Form ini (untuk soal Kelas di Form).
- Selalu sertakan field Nama lengkap + Kelas + Materi (helper yang menambahkan otomatis dari data ini).
- Jangan sertakan email (email tidak dikumpulkan).

2. Jalankan helper (validasi lokal dulu, lalu POST ke Web App GAS):
```
python3 /home/ubuntu/guru-tools/gas_webapp.py /tmp/kuis-<topik>.json
```
Helper mengembalikan JSON: `{"formId": "...", "editUrl": "...", "publishedUrl": "...", "shortUrl": "https://forms.gle/..."}`.
Kalau gagal, helper mengembalikan `{"error": "..."}` dan exit 1 — baca pesannya, perbaiki JSON, ulangi. JANGAN lanjut kalau ada error.

3. Verifikasi hasil (WAJIB sebelum melapor ke Alfi):
```
python3 /home/ubuntu/guru-tools/forms_api.py get <formId>
```
Pastikan: total poin 100, setiap soal ada kunci yang cocok dengan salah satu pilihan, semua soal Required, email tidak dikumpulkan, isQuiz true. Kalau ada yang kurang, perbaiki dan buat ulang (jangan edit Form yang sudah jadi secara manual).

4. Laporkan ke Alfi: kirim **short link (forms.gle) sebagai PLAIN TEXT** (bukan hyperlink markdown), beserta formId dan judul. Jangan bagikan Form ke murid sebelum Alfi memeriksa.

## Yang TIDAK boleh dilakukan
- JANGAN buat Form lewat browser (Apps Script di browser) — lambat (~7 menit) dan boros token.
- JANGAN buat Form lewat Forms API (`forms_api.py create`) — nilainya langsung muncul ke murid.
- JANGAN ubah Web App URL atau kredensial di `/home/ubuntu/guru-tools/`. URL Web App GAS sudah benar dan teruji.
- JANGAN membuat Form duplikat: kalau Form yang sudah terverifikasi untuk materi+kelas+hari itu sudah ada, laporkan link yang sudah ada, jangan buat baru.

## Membaca respons (untuk CEK / rekap)
Pakai Forms API (baca saja, bukan membuat):
```
python3 /home/ubuntu/guru-tools/forms_api.py responses <formId>
```
Aturan CEK 3 verifikasi tetap berlaku (baca gagal/0 bukan berarti 0 submitted; cross-check submitted+missing+manual = jumlah roster).
