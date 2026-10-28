---
name: urutan-materi
description: "Urutan topik pelajaran per mapel per kelas (Matematika 7/8, Koding 8/9): topik yang sedang berjalan, topik berikutnya, dan aturan kapan maju ke topik selanjutnya. Pakai skill ini setiap kali menentukan materi pelajaran berikutnya, sebelum membuat Form kuis atau saat Alfi bertanya materi selanjutnya. Koding 9 tidak punya buku — topik berikutnya ditentukan Alfi."
example-prompt: "Materi selanjutnya untuk Matematika Kelas 8 apa?"
---

# Urutan Materi

## Hasil yang diharapkan
Topik pelajaran berikutnya yang benar untuk tiap kelas, dengan posisi yang tercatat sehingga Routine berikutnya tidak mengulang topik yang sama.

## Posisi saat ini (26 Okt 2026)
- M7 (Matematika 7): Bab 1 Bilangan, 1.7 Bilangan Pecahan Negatif
- M8 (Matematika 8): Bab 3 Fungsi Linear, 3B Gradien Fungsi Linear
- K8 (Koding 8): Bab 2 Menulis Kode, 2B Pemrograman Visual dengan Scratch
- K9 (Koding 9): Rekursi (tidak ada buku paket)

## Posisi saat ini (28 Okt 2026, hasil migrasi OpenBot → AgyBot — terverifikasi dari thread Guru)
- M7: 1.8 Sifat Operasi dan Urutan Operasi (diajarkan Sel 27 Okt, Form forms.gle/dKcFhaGYqd8i5eMz7) → berikut 1.9 Persentase
- M8: 3C Hubungan Dua Garis Lurus (diajarkan 27-28 Okt) → berikut 3D Menentukan Persamaan Garis Lurus. Form 3D SUDAH ADA (https://forms.gle/rbNZRhr7tXaxarS4A, terverifikasi total 100) — pakai itu, JANGAN buat duplikat.
- K8: 2B Scratch (pertemuan terakhir di rekap: 15 Okt) → cek Form Koding 8 terakhir dulu, lalu maju SATU langkah (2C Python kalau 2B sudah tuntas)
- K9: Rekursi (26 Okt) → berikut DITENTUKAN ALFI, jangan maju sendiri

## Urutan topik
- **M7 Bab 1 Bilangan**: 1.1 Bilangan Bulat → 1.2 Penjumlahan & Pengurangan Bilangan Bulat → 1.3 Perkalian & Pembagian Bilangan Bulat → 1.4 Bilangan Berpangkat → 1.5 Pecahan dan Lambangnya → 1.6 Operasi Hitung pada Pecahan → 1.7 Bilangan Pecahan Negatif → 1.8 Sifat Operasi dan Urutan Operasi → 1.9 Persentase → 1.10 Bilangan Desimal → 1.11 Bentuk Baku → Bab 2 Aljabar → Bab 3 Himpunan → Bab 4 Persamaan & Pertidaksamaan Linear Satu Variabel → Bab 5 Perbandingan → Bab 6 Aritmetika Sosial → Bab 7 Sudut & Garis Sejajar → Bab 8 Bangun Datar.
- **M8 Bab 3 Fungsi Linear**: A. Mengenal Fungsi Linear → B. Gradien Fungsi Linear → C. Hubungan Dua Garis Lurus → D. Menentukan Persamaan Garis Lurus → E. Menyelesaikan Permasalahan yang Melibatkan Fungsi Linear → Evaluasi Akhir Bab 3 → Bab 4 SPLDV → Bab 5 Teorema Pythagoras → Bab 6 Lingkaran → Bab 7 Bangun Ruang Sisi Datar.
- **K8 Bab 2 Menulis Kode**: A. Struktur Dasar Program → B. Pemrograman Visual dengan Scratch → C. Program Sederhana dengan Python → Bab 3 Etika & Keamanan Digital → Bab 4 Konten Audio & Video Digital → Bab 5 Prinsip Kerja & Dampak AI → Bab 6 AI untuk Kegiatan Sederhana.
- **K9 (tanpa buku)**: Tree & Graph → Algoritma Greedy → Rekursi → (berikutnya ditentukan Alfi).

## Aturan maju ke topik berikutnya
1. Topik berikutnya = item tepat setelah posisi saat ini di urutan di atas.
2. Posisi dicatat di Memory ("Posisi materi: M7=..., M8=..., K8=..., K9=..."). Kalau Memory posisi belum ada, pakai "Posisi saat ini" di skill ini. Setelah Form untuk topik berjalan selesai dibuat, terverifikasi, dan pelajarannya sudah berjalan, simpan posisi baru sebagai Memory. Routine berikutnya membaca posisi dari Memory — bukan menebak.
3. Kalau Alfi bilang review / ulang / remedial, atau menyebut topik lain: pakai topik itu. JANGAN maju, JANGAN ubah posisi.
4. Kalau mendekati akhir Bab, beri tahu Alfi (Bab hampir selesai; topik Bab berikutnya adalah ...) supaya Alfi bisa putuskan evaluasi bab dulu atau langsung lanjut.
5. **K9: JANGAN maju sendiri.** Tidak ada buku yang menentukan lanjutannya. Usulkan kandidat ke Alfi (sisa Bab K8 yang belum dipakai: Etika Digital, Audio/Video, AI; atau pendalaman algoritma) dan TANYA Alfi, atau pakai topik yang Alfi sebutkan. Tanyakan jauh-jauh hari (saat review mingguan atau briefing pagi), jangan menunggu 1 jam sebelum kelas.

## Alur kerja (konfirmasi di Form jadi)
Begitu topik diketahui, LANGSUNG buat materi + gambar + soal menjadi Google Form (pakai skill buat-form-kuis) — tanpa tanya/konfirmasi dulu soal topiknya. Konfirmasi Alfi terjadi SETELAH Form jadi: kirim link Form ke Alfi untuk dicek sebelum dibagikan ke murid. Kalau Alfi bilang topiknya salah atau minta review, buat ulang dengan topik yang benar dan jangan ubah posisi.

## Batasan
- Jangan mengarang urutan di luar buku. Urutan di atas berasal dari daftar isi buku Alfi.
- Keputusan topik selalu di tangan Alfi; skill ini hanya menunjukkan urutan dan mengusulkan.

## Cara verifikasi (SEBELUM lapor selesai)
- Topik yang dipakai = posisi + 1 di urutan, atau topik yang Alfi sebutkan secara eksplisit.
- Posisi baru sudah disimpan sebagai Memory (kecuali kalau Alfi minta review/ulang).
- Form yang dibuat sudah melewati verifikasi skill buat-form-kuis, dan linknya sudah dikirim ke Alfi.
