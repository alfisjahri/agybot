// AgyBot — Chat UI (Phase 6: dark theme ala DS-Bot layout,
// karakter bot "hidup" — wajah ekspresif + mata berkedip + dot
// kehadiran berdenyut + indikator mengetik beravatar; rail sidebar
// dinonaktifkan total di HP; rumus $...$ dirender sebagai math.
// Phase 8: avatar karakter ala DS-Bot (blob + color picker),
// header atas terpusat, KaTeX lokal.)
// ES module: mengimpor ./ds-avatars.js (aset karakter DS-Bot).
import { dsAvatarHTML, dsShapeRing, paintCss, inkHex } from './ds-avatars.js';

let bots = [];
let currentBot = null;
let models = [];
let efforts = [];
let modelEfforts = {};
let pendingImage = null;
let avatarShapes = [];
let avatarColors = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* Label model singkat untuk pill header (di HP "gemini-3.8-flash"
   kepotong jadi "gemini-3..."). Nama lengkap tetap di settings. */
function shortModel(m) {
  const map = {
    "gemini-3.8-flash": "Flash", "gemini-4-argon": "Argon",
    "claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5",
    "gpt-oss-120b": "GPT-OSS",
  };
  return map[m] || m;
}

/* ---- Avatar karakter ala DS-Bot (Phase 8) ----
   Blob lucu + warna dari DS-Bot (aset karakter + inks DS-Bot,
   Apache 2.0 — lihat static/ds/). Foto upload tetap didahulukan
   kalau ada. Bentuk + warna bot tersimpan di avatar_shape /
   avatar_color; kalau kosong, pakai default per bot di bawah. */
const DEFAULT_SHAPES = { 1: "star", 2: "moon", 3: "gumdrop", 4: "bunny", 5: "kitty" };
const DEFAULT_COLORS = { 1: "#2FA08C", 2: "#1F7AE0", 3: "#FF7A1A", 4: "#7B5CFF", 5: "#2FA08C" };
function avatarHtml(b, size, avState) {
  if (b.avatar_image) {
    return `<img class="avatar-img" src="/static/avatars/${esc(b.avatar_image)}" alt="" style="width:${size || 40}px;height:${size || 40}px">`;
  }
  const shape = b.avatar_shape || DEFAULT_SHAPES[b.id] || "gumdrop";
  const color = b.avatar_color || "#2FA08C";
  return dsAvatarHTML(shape, color, size || 40, avState || "idle");
}

