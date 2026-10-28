"""Seed AgyBot routines from Alfi's real workflow (idempotent: only seeds
when the routines table is empty). ALL routines are DISABLED by default —
Alfi enables the ones he wants from the Routines UI.

Schedules use Alfi's timetable (Jadwal-Mengajar-Alfi.csv, WITA):
- BUAT SOAL: 1 jam sebelum kelas dimulai.
- CEK: 10 menit sebelum kelas berakhir.
- Wali Kelas: 07:35 + 13:35 (Senin-Sabtu).
- PTMT: Rabu + Kamis 08:30. Kokurikuler: CEK Sel/Rab/Kam 12:55, rekap Jumat 10:00.
"""
import os
import time

import routines
import store

MON_SAT = "mon,tue,wed,thu,fri,sat"

CEK_RULES = (
    "Terapkan 3 aturan CEK: (1) gagal baca data/kosong BUKAN berarti 0 submit "
    "— baca ulang sekali, kalau tetap gagal laporkan 'Data Form tidak bisa "
    "dibaca, cek manual' tanpa daftar; (2) hasil '0 submit' mencurigakan — "
    "baca ulang sekali; (3) cross-check submit + belum + manual = jumlah "
    "roster. Abaikan entri tes ('Tes Siswa', 'Tes Muse', 'muse alias jolly')."
)

PROMPT_WALI_PAGI = (
    "Rekap absensi 8A PAGI. Langkah: (1) baca kunci wali dari "
    "/home/ubuntu/agybot/data/secrets.json (JSON, key WALI_KEY) — JANGAN "
    "tampilkan kuncinya. (2) ambil data: curl "
    "'http://127.0.0.1:8503/api/wali/data?key=<WALI_KEY>'. (3) VERIFIKASI: "
    "total hadir + alpa + sakit + izin HARUS = 18 (siswa 8A). Kalau tidak 18, "
    "laporkan ada yang aneh dan jangan klaim angka final. (4) Laporkan: hadir "
    "X, alpa Y (sebut nama yang alpa), sakit/izin bila ada. Format ringkas."
)
PROMPT_WALI_SIANG = PROMPT_WALI_PAGI.replace("PAGI", "SIANG")


def buat_soal_prompt(kelas, mapel, materi):
    return (
        "Buat soal kuis untuk kelas %s %s hari ini. Materi: %s. Langkah: "
        "(1) tulis ringkasan materi singkat + 5 soal pilihan ganda (total 100 "
        "poin, 20/soal) dengan kunci jawaban. (2) tulis file JSON kuis ke "
        "work/kuis-%s-%s.json (format gas_webapp.py: {title, description, "
        "materi, kelas, questions:[{text, choices[], correctIndex, points}]}). "
        "(3) buat Form: python3 /home/ubuntu/guru-tools/gas_webapp.py "
        "work/kuis-%s-%s.json. (4) verifikasi shortUrl hidup (curl -sI, harus "
        "200/301). (5) simpan formId + shortUrl ke data/latest_forms.json "
        "supaya routine CEK bisa menemukannya. (6) laporkan shortUrl + judul "
        "Form + kunci jawaban (kunci HANYA untuk Alfi, bukan murid). JANGAN "
        "duplikasi Form yang sudah terverifikasi hari ini (cek dulu "
        "data/latest_forms.json)." % (kelas, mapel, materi, kelas.lower(),
        mapel.lower(), kelas.lower(), mapel.lower())
    )


def cek_prompt(kelas, mapel):
    return (
        "Cek siapa yang belum mengerjakan kuis %s %s hari ini. Langkah: "
        "(1) baca data/latest_forms.json untuk formId kuis hari ini (cari "
        "entri routine BUAT SOAL %s %s tanggal hari ini); kalau tidak ada, "
        "resolve shortUrl dari chat/rekap (curl -sI, ambil formId dari "
        "Location); kalau tetap tidak ada, laporkan 'Belum ada Form hari ini, "
        "cek manual'. (2) baca respons: python3 "
        "/home/ubuntu/guru-tools/forms_api.py responses <FORM_ID>. (3) %s "
        "(4) Laporkan daftar yang belum mengerjakan, format siap tempel ke "
        "grup WhatsApp." % (kelas, mapel, kelas, mapel, CEK_RULES)
    )


