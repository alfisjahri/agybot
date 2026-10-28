// AgyBot — Routines UI (Phase 4: cards, toggle switches, verification pills)
let BOTS = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("id-ID");
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function loadBots() {
  BOTS = await api("/api/bots");
  const sel = document.getElementById("f-bot");
  sel.innerHTML = BOTS.map(b =>
    `<option value="${b.id}">${esc(b.name)}</option>`).join("");
}

function botName(id) {
  const b = BOTS.find(x => x.id === id);
  return b ? b.name : ("Bot " + id);
}

async function loadRoutines() {
  const list = await api("/api/routines");
  const wrap = document.getElementById("routine-list");
  wrap.innerHTML = "";
  if (!list.length) {
    wrap.innerHTML = `<p class="note">Belum ada routine. Tambah dari form di bawah.</p>`;
    return;
  }
  for (const r of list) {
    const last = r.last_run
      ? `${esc(r.last_run.status)} · ${fmtTime(r.last_run.finished_at || r.last_run.started_at)}`
      : "belum pernah jalan";
    const card = document.createElement("div");
    card.className = "routine-card";
    card.innerHTML =
      `<div class="info">
        <div class="r-name">${esc(r.name)}</div>
        <div class="r-meta">${esc(botName(r.bot_id))} · ${esc(r.schedule_label)}</div>
        <div class="r-last">Run terakhir: ${last}</div>
      </div>
      <div class="actions">
        <label class="switch" title="${r.enabled ? "Nonaktifkan" : "Aktifkan"}">
          <input type="checkbox" data-act="toggle" ${r.enabled ? "checked" : ""}>
          <span class="slider"></span>
        </label>
        <button class="btn primary" data-act="run"><svg viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true"><polygon points="7 4.5 20 12 7 19.5 7 4.5"/></svg> Jalankan</button>
        <button class="btn" data-act="edit">Ubah</button>
        <button class="btn danger" data-act="del">Hapus</button>
      </div>`;
    card.querySelector('[data-act="toggle"]').addEventListener("change", async (e) => {
      try {
        await api("/api/routines/" + r.id, { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: e.target.checked }) });
        loadRoutines();
      } catch (err) { alert("Gagal: " + err.message); e.target.checked = !e.target.checked; }
    });
    card.querySelector('[data-act="run"]').addEventListener("click", async (ev) => {
      const btn = ev.currentTarget;
      btn.disabled = true;
      try {
        const res = await api("/api/routines/" + r.id + "/run", { method: "POST" });
        pollRun(res.run_id);
      } catch (err) {
        alert("Gagal menjalankan: " + err.message);
        btn.disabled = false;
      }
    });
    card.querySelector('[data-act="edit"]').addEventListener("click", () => fillForm(r));
    card.querySelector('[data-act="del"]').addEventListener("click", async () => {
      if (!confirm("Hapus routine '" + r.name + "'?")) return;
      try { await api("/api/routines/" + r.id, { method: "DELETE" }); loadRoutines(); }
      catch (err) { alert("Gagal menghapus: " + err.message); }
    });
    wrap.appendChild(card);
  }
}

async function pollRun(runId) {
  for (let i = 0; i < 40; i++) {
    await new Promise(res => setTimeout(res, 15000));
    try {
      const run = await api("/api/routine-runs/" + runId);
      if (run.status !== "running") { loadRuns(); loadRoutines(); return; }
    } catch (e) { /* keep polling */ }
  }
  loadRuns();
}

const VERIFY_LABEL = {
  ok: ["pill-ok", "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><path d='M22 11.08V12a10 10 0 1 1-5.93-9.14'/><polyline points='22 4 12 14.01 9 11.01'/></svg> Terverifikasi"],
  needs_manual_check: ["pill-warn", "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><path d='M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/></svg> Cek manual"],
  failed: ["pill-fail", "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><circle cx='12' cy='12' r='10'/><line x1='15' y1='9' x2='9' y2='15'/><line x1='9' y1='9' x2='15' y2='15'/></svg> Gagal"],
  unverified: ["pill-muted", "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><circle cx='12' cy='12' r='10'/><path d='M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3'/><line x1='12' y1='17' x2='12.01' y2='17'/></svg> Belum terverifikasi"],
  none: ["pill-muted", "—"],
};