function fmtClock(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

/* ---- Markdown ringan (aman: escape dulu, baru format) ----
   Phase 6: rumus $...$ / $$...$$ dirender sebagai math (serif miring),
   bukan teks mentah "$g$" seperti di screenshot Alfi. Isi yang diawali
   angka (harga dolar, mis. $8.38) dibiarkan apa adanya. */
function stashMath(c, stash, display) {
  if (/^\d/.test(c.trim())) return "$" + c + "$";
  stash.push('<span class="math' + (display ? " display" : "") + '">' + c + "</span>");
  return "\u0000" + (stash.length - 1) + "\u0000";
}
function mdInline(s) {
  const stash = [];
  let t = s
    .replace(/\$\$([^$\n]+?)\$\$/g, (m, c) => stashMath(c, stash, true))
    .replace(/\$([^$\n]+?)\$/g, (m, c) => stashMath(c, stash, false));
  t = t.split(/(`[^`]*`)/g).map(part => {
    if (part.startsWith("`") && part.length > 1) return "<code>" + part.slice(1, -1) + "</code>";
    return part
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\W)\*([^*]+)\*/g, "$1<em>$2</em>");
  }).join("");
  return t.replace(/\u0000(\d+)\u0000/g, (m, i) => stash[+i]);
}
function renderMarkdown(text) {
  const lines = esc(text || "").split("\n");
  let html = "";
  let inList = null; // "ul" | "ol" | null
  const closeList = () => { if (inList) { html += "</" + inList + ">"; inList = null; } };
  // Tabel Markdown: baris "| a | b |" + baris pemisah "|---|---|".
  const tableRow = (line) => {
    const t = (line || "").trim();
    if (!t.includes("|")) return null;
    let cells = t.split("|").map(c => c.trim());
    if (cells[0] === "") cells.shift();
    if (cells.length && cells[cells.length - 1] === "") cells.pop();
    return cells.length ? cells : null;
  };
  const isSep = (line) => {
    const cells = tableRow(line);
    return !!cells && cells.length > 0 && cells.every(c => /^:?-{3,}:?$/.test(c));
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const h3 = line.match(/^###\s+(.*)$/);
    const h2 = line.match(/^##\s+(.*)$/);
    const ul = line.match(/^[-*•]\s+(.*)$/);
    const ol = line.match(/^(\d+)[.)]\s+(.*)$/);
    // Blok tabel: baris header + baris pemisah, lalu baris-baris isi.
    if (tableRow(line) && i + 1 < lines.length && isSep(lines[i + 1])) {
      closeList();
      const header = tableRow(line);
      html += '<div class="table-wrap"><table><thead><tr>';
      for (const c of header) html += `<th>${mdInline(c)}</th>`;
      html += '</tr></thead><tbody>';
      i += 2;
      while (i < lines.length) {
        const row = tableRow(lines[i]);
        if (!row) break;
        html += '<tr>';
        for (const c of row) html += `<td>${mdInline(c)}</td>`;
        html += '</tr>';
        i++;
      }
      html += '</tbody></table></div>';
      i--;
      continue;
    }
    if (h3 || h2) {
      closeList();
      html += h3 ? `<h3>${mdInline(h3[1])}</h3>` : `<h2>${mdInline(h2[1])}</h2>`;
    } else if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      if (inList !== tag) { closeList(); html += tag === "ol" ? '<ol style="list-style:none">' : "<ul>"; inList = tag; }
      if (ol) {
        html += `<li><span style="display:inline-block;min-width:1.6em">${ol[1]}.</span> ${mdInline(ol[2])}</li>`;
      } else {
        html += `<li>${mdInline(ul[1])}</li>`;
      }
    } else if (line === "") {
      closeList();
    } else {
      closeList();
      html += `<p>${mdInline(line)}</p>`;
    }
  }
  closeList();
  return html || "<p></p>";
}

/* ---- KaTeX lokal (Phase 8) ----
   Rumus $...$ / $$...$$ dirender jadi matematika beneran (KaTeX
   0.16.11, disajikan lokal dari /static/katex/, tanpa CDN).
   Penjaga harga dolar tetap di stashMath: "$8.38" tidak pernah
   masuk stash, jadi tidak pernah dirender sebagai rumus. */
function renderMath(container) {
  if (!window.katex || !container) return;
  container.querySelectorAll(".math").forEach(el => {
    try {
      window.katex.render(el.textContent, el, {
        displayMode: el.classList.contains("display"),
        throwOnError: false,
      });
    } catch (e) { /* biarkan teks mentah kalau KaTeX gagal */ }
  });
}

/* ---- Bot picker MINIMALIS (Phase 7): avatar + nama + dot saja.
   Tagline/chip/effort TIDAK tampil di daftar — chat yang mendominasi
   layar. Tagline tetap ada di pill header (via settings) & settings. ---- */
function renderBotList() {
  const el = document.getElementById("bot-list");
  if (!el) return;
  el.querySelectorAll(".bot-item").forEach(n => n.remove());
  bots.forEach(b => {
    const d = document.createElement("button");
    d.type = "button";
    d.className = "bot-item" + (currentBot && b.id === currentBot.id ? " active" : "");
    d.setAttribute("aria-current", currentBot && b.id === currentBot.id ? "page" : undefined);
    d.innerHTML = `${avatarHtml(b)}
      <div class="who">
        <div class="name-row"><span class="name">${esc(b.name)}</span><span class="dot live" title="Siap"></span></div>
      </div>`;
    d.onclick = () => selectBot(b.id);
    el.appendChild(d);
  });
}

/* ---- Floating header pill (ala DS-Bot .bt-pill): avatar + name + chip.
   Clicking it opens the bot settings (model/effort/avatar/tagline). ---- */
