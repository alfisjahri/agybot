"""AgyBot - avatar templates (Phase 3).

5 template avatar (ikon SVG, digambar putih di atas lingkaran warna bot).
Ikon memakai path gaya Feather (stroke), jadi dirender dengan stroke putih.
Kalau bot punya foto upload (avatar_image), foto itu yang dipakai, bukan
template. Logo brand AgyBot (logo.svg) tetap terpisah — bukan avatar bot.
"""
import os

# Stroke paths (viewBox 0 0 24 24, fill none, stroke white, width 2).
TEMPLATES = [
    {
        "id": 1,
        "name": "Buku",
        "desc": "Buku terbuka — Guru Mapel",
        "svg": (
            '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
            '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'
        ),
    },
    {
        "id": 2,
        "name": "Clipboard",
        "desc": "Papan klip — Wali Kelas",
        "svg": (
            '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
            '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'
            '<path d="M9 12l2 2 4-4"/>'
        ),
    },
    {
        "id": 3,
        "name": "Play",
        "desc": "Tombol play — Video Maker",
        "svg": (
            '<circle cx="12" cy="12" r="10"/>'
            '<polygon points="10 8 16 12 10 16 10 8"/>'
        ),
    },
    {
        "id": 4,
        "name": "Bintang",
        "desc": "Bintang — Asisten",
        "svg": (
            '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 '
            '12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'
        ),
    },
    {
        "id": 5,
        "name": "Gear",
        "desc": "Roda gigi — slot fleksibel",
        "svg": (
            '<circle cx="12" cy="12" r="3"/>'
            '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 '
            '2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 '
            '2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 '
            '2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 '
            '2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 '
            '2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 '
            '2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 '
            '2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 '
            '1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
        ),
    },
]


def get_template(template_id):
    for t in TEMPLATES:
        if t["id"] == int(template_id):
            return t
    return TEMPLATES[0]


def template_svg(template_id, color="#2FA08C", size=40):
    """Ikon template sebagai SVG inline (stroke putih, di atas warna bot)."""
    t = get_template(template_id)
    return (
        '<svg viewBox="0 0 24 24" width="%d" height="%d" fill="none" '
        'stroke="#ffffff" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" style="background:%s;border-radius:50%%;'
        'padding:7px">%s</svg>' % (size, size, color, t["svg"])
    )


def avatar_html(bot, size=40):
    """HTML avatar bot: foto upload kalau ada, kalau tidak template+warna."""
    img = (bot or {}).get("avatar_image")
    if img:
        return ('<img src="/static/avatars/%s" class="avatar-img" '
                'width="%d" height="%d" alt="">' % (img, size, size))
    color = (bot or {}).get("avatar_color") or "#2FA08C"
    return template_svg((bot or {}).get("avatar_template") or 1, color, size)


def avatar_url(bot):
    """URL foto avatar, atau None kalau pakai template."""
    img = (bot or {}).get("avatar_image")
    return ("/static/avatars/%s" % img) if img else None


def list_templates():
    return [dict(t) for t in TEMPLATES]


# ------------------------------------------------------------------ Phase 8
# Karakter avatar ala DS-Bot (DeepSeek Harness, Apache 2.0) — bentuk blob
# lucu + warna. Daftar ini cerminan dari ds-bot/src/client/characters.js
# (CHARACTERS + CHARACTER_COLORS); render-nya ada di static/ds-avatars.js
# yang mengimpor characters.js/inks.js DS-Bot secara verbatim.
SHAPES = [
    {"id": "whale", "label": "Paus"},
    {"id": "star", "label": "Bintang"},
    {"id": "moon", "label": "Bulan"},
    {"id": "wave", "label": "Ombak"},
    {"id": "squircle", "label": "Squircle"},
    {"id": "zed", "label": "Banteng"},
    {"id": "hex", "label": "Bunga"},
    {"id": "gumdrop", "label": "Gumdrop"},
    {"id": "peanut", "label": "Kacang"},
    {"id": "saucer", "label": "UFO"},
    {"id": "bunny", "label": "Kelinci"},
    {"id": "kitty", "label": "Kucing"},
    {"id": "beacon", "label": "Beacon"},
    {"id": "plus", "label": "Plus"},
    {"id": "magnet", "label": "Magnet"},
    {"id": "acorn", "label": "Biji Ek"},
    {"id": "pebbles", "label": "Kerikil"},
    {"id": "cushion", "label": "Bantal"},
    {"id": "ring", "label": "Cincin"},
    {"id": "gem", "label": "Permata"},
]
SHAPE_IDS = [s["id"] for s in SHAPES]

# Warna DS-Bot (CHARACTER_COLORS): nama warna, bukan hex — render-nya
# memakai var(--bt-ink-<nama>) dari inks.js (nilai gelap untuk tema gelap).
COLORS = [
    {"id": "black", "label": "Hitam"},
    {"id": "brown", "label": "Coklat"},
    {"id": "red", "label": "Merah"},
    {"id": "orange", "label": "Oranye"},
    {"id": "yellow", "label": "Kuning"},
    {"id": "green", "label": "Hijau"},
    {"id": "cyan", "label": "Cyan"},
    {"id": "blue", "label": "Biru"},
    {"id": "violet", "label": "Ungu"},
    {"id": "magenta", "label": "Magenta"},
    {"id": "gray", "label": "Abu-abu"},
    {"id": "aurora", "label": "Aurora"},
]
COLOR_IDS = [c["id"] for c in COLORS]

# Bentuk default tiap bot (dipakai seed.py + migrasi satu kali).
DEFAULT_SHAPES = {
    1: "star",    # Guru Mapel
    2: "moon",    # Wali Kelas
    3: "gumdrop",  # Video Maker
    4: "bunny",   # Asisten
    5: "kitty",   # Bot Cadangan
}


def list_shapes():
    return [dict(s) for s in SHAPES]


def list_colors():
    return [dict(c) for c in COLORS]


def avatar_file_path(base_dir, bot_id, ext):
    return os.path.join(base_dir, "static", "avatars", "bot_%d.%s" % (bot_id, ext))


ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
