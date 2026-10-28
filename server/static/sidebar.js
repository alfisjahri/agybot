// AgyBot — shared sidebar (Phase 6: dark theme, avatar karakter "hidup";
// Phase 8: avatar karakter ala DS-Bot, blob + warna).
// Used by the Routines and Usage pages so all pages share the same shell:
// brand, bot list, page nav. Clicking a bot goes to Chat with that bot
// selected (via ?bot=<id>).
// ES module: mengimpor ./ds-avatars.js (aset karakter DS-Bot).
import { dsAvatarHTML } from './ds-avatars.js';

async function sidebarApi(path) {
  const r = await fetch(path);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

function sidebarEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Karakter default tiap bot (cermin avatars.py DEFAULT_SHAPES).
const SIDEBAR_DEFAULT_SHAPES = { 1: "star", 2: "moon", 3: "gumdrop", 4: "bunny", 5: "kitty" };

function sidebarAvatar(b) {
  if (b.avatar_image) {
    return `<img class="avatar-img" src="/static/avatars/${sidebarEsc(b.avatar_image)}" alt="">`;
  }
  const shape = b.avatar_shape || SIDEBAR_DEFAULT_SHAPES[b.id] || "gumdrop";
  const color = b.avatar_color || "#2FA08C";
  return dsAvatarHTML(shape, color, 36);
}

function sidebarGuardRail() {
  const frame = document.getElementById("frame");
  if (frame && window.innerWidth <= 760) frame.removeAttribute("data-rail");
}

async function sidebarInit() {
  const btn = document.getElementById("collapse-btn");
  if (btn) btn.addEventListener("click", () => {
    if (window.innerWidth <= 760) return; // rail tidak ada di HP
    document.getElementById("frame").toggleAttribute("data-rail");
  });
  sidebarGuardRail();
  window.addEventListener("resize", sidebarGuardRail);
  const el = document.getElementById("bot-list");
  if (!el) return;
  try {
    const bots = await sidebarApi("/api/bots");
    bots.forEach(b => {
      const d = document.createElement("button");
      d.type = "button";
      d.className = "bot-item";
      d.innerHTML = `${sidebarAvatar(b)}
        <div class="who">
          <div class="name-row"><span class="name">${sidebarEsc(b.name)}</span><span class="dot live" title="Siap"></span></div>
        </div>`;
      d.onclick = () => { window.location.href = "/?bot=" + b.id; };
      el.appendChild(d);
    });
  } catch (e) { /* sidebar bot list is a nicety; page still works */ }
}

document.addEventListener("DOMContentLoaded", sidebarInit);