function renderBotHeader() {
  const el = document.getElementById("bot-header");
  if (!currentBot) { el.innerHTML = ""; return; }
  el.innerHTML =
    `<button type="button" class="bt-pill" id="pill-btn" title="Lihat detail bot">` +
    `${avatarHtml(currentBot, 26)}` +
    `<span class="bt-pill-name">${esc(currentBot.name)}</span>` +
    `<span class="bt-pill-go" aria-hidden="true">→</span>` +
    `</button>` +
    `<button type="button" class="btn" id="picker-back" title="Kembali ke daftar bot">Pilih bot lain</button>`;
  document.getElementById("picker-back").onclick = showPicker;
  document.getElementById("pill-btn").onclick = () => {
    const panel = document.getElementById("bot-settings");
    if (panel.hidden) openSettings();
    else panel.hidden = true;
  };
}

function setBotTyping(on) {
  const head = document.querySelector(".dsb-head");
  if (head) head.classList.toggle("typing", !!on);
}

/* ---- Settings sheet (model & effort + avatar ala DS-Bot) ---- */
function openSettings() {
  const panel = document.getElementById("bot-settings");
  panel.hidden = false;
  document.getElementById("set-name").value = currentBot.name;
  document.getElementById("set-tagline").value = currentBot.tagline || "";
  const modelSel = document.getElementById("set-model");
  modelSel.innerHTML = models.map(m =>
    `<option ${m === currentBot.model ? "selected" : ""}>${m}</option>`).join("");
  const effortSel = document.getElementById("set-effort");
  effortSel.innerHTML = efforts.map(e =>
    `<option ${e === currentBot.effort ? "selected" : ""}>${e}</option>`).join("");
  modelSel.onchange = () => {
    const sup = modelEfforts[modelSel.value] || efforts;
    effortSel.innerHTML = sup.map(e =>
      `<option ${e === currentBot.effort ? "selected" : ""}>${e}</option>`).join("");
  };
  renderAvatarPicker();
  document.getElementById("set-status").textContent =
    currentBot.avatar_image ? ("Foto avatar aktif: " + currentBot.avatar_image) : "";
}

/* Picker avatar ala DS-Bot Settings: preview besar + grid karakter
   (6 kolom) + baris warna. Tiap klik langsung tersimpan (seperti
   DS-Bot: "every click saves") — tidak perlu tekan Simpan. */
function renderAvatarPicker() {
  const b = currentBot;
  const shape = b.avatar_shape || DEFAULT_SHAPES[b.id] || "gumdrop";
  const color = b.avatar_color || "#2FA08C";
  document.getElementById("set-preview").innerHTML = avatarHtml(b, 96);
  document.getElementById("set-preview-name").textContent = b.name;
  document.getElementById("set-preview-role").textContent = b.role || "";
  const grid = document.getElementById("set-shapes");
  grid.innerHTML = "";
  avatarShapes.forEach(s => {
    const cell = document.createElement("button");
    cell.type = "button";
    const selected = shape === s.id && !b.avatar_image;
    cell.className = "bt-shape" + (selected ? " selected" : "");
    cell.title = s.label;
    cell.setAttribute("aria-label", s.label);
    cell.setAttribute("aria-pressed", selected ? "true" : "false");
    cell.innerHTML = dsShapeRing(s.id, 36) + dsAvatarHTML(s.id, color, 36);
    cell.onclick = () => saveLook({ avatar_shape: s.id });
    grid.appendChild(cell);
  });
  const row = document.getElementById("set-colors");
  row.innerHTML = "";
  avatarColors.forEach(c => {
    const sw = document.createElement("button");
    sw.type = "button";
    const selected = color === c.id;
    sw.className = "bt-color" + (selected ? " selected" : "");
    sw.title = c.label;
    sw.setAttribute("aria-label", c.label);
    sw.setAttribute("aria-pressed", selected ? "true" : "false");
    sw.innerHTML = `<span style="background:${paintCss(c.id)}"></span>`;
    sw.onclick = () => saveLook({ avatar_color: c.id });
    row.appendChild(sw);
  });
  const custom = document.getElementById("set-color");
  custom.value = /^#[0-9a-f]{6}$/i.test(color) ? color : inkHex(color);
  document.getElementById("set-color-hex").textContent = color;
}

