---
name: cek-belum-mengerjakan
description: "Cek siapa yang sudah dan belum mengerjakan Form pelajaran hari itu dengan membandingkan nama pengirim Form dengan daftar nama resmi kelas, lalu laporkan hasilnya dalam format singkat yang siap disalin ke grup WhatsApp. Pakai skill ini saat Routine cek sebelum deadline berjalan atau saat Alfi minta daftar yang belum mengerjakan."
example-prompt: "Cek siapa yang belum mengerjakan Form Matematika 8A hari ini."
---

# Cek Belum Mengerjakan

## Hasil yang diharapkan
Daftar yang SUDAH dan yang BELUM mengerjakan per kelas, nama lengkap sesuai daftar resmi, dalam format singkat yang siap disalin ke grup WhatsApp (mapel + tanggal, daftar yang belum).

## Alur kerja
1. **Input**: kelas, tanggal pertemuan (WITA), dan data jawaban Form hari itu (nama pengirim + nilai).
2. **Bandingkan** nama pengirim dengan daftar nama resmi kelas itu di Files / Tables.
3. **Toleransi typo kecil dan nama panggilan** (contoh: M.raffa stiawan = Muhammad Raffa Setiawan).
4. **Nama tidak jelas / tidak ada di daftar: JANGAN ditebak.** Tulis di daftar terpisah "perlu dicek manual".
5. **Nama kembar / kakak-adik**: Giviansyah Nehemia Reyhan (8A) dan Givriansyah Nathaiel Renaldy (Kelas 7) adalah dua orang berbeda, jangan disamakan.
6. **Entri tes bukan murid**: nama TES, "Tes Siswa", "Tes Muse", atau nama Alfi sendiri dikecualikan dari daftar.
7. **Kalau data jawaban hari itu belum diunggah**, katakan datanya belum ada, jangan karang daftarnya.

## Batasan
- Jangan mengarang nama atau daftar. Kalau ragu soal satu nama, masukkan ke "perlu dicek manual", jangan ditebak.

## Cara verifikasi (SEBELUM lapor selesai)
- Jumlah sudah + belum + perlu dicek manual = jumlah murid kelas itu.
- Tidak ada nama yang ditebak — semua nama yang tidak cocok ada di "perlu dicek manual".
- Format laporan singkat dan siap salin ke WhatsApp.