PROMPT_PTMT_RABU = (
    "PTMT hari ini (Rabu): 9B 09:00-09:30, 8B 09:30-10:00, 7 10:00-10:30. "
    "Langkah 1 REKAP: untuk tiap kelas PTMT hari ini, baca respons Form kuis "
    "terbaru (via forms_api.py responses <FORM_ID>, formId dari "
    "data/latest_forms.json atau chat) dan hitung skor PERTAMA tiap siswa "
    "(jangan timpa/rata-rata); susulan masuk kolom tanggal pertemuan ASAL + "
    "kuning + catatan tanggal susulan. Laporkan skor yang harus dilipat ke "
    "rekap (file: /var/lib/openbot/OpenBot/Shared/Rekap nilai dan kehadiran "
    "BDR terbaru.xlsx — kalau tidak bisa tulis, laporkan saja skornya). "
    "Langkah 2 SUSULAN: daftar nama + tanggal pertemuan yang belum "
    "dikerjakan (kumulatif), dipisah per mapel. " + CEK_RULES
)
PROMPT_PTMT_KAMIS = PROMPT_PTMT_RABU.replace(
    "Rabu): 9B 09:00-09:30, 8B 09:30-10:00, 7 10:00-10:30",
    "Kamis): 9A 09:00-09:30, 8A 09:30-10:00")

PROMPT_CEK_KOKUR = (
    "CEK Kokurikuler Numerasi TP5 hari ini (semua kelas: 7, 8A, 8B, 9A, 9B = "
    "98 siswa). Form Kokurikuler: P1 "
    "17L7mmkA1h60rs__tjmLOv9I-TVnmzBGYLwpfCAzHONg (27 Okt), P2 "
    "100_mVz3YC_9wiaWQpmEu2A56wbQ6WROsBZoX9EsjDxU (28 Okt), P3 "
    "12vfmVzQUhklV-Hl4qecpUKnUPBQwxPzEB8aziZ6pg1k (29 Okt) — pakai Form "
    "tanggal hari ini; kalau sudah lewat minggu itu, cari Form terbaru dari "
    "chat/rekap. Baca respons via forms_api.py. " + CEK_RULES +
    " Laporkan yang belum mengerjakan DIPISAH PER KELAS, format siap tempel "
    "ke grup WhatsApp."
)
PROMPT_REKAP_KOKUR = (
    "Rekap Kokurikuler Numerasi TP5 (file 'Rekap Kokurikuler Numerasi TP5.xlsx' "
    "di Shared Guru, 5 sheet, kolom P1 27 Okt + P2 28 Okt + P3 29 Okt + "
    "Jumlah). Baca respons Form P1/P2/P3 via forms_api.py (formId lihat "
    "prompt CEK Kokurikuler), lipat skor PERTAMA tiap siswa ke sheet yang "
    "sesuai. Laporkan ringkasan per kelas + yang belum mengerjakan. Kalau "
    "file xlsx tidak bisa ditulis, laporkan skor yang harus dilipat."
)