function switchAvatarTab(tab) {
  document.getElementById("tab-bot").classList.toggle("active", tab === "bot");
  document.getElementById("tab-upload").classList.toggle("active", tab === "upload");
  document.getElementById("set-tab-bot").hidden = tab !== "bot";
  document.getElementById("set-tab-upload").hidden = tab !== "upload";
}

async function saveLook(patch) {
  const status = document.getElementById("set-status");
  try {
    const updated = await api("/api/bots/" + currentBot.id, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch) });
    currentBot = updated;
    bots = bots.map(x => (x.id === updated.id ? updated : x));
    status.textContent = "Karakter tersimpan.";
    renderBotList(); renderBotHeader(); renderAvatarPicker();
  } catch (err) {
    status.textContent = "Gagal: " + err.message;
  }
}

async function resetLook() {
  // Kembali ke karakter default bot ini (bentuk + warna seed).
  await saveLook({
    avatar_shape: DEFAULT_SHAPES[currentBot.id] || "gumdrop",
    avatar_color: DEFAULT_COLORS[currentBot.id] || "#2FA08C",
  });
}

async function saveSettings() {
  const status = document.getElementById("set-status");
  const body = {
    name: document.getElementById("set-name").value.trim() || currentBot.name,
    tagline: document.getElementById("set-tagline").value.trim(),
    model: document.getElementById("set-model").value,
    effort: document.getElementById("set-effort").value,
  };
  try {
    const photo = document.getElementById("set-photo").files[0];
    if (photo) {
      const fd = new FormData();
      fd.append("avatar", photo);
      const r = await fetch("/api/bots/" + currentBot.id + "/avatar", { method: "POST", body: fd });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
      currentBot.avatar_image = j.avatar_image;
    }
    const updated = await api("/api/bots/" + currentBot.id, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) });
    currentBot = updated;
    bots = bots.map(b => (b.id === updated.id ? updated : b));
    status.textContent = "Tersimpan.";
    renderBotList(); renderBotHeader(); openSettings();
  } catch (err) {
    status.textContent = "Gagal: " + err.message;
  }
}

async function removePhoto() {
  const status = document.getElementById("set-status");
  try {
    const updated = await api("/api/bots/" + currentBot.id, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatar_image: null }) });
    currentBot = updated;
    bots = bots.map(b => (b.id === updated.id ? updated : b));
    status.textContent = "Foto dihapus, balik ke karakter.";
    renderBotList(); renderBotHeader(); openSettings();
  } catch (err) {
    status.textContent = "Gagal: " + err.message;
  }
}

/* ---- Messages ---- */
function timeLine(ts) {
  const t = fmtClock(ts);
  return t ? `<span class="time">${t}</span>` : "";
}

function scrollMessages() {
  const el = document.querySelector(".dsb-scroll");
  if (el) el.scrollTop = el.scrollHeight;
}

/* Pesan: user = bubble kanan; assistant = BARIS PENUH ala OpenBot
   (avatar + nama + isi, tanpa bubble). */