function verifyCell(run) {
  let v = run.verification;
  if (typeof v === "string") {
    try { v = JSON.parse(v); } catch (e) { v = null; }
  }
  if (!v || !v.status) return `<span class="pill pill-muted">—</span>`;
  const entry = VERIFY_LABEL[v.status] || ["pill-muted", esc(v.status)];
  const notes = (v.checks || []).map(c => c.note || "").filter(Boolean).join(" | ");
  return `<span class="pill ${entry[0]}" title="${esc(notes)}">${entry[1]}</span>`;
}

function statusPill(status) {
  if (status === "done") return `<span class="pill pill-ok">done</span>`;
  if (status === "failed") return `<span class="pill pill-fail">failed</span>`;
  if (status === "running") return `<span class="pill pill-info">running…</span>`;
  return `<span class="pill pill-muted">${esc(status || "—")}</span>`;
}

async function loadRuns() {
  const runs = await api("/api/routine-runs?limit=15");
  const tbody = document.querySelector("#runs-table tbody");
  tbody.innerHTML = "";
  for (const run of runs) {
    const tr = document.createElement("tr");
    const snippet = esc((run.result || "").slice(0, 120));
    tr.innerHTML =
      `<td data-label="Waktu">${fmtTime(run.started_at)}</td>` +
      `<td data-label="Routine">${esc(run.routine_name || "")}</td>` +
      `<td data-label="Trigger">${esc(run.trigger)}</td>` +
      `<td data-label="Status">${statusPill(run.status)}</td>` +
      `<td data-label="Verifikasi">${verifyCell(run)}</td>` +
      `<td data-label="Token" class="num">${run.total_tokens || 0}</td>` +
      `<td data-label="Durasi" class="num">${run.duration_seconds || 0} dtk</td>` +
      `<td data-label="Hasil" title="${esc(run.result || "")}">${snippet}</td>`;
    tbody.appendChild(tr);
  }
}

function fillForm(r) {
  document.getElementById("f-id").value = r.id;
  document.getElementById("f-name").value = r.name;
  document.getElementById("f-bot").value = r.bot_id;
  document.getElementById("f-prompt").value = r.prompt;
  document.getElementById("f-time").value = r.time_hhmm || "07:35";
  document.getElementById("f-cron").value = "";
  document.getElementById("f-enabled").checked = !!r.enabled;
  const days = (r.days || "").split(",");
  document.querySelectorAll(".f-day").forEach(cb => { cb.checked = days.includes(cb.value); });
  document.getElementById("form-status").textContent = "Mengubah routine #" + r.id + " — " + r.name;
  window.scrollTo(0, document.getElementById("routine-form").offsetTop);
}

function resetForm() {
  document.getElementById("f-id").value = "";
  document.getElementById("f-name").value = "";
  document.getElementById("f-prompt").value = "";
  document.getElementById("f-time").value = "07:35";
  document.getElementById("f-cron").value = "";
  document.getElementById("f-enabled").checked = false;
  document.querySelectorAll(".f-day").forEach(cb => { cb.checked = false; });
  document.getElementById("form-status").textContent = "";
}

document.getElementById("routine-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("f-id").value;
  const days = [...document.querySelectorAll(".f-day:checked")].map(cb => cb.value).join(",");
  const body = {
    name: document.getElementById("f-name").value,
    bot_id: parseInt(document.getElementById("f-bot").value, 10),
    days, time_hhmm: document.getElementById("f-time").value,
    prompt: document.getElementById("f-prompt").value,
    enabled: document.getElementById("f-enabled").checked,
  };
  const cron = document.getElementById("f-cron").value.trim();
  if (cron) body.cron_expr = cron;
  try {
    if (id) await api("/api/routines/" + id, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    else await api("/api/routines", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    document.getElementById("form-status").textContent = "Tersimpan.";
    resetForm(); loadRoutines();
  } catch (err) {
    document.getElementById("form-status").textContent = "Gagal: " + err.message;
  }
});
document.getElementById("form-reset").addEventListener("click", resetForm);

loadBots().then(loadRoutines).catch(err => alert("Gagal memuat: " + err.message));
loadRuns();
setInterval(loadRuns, 30000);