# (name, bot_id, days, time, prompt)
ROUTINES = [
    ("Rekap absensi 8A — pagi", 2, MON_SAT, "07:35", PROMPT_WALI_PAGI),
    ("Rekap absensi 8A — siang", 2, MON_SAT, "13:35", PROMPT_WALI_SIANG),
    # BUAT SOAL (1 jam sebelum kelas) — Senin
    ("BUAT SOAL — 9B Koding (Senin)", 1, "mon", "07:10",
     buat_soal_prompt("9B", "Koding", "Rekursi (Koding 9, tanpa buku — improvisasi dari Koding 8)")),
    ("BUAT SOAL — 9A Koding (Senin)", 1, "mon", "10:45",
     buat_soal_prompt("9A", "Koding", "Rekursi (Koding 9, tanpa buku — improvisasi dari Koding 8)")),
    # BUAT SOAL — Selasa
    ("BUAT SOAL — 8A Matematika (Selasa)", 1, "tue", "07:50",
     buat_soal_prompt("8A", "Matematika", "Bab 3 Fungsi Linear — lanjutkan dari materi terakhir (Hubungan Dua Garis Lurus)")),
    ("BUAT SOAL — 7 Matematika (Selasa)", 1, "tue", "09:25",
     buat_soal_prompt("7", "Matematika", "Bab 1 Bilangan, 1.7 Pecahan Negatif — lanjutkan sesuai urutan bab")),
    # BUAT SOAL — Rabu
    ("BUAT SOAL — 8B Matematika (Rabu)", 1, "wed", "09:25",
     buat_soal_prompt("8B", "Matematika", "Bab 3 Fungsi Linear, 3B Gradien — lanjutkan dari materi terakhir")),
    # BUAT SOAL — Kamis
    ("BUAT SOAL — 8B Koding (Kamis)", 1, "thu", "07:50",
     buat_soal_prompt("8B", "Koding", "Bab 2, 2B Scratch — lanjutkan dari materi terakhir")),
    ("BUAT SOAL — 7 Matematika (Kamis)", 1, "thu", "09:25",
     buat_soal_prompt("7", "Matematika", "Bab 1 Bilangan — lanjutkan sesuai urutan bab")),
    # BUAT SOAL — Jumat
    ("BUAT SOAL — 8A Matematika (Jumat)", 1, "fri", "06:30",
     buat_soal_prompt("8A", "Matematika", "Bab 3 Fungsi Linear — lanjutkan dari materi terakhir")),
    # BUAT SOAL — Sabtu
    ("BUAT SOAL — 8B Matematika (Sabtu)", 1, "sat", "06:30",
     buat_soal_prompt("8B", "Matematika", "Bab 3 Fungsi Linear — lanjutkan dari materi terakhir")),
    ("BUAT SOAL — 8A Koding (Sabtu)", 1, "sat", "07:50",
     buat_soal_prompt("8A", "Koding", "Bab 2, 2B Scratch — lanjutkan dari materi terakhir")),
    # CEK (10 menit sebelum kelas berakhir)
    ("CEK — 9B Koding (Senin)", 1, "mon", "09:20", cek_prompt("9B", "Koding")),
    ("CEK — 9A Koding (Senin)", 1, "mon", "12:55", cek_prompt("9A", "Koding")),
    ("CEK — 8A Matematika (Selasa)", 1, "tue", "10:00", cek_prompt("8A", "Matematika")),
    ("CEK — 7 Matematika (Selasa)", 1, "tue", "11:35", cek_prompt("7", "Matematika")),
    ("CEK — 8B Matematika (Rabu)", 1, "wed", "11:35", cek_prompt("8B", "Matematika")),
    ("CEK — 8B Koding (Kamis)", 1, "thu", "10:00", cek_prompt("8B", "Koding")),
    ("CEK — 7 Matematika (Kamis)", 1, "thu", "11:35", cek_prompt("7", "Matematika")),
    ("CEK — 8A Matematika (Jumat)", 1, "fri", "08:40", cek_prompt("8A", "Matematika")),
    ("CEK — 8B Matematika (Sabtu)", 1, "sat", "08:40", cek_prompt("8B", "Matematika")),
    ("CEK — 8A Koding (Sabtu)", 1, "sat", "10:00", cek_prompt("8A", "Koding")),
    # PTMT + Kokurikuler
    ("PTMT — rekap + susulan (Rabu)", 1, "wed", "08:30", PROMPT_PTMT_RABU),
    ("PTMT — rekap + susulan (Kamis)", 1, "thu", "08:30", PROMPT_PTMT_KAMIS),
    ("CEK Kokurikuler (Sel/Rab/Kam)", 1, "tue,wed,thu", "12:55", PROMPT_CEK_KOKUR),
    ("Rekap Kokurikuler (Jumat)", 1, "fri", "10:00", PROMPT_REKAP_KOKUR),
]


def seed(db_path):
    store.init_db(db_path)
    routines.init_routines_db(db_path)
    if routines.list_routines(db_path):
        print("routines already seeded, skipping")
        return
    for name, bot_id, days, time_hhmm, prompt in ROUTINES:
        routines.create_routine(db_path, {
            "name": name, "bot_id": bot_id, "days": days,
            "time_hhmm": time_hhmm, "prompt": prompt, "enabled": 0,
        })
    print("seeded %d routines (all disabled)" % len(ROUTINES))


if __name__ == "__main__":
    db = os.environ.get("AGYBOT_DB", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "agybot.db"))
    seed(db)