function addMsg(role, text, usage, ts) {
  const el = document.getElementById("messages");
  const d = document.createElement("div");
  d.className = "msg " + role;
  const when = timeLine(ts || Math.floor(Date.now() / 1000));
  if (role === "assistant") {
    const body = document.createElement("div");
    body.className = "msg-body";
    const nm = document.createElement("div");
    nm.className = "msg-name";
    nm.innerHTML = `${esc(currentBot ? currentBot.name : "Bot")}` +
      (currentBot && currentBot.tagline ? `<span class="msg-tag">${esc(currentBot.tagline)}</span>` : "");
    body.appendChild(nm);
    const m = String(text || "").match(/^\[gambar: (\/static\/uploads\/[^\]]+)\]\n?([\s\S]*)$/);
    if (m) {
      const img = document.createElement("img");
      img.className = "attached";
      img.src = m[1];
      img.alt = "gambar terlampir";
      body.appendChild(img);
      const md = document.createElement("div");
      md.className = "md";
      md.innerHTML = renderMarkdown(m[2] || "");
      renderMath(md);
      body.appendChild(md);
    } else {
      const md = document.createElement("div");
      md.className = "md";
      md.innerHTML = renderMarkdown(text);
      renderMath(md);
      body.appendChild(md);
    }
    if (usage) {
      const s = document.createElement("span");
      s.className = "usage-line";
      s.textContent = `token: ${usage.total_tokens} (in ${usage.input_tokens} / out ${usage.output_tokens})`;
      body.appendChild(s);
    }
    if (when) {
      const t = document.createElement("span");
      t.innerHTML = when;
      if (t.firstChild) body.appendChild(t.firstChild);
    }
    d.appendChild(document.createRange().createContextualFragment(
      currentBot ? avatarHtml(currentBot, 30) : ""));
    d.appendChild(body);
  } else {
    const m = String(text || "").match(/^\[gambar: (\/static\/uploads\/[^\]]+)\]\n?([\s\S]*)$/);
    if (m) {
      const img = document.createElement("img");
      img.className = "attached";
      img.src = m[1];
      img.alt = "gambar terlampir";
      d.appendChild(img);
      d.appendChild(document.createTextNode(m[2] || ""));
    } else {
      d.textContent = text;
    }
    if (usage) {
      const s = document.createElement("span");
      s.className = "usage-line";
      s.textContent = `token: ${usage.total_tokens} (in ${usage.input_tokens} / out ${usage.output_tokens})`;
      d.appendChild(s);
    }
    if (when) {
      const t = document.createElement("span");
      t.innerHTML = when;
      if (t.firstChild) d.appendChild(t.firstChild);
    }
  }
  el.appendChild(d);
  scrollMessages();
  return d;
}

/* Typing indicator "hidup": avatar bot + nama + titik mengetik. */
function showTyping() {
  const el = document.getElementById("messages");
  const d = document.createElement("div");
  d.className = "msg assistant typing-msg";
  d.id = "typing-indicator";
  d.innerHTML = `${avatarHtml(currentBot, 34)}` +
    `<div class="typing-body"><div class="typing-name">${esc(currentBot.name)}</div>` +
    `<span class="typing"><i></i><i></i><i></i></span><span class="typing-text">sedang mengetik…</span></div>`;
  el.appendChild(d);
  scrollMessages();
  return d;
}

function showPicker() {
  currentBot = null;
  document.getElementById("frame").classList.add("picker-mode");
  document.getElementById("bot-picker").hidden = false;
  document.getElementById("chat").hidden = true;
  document.querySelector(".dsb-head").hidden = true;
  document.getElementById("bot-settings").hidden = true;
  renderBotList();
  renderPicker();
}

function renderPicker() {
  const list = document.getElementById("picker-list");
  const count = document.getElementById("picker-count");
  if (count) count.textContent = bots.length + " / 20 bot";
  const addModel = document.getElementById("add-model");
  if (addModel && models.length) {
    addModel.innerHTML = models.map(m => `<option>${m}</option>`).join("");
    if (models.includes("gemini-3.8-flash")) addModel.value = "gemini-3.8-flash";
  }
  const addEffort = document.getElementById("add-effort");
  if (addEffort && efforts.length) {
    addEffort.innerHTML = efforts.map(e => `<option>${e}</option>`).join("");
    if (efforts.includes("medium")) addEffort.value = "medium";
  }
  list.innerHTML = "";
  bots.forEach(b => {
    const card = document.createElement("div");
    card.className = "picker-card";
    card.dataset.name = (b.name || "").toLowerCase();
    card.innerHTML = `${avatarHtml(b, 48)}
      <div class="who"><div class="name">${esc(b.name)}</div>${b.tagline ? `<div class="sub">${esc(b.tagline)}</div>` : ""}</div>`;
    card.addEventListener("click", () => selectBot(b.id));
    list.appendChild(card);
  });
  const addCard = document.createElement("div");
  addCard.className = "picker-card picker-add-card";
  addCard.innerHTML = `<div class="picker-plus">+</div><div class="who"><div class="name">Tambah</div></div>`;
  addCard.addEventListener("click", () => {
    const wrap = document.getElementById("picker-add-wrap");
    wrap.hidden = !wrap.hidden;
    if (!wrap.hidden) document.getElementById("add-name").focus();
  });
  list.appendChild(addCard);
}

