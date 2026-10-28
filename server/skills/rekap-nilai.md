---
name: rekap-nilai
description: "Perbarui file rekap nilai dan kehadiran (rekap_nilai___kehadiran_BDR.xlsx) dari jawaban Google Form: masukkan nilai ke kolom tanggal pertemuan yang benar, tandai susulan dengan warna kuning dan catatan tanggal, tambah kolom tanggal baru bila perlu, dan jangan pernah menimpa nilai lama. Pakai skill ini setiap kali Alfi minta rekap harian atau memasukkan nilai Form ke rekap."
example-prompt: "Masukkan nilai Form Matematika Kelas 7 tanggal 20 Oktober ke rekap."
---

# Rekap Nilai dan Kehadiran

## Hasil yang diharapkan
File rekap_nilai___kehadiran_BDR.xlsx terisi benar: nilai masuk kolom tanggal pertemuan yang tepat, susulan ditandai kuning + catatan, tanpa satu pun nilai lama tertimpa.

## Alur kerja
1. **File**: rekap_nilai___kehadiran_BDR.xlsx, 5 sheet: Kelas 7, 8A, 8B, 9A, 9B. Baris = murid, kolom = tanggal pertemuan, isi = nilai 0-100, kosong = belum mengumpulkan / tidak hadir.
2. **Mapel per kelas**: Kelas 7 = Matematika. 8A dan 8B = Matematika + Koding (dua blok terpisah). 9A dan 9B = Koding.
3. **Sumber nilai HANYA dari Google Form**, jangan karang nilai.
4. **Nilai pertama**: kalau satu murid mengirim lebih dari satu kali, pakai nilai PERTAMA. Jangan timpa, jangan rata-rata.
5. **Susulan**: kalau tanggal kirim (WITA) berbeda dengan tanggal pertemuan, itu susulan. Nilainya tetap masuk kolom TANGGAL PERTEMUAN, beri warna kuning (FFFF00), dan di bawah tabel beri catatan: nama depan murid + tanggal susulan di bawah kolom tanggal pertemuan yang sama. Terlambat beberapa jam di hari yang sama BUKAN susulan.
6. **Tanggal baru**: tambah kolom baru di akhir blok mapel itu, sebelum kolom hitung (count) kalau ada. Jangan timpa kolom lama, jangan ubah rumus count dan merge header.
7. **Tanggal pertemuan tiap kelas** dilihat dari hari jawaban kelas itu sendiri (tanggal yang paling banyak muncul). Jangan asumsikan kelas A selalu tanggal pertama (contoh pengecualian: Koding Kelas 8 tanggal 15 dan 17 Okt, 8B = 15 Okt, 8A = 17 Okt).
8. **Nama kembar / kakak-adik**: Giviansyah Nehemia Reyhan (8A) dan Givriansyah Nathaiel Renaldy (Kelas 7) adalah dua orang berbeda, jangan disamakan.
9. **Sebelum mengubah file rekap**, tunjukkan dulu perubahan yang akan dibuat dan tunggu persetujuan Alfi.
10. **Jangan ubah nilai lama tanpa perintah Alfi**. Kalau ada nilai di rekap yang berbeda dengan nilai Form, laporkan dan jangan langsung diubah.

## Batasan
- Kalau Form tidak memberi totalScore dan semua nilai per soal kosong, jangan tulis 0 dulu, tanyakan ke Alfi. Nilai 0 yang benar adalah nilai 0, bukan kosong.
- Jangan mengarang nama, nilai, atau tanggal.

## Cara verifikasi (SEBELUM lapor selesai)
- Baca kembali sel yang diubah: nilai, kolom tanggal, warna kuning susulan, dan catatan tanggal susulan semuanya sesuai.
- Pastikan tidak ada nilai lama yang tertimpa dan rumus count masih benar.
- Laporkan ringkasan perubahan ke Alfi (kelas, tanggal, berapa nilai masuk, berapa susulan).