function showBotTab(which) {
  const chatTab = document.getElementById("tab-chat-view");
  const routTab = document.getElementById("tab-routines-view");
  const scroll = document.querySelector(".dsb-scroll");
  const composer = document.querySelector(".dsb-composer-root");
  const rout = document.getElementById("bot-routines");
  const isRout = which === "routines";
  chatTab.classList.toggle("active", !isRout);
  routTab.classList.toggle("active", isRout);
  scroll.hidden = isRout;
  composer.hidden = isRout;
  rout.hidden = !isRout;
  if (isRout) loadBotRoutines();
}

async function loadBotRoutines() {
  const wrap = document.getElementById("bot-routine-list");
  if (!currentBot) { wrap.innerHTML = ""; return; }
  wrap.innerHTML = `<p class="note">Memuat routines…</p>`;
  try {
    const all = await api("/api/routines");
    const mine = all.filter(r => r.bot_id === currentBot.id);
    if (!mine.length) {
      wrap.innerHTML = `<p class="note">Bot ini belum punya routine.</p>`;
      return;
    }
    wrap.innerHTML = "";
    mine.forEach(r => {
      const last = r.last_run
        ? `${esc(r.last_run.status)} · ${new Date((r.last_run.finished_at || r.last_run.started_at) * 1000).toLocaleString("id-ID")}`
        : "belum pernah jalan";
      const card = document.createElement("div");
      card.className = "routine-card";
      card.innerHTML =
        `<div class="info">
          <div class="r-name">${esc(r.name)}</div>
          <div class="r-meta">${esc(r.schedule_label)}</div>
          <div class="r-last">Run terakhir: ${last}</div>
        </div>
        <div class="actions">
          <label class="switch" title="${r.enabled ? "Nonaktifkan" : "Aktifkan"}">
            <input type="checkbox" data-act="toggle" ${r.enabled ? "checked" : ""}>
            <span class="slider"></span>
          </label>
          <button class="btn primary" data-act="run">Jalankan</button>
        </div>`;
      card.querySelector('[data-act="toggle"]').addEventListener("change", async (e) => {
        try {
          await api("/api/routines/" + r.id, { method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: e.target.checked }) });
        } catch (err) { alert("Gagal: " + err.message); e.target.checked = !e.target.checked; }
      });
      card.querySelector('[data-act="run"]').addEventListener("click", async (ev) => {
        const btn = ev.currentTarget;
        btn.disabled = true;
        try {
          const res = await api("/api/routines/" + r.id + "/run", { method: "POST" });
          btn.textContent = "Berjalan…";
          for (let i = 0; i < 40; i++) {
            await new Promise(res2 => setTimeout(res2, 15000));
            const run = await api("/api/routine-runs/" + res.run_id);
            if (run.status !== "running") break;
          }
          loadBotRoutines();
        } catch (err) { alert("Gagal menjalankan: " + err.message); btn.disabled = false; }
      });
      wrap.appendChild(card);
    });
  } catch (err) {
    wrap.innerHTML = `<p class="note">Gagal memuat routines: ${esc(err.message)}</p>`;
  }
}

async function deleteCurrentBot() {
  if (!currentBot) return;
  if (!confirm("Hapus bot '" + currentBot.name + "'?")) return;
  try {
    await api("/api/bots/" + currentBot.id, { method: "DELETE" });
    bots = await api("/api/bots");
    renderBotList(); showPicker();
  } catch (err) { alert("Gagal menghapus: " + err.message); }
}

async function selectBot(id) {
  currentBot = bots.find(b => b.id === id);
  document.getElementById("frame").classList.remove("picker-mode");
  document.getElementById("picker-add-wrap").hidden = true;
  showBotTab("chat");
  document.getElementById("bot-picker").hidden = true;
  document.getElementById("chat").hidden = false;
  document.querySelector(".dsb-head").hidden = false;
  document.getElementById("bot-settings").hidden = true;
  renderBotList();
  renderBotHeader();
  document.getElementById("messages").innerHTML = "";
  try {
    const msgs = await api("/api/bots/" + id + "/messages");
    msgs.forEach(m => addMsg(m.role === "user" ? "user" : "assistant", m.content, null, m.created_at));
  } catch (e) { /* history optional */ }
}

function updateImagePreview() {
  const file = document.getElementById("image-input").files[0];
  const prev = document.getElementById("image-preview");
  pendingImage = file || null;
  if (!file) { prev.innerHTML = ""; updateSendBtn(); return; }
  const url = URL.createObjectURL(file);
  prev.innerHTML = `<img src="${url}" alt="preview"> <span>${esc(file.name)}</span> ` +
    `<button type="button" id="image-clear">✕</button>`;
  document.getElementById("image-clear").onclick = () => {
    document.getElementById("image-input").value = "";
    updateImagePreview();
  };
  updateSendBtn();
}

/* DS-Bot hides the send button while the draft is empty. */
function updateSendBtn() {
  const btn = document.querySelector("#composer button[type=submit]");
  const hasText = document.getElementById("input").value.trim().length > 0;
  btn.disabled = !hasText && !pendingImage;
}

function addUserMsgWithImage(objectUrl, text) {
  const el = document.getElementById("messages");
  const d = document.createElement("div");
  d.className = "msg user";
  const img = document.createElement("img");
  img.className = "attached";
  img.src = objectUrl;
  img.alt = "gambar terlampir";
  d.appendChild(img);
  const span = document.createElement("span");
  span.textContent = text || "";
  d.appendChild(span);
  const t = document.createElement("span");
  t.innerHTML = timeLine(Math.floor(Date.now() / 1000));
  if (t.firstChild) d.appendChild(t.firstChild);
  el.appendChild(d);
  scrollMessages();
}

async function send(e) {
  e.preventDefault();
  if (!currentBot) return;
  if (window.__chatPending) return;
  const input = document.getElementById("input");
  const text = input.value.trim();
  if (!text && !pendingImage) return;
  window.__chatPending = true;
  input.value = "";
  updateSendBtn();
  const file = pendingImage;
  pendingImage = null;
  document.getElementById("image-input").value = "";
  updateImagePreview();
  if (file) {
    addUserMsgWithImage(URL.createObjectURL(file), text);
  } else {
    addMsg("user", text);
  }
  const btn = document.querySelector("#composer button[type=submit]");
  const status = document.getElementById("status");
  btn.disabled = true;
  const typing = showTyping();
  setBotTyping(true);
  const t0 = Date.now();
  const tick = () => {
    const s = Math.floor((Date.now() - t0) / 1000);
    status.textContent = currentBot.name + " mikir… " + s + " detik";
  };
  tick();
  const timer = setInterval(tick, 1000);
  const finish = () => {
    clearInterval(timer);
    typing.remove();
    setBotTyping(false);
    btn.disabled = false;
    window.__chatPending = false;
    updateSendBtn();
  };
  try {
    let jobId = null;
    let was409 = false;
    const fd2 = new FormData();
    if (file) {
      fd2.append("bot_id", String(currentBot.id));
      fd2.append("message", text || "Jelaskan gambar ini.");
      fd2.append("image", file);
    }
    const res = file
      ? await fetch("/api/chat", { method: "POST", body: fd2 })
      : await fetch("/api/chat", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ bot_id: currentBot.id, message: text }) });
    const r = await res.json().catch(() => ({}));
    if (res.status === 409 && r.job_id) {
      jobId = r.job_id;
      was409 = true;
    } else if (!res.ok) {
      throw new Error(r.error || ("HTTP " + res.status));
    } else {
      jobId = r.job_id;
    }
    if (!jobId) throw new Error("server tidak mengembalikan job_id");
    if (was409) {
      addMsg("assistant", "Bot masih menjawab pesan sebelumnya, jadi pesan barusan belum dikirim. Ini balasan untuk pesan sebelumnya:");
    }
    let fails = 0;
    for (;;) {
      if (Date.now() - t0 > 900000) {
        finish();
        addMsg("assistant", "Bot belum selesai setelah 15 menit, kemungkinan server restart. Buka ulang chat untuk melihat balasan.");
        status.textContent = "timeout poll";
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 3000));
      let j;
      try {
        const pr = await fetch("/api/chat/jobs/" + jobId);
        j = await pr.json().catch(() => ({}));
        if (!pr.ok) throw new Error(j.error || ("HTTP " + pr.status));
        fails = 0;
      } catch (pollErr) {
        fails += 1;
        if (fails >= 5) throw pollErr;
        continue;
      }
      if (j.status === "done") {
        finish();
        addMsg("assistant", j.reply, j.usage);
        status.textContent = j.ok ? `selesai ${j.duration_seconds || "?"} detik` : "agy gagal";
        return;
      }
      if (j.status === "failed") {
        finish();
        addMsg("assistant", j.reply || ("Maaf, agy gagal: " + (j.error || "unknown error")));
        status.textContent = "agy gagal";
        return;
      }
    }
  } catch (err) {
    finish();
    addMsg("assistant", "Gagal menghubungi server: " + err.message);
    status.textContent = "error";
  }
}

/* Rail sidebar (data-rail) hanya untuk desktop. Di HP rail pernah menumpuk
   chat dan memotong brand jadi "AgyB" — jadi di sini rail selalu dimatikan
   kalau lebar layar ≤ 760px (saat load dan saat resize). */
function guardRail() {
  const frame = document.getElementById("frame");
  if (frame && window.innerWidth <= 760) frame.removeAttribute("data-rail");
}

(async function init() {
  const m = await api("/api/models");
  models = m.models; efforts = m.efforts; modelEfforts = m.model_efforts || {};
  const a = await api("/api/avatars");
  avatarShapes = a.shapes || []; avatarColors = a.colors || [];
  bots = await api("/api/bots");
  const params = new URLSearchParams(window.location.search);
  const want = parseInt(params.get("bot") || "", 10);
  const first = bots.find(b => b.id === want);
  if (first) selectBot(first.id);
  else showPicker();
  document.getElementById("composer").addEventListener("submit", send);
  document.getElementById("input").addEventListener("input", updateSendBtn);
  document.getElementById("image-input").addEventListener("change", updateImagePreview);
  document.getElementById("tab-chat-view").addEventListener("click", () => showBotTab("chat"));
  document.getElementById("tab-routines-view").addEventListener("click", () => showBotTab("routines"));
  document.getElementById("set-save").addEventListener("click", saveSettings);
  document.getElementById("set-delete-bot").addEventListener("click", deleteCurrentBot);
  document.getElementById("picker-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("add-status");
    try {
      const nb = await api("/api/bots", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: document.getElementById("add-name").value.trim(),
          role: document.getElementById("add-role").value.trim() || "Bot baru",
          instructions: document.getElementById("add-instructions").value.trim(),
          model: document.getElementById("add-model").value,
          effort: document.getElementById("add-effort").value,
        }) });
      bots = await api("/api/bots");
      renderBotList(); renderPicker();
      document.getElementById("add-name").value = "";
      document.getElementById("add-role").value = "";
      document.getElementById("add-instructions").value = "";
      status.textContent = "Bot '" + nb.name + "' ditambahkan.";
      document.getElementById("picker-add-wrap").hidden = true;
    } catch (err) { status.textContent = "Gagal: " + err.message; }
  });
  document.getElementById("set-remove-photo").addEventListener("click", removePhoto);
  document.getElementById("set-close").addEventListener("click", () => {
    document.getElementById("bot-settings").hidden = true;
  });
  document.getElementById("tab-bot").addEventListener("click", () => switchAvatarTab("bot"));
  document.getElementById("tab-upload").addEventListener("click", () => switchAvatarTab("upload"));
  document.getElementById("set-reset-look").addEventListener("click", resetLook);
  document.getElementById("set-color").addEventListener("change", (e) => saveLook({ avatar_color: e.target.value }));
  const collapseBtn = document.getElementById("collapse-btn");
  if (collapseBtn) collapseBtn.addEventListener("click", () => {
    if (window.innerWidth <= 760) return; // rail tidak ada di HP
    document.getElementById("frame").toggleAttribute("data-rail");
  });
  guardRail();
  window.addEventListener("resize", guardRail);
  updateSendBtn();
})();

// Untuk verifikasi (CDP): renderMarkdown + renderMath bisa dipanggil
// dari luar tanpa mengirim pesan ke agy (tanpa bakar token).
window.AGYBOT_TEST = { renderMarkdown, renderMath };
