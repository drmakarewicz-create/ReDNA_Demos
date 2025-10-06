// ExplorerFinal/ui/app.js

// ------- Config (overridden by /config if present) -------
const CONFIG = {
  core_base_url: "http://localhost:8002",
  ucnrr_base_url: "http://localhost:8003",
  photo_base_url: "http://localhost:8004",
  user_id: "dev_user_001",
};

// Simple state
const state = {
  devMode: false,
  rr: null,
  traits: [],          // TraitRow[]
  recentEvents: [],    // Prov[]
  curiosityTop: [],    // Cur[]
  avatar: null,        // {image_url?, description}
};

// Utilities
async function getJSON(url) {
  try {
    const r = await fetch(url, { credentials: "omit" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    return null;
  }
}
async function fetchConfig() {
  const cfg = await getJSON("/config");
  if (cfg) Object.assign(CONFIG, cfg);
}

function saveDev(v) { try { localStorage.setItem("dev_mode", v ? "1" : "0"); } catch (e) {} }
function loadDev() { try { return localStorage.getItem("dev_mode") === "1"; } catch (e) { return false; } }

// ------- Rendering helpers -------
const elTabs = document.getElementById("tabs");
const elContent = document.getElementById("tabContent");
const elBadge = document.getElementById("rrBadge");
const elToggle = document.getElementById("devToggle");

// Tab registry (label, renderer)
const tabs = [
  ["Unabridged Traits", renderUnabridgedTraits],
  ["Recent Evidence", renderRecentEvidence],
  ["Curiosity Agenda", renderCuriosityAgenda],
  ["PaDNA Avatar (Preview)", renderPaAvatar],
  ["Developer Logs", renderDevLogs],
];

function setBadge(rr) {
  elBadge.textContent = `RR: ${rr == null ? "--" : `${rr}%`}`;
}

function mountTabs() {
  elTabs.innerHTML = "";
  tabs.forEach(([label], idx) => {
    // Only show in Dev Mode:
    if (!state.devMode) return;
    const b = document.createElement("button");
    b.className = "tabbtn";
    b.textContent = label;
    b.addEventListener("click", () => selectTab(idx));
    elTabs.appendChild(b);
  });
  // Auto-select first if any
  if (state.devMode && elTabs.children.length) selectTab(0);
  else elContent.innerHTML = `<div class="empty">Enable <strong>Developer Mode</strong> to see read-only tabs.</div>`;
}

function selectTab(idx) {
  [...elTabs.children].forEach((c, i) => c.classList.toggle("active", i === idx));
  const renderer = tabs[idx][1];
  safeRender(renderer);
}

function safeRender(fn) {
  try { fn(); } catch (e) {
    elContent.innerHTML = `<div class="empty">Tab temporarily unavailable: ${e.message}</div>`;
  }
}

// ------- Data loaders (read-only) -------
async function loadRR() {
  const url = `${CONFIG.ucnrr_base_url}/rr?user_id=${encodeURIComponent(CONFIG.user_id)}`;
  const data = await getJSON(url);
  const rr = data && (data.rr_percent ?? data.rr ?? null);
  state.rr = rr != null ? Math.round(rr) : null;
  setBadge(state.rr);
}

async function loadTraits() {
  // Primary: Core export
  const url = `${CONFIG.core_base_url}/traits/full?user_id=${encodeURIComponent(CONFIG.user_id)}`;
  const data = await getJSON(url);
  if (data && Array.isArray(data.traits)) {
    state.traits = data.traits;
    return;
  }
  // Fallback: static skeleton (unknowns)
  state.traits = fallbackTraits();
}

async function loadProvenance() {
  const url = `${CONFIG.core_base_url}/provenance/recent?user_id=${encodeURIComponent(CONFIG.user_id)}&limit=50`;
  const data = await getJSON(url);
  state.recentEvents = data && Array.isArray(data.events) ? data.events : [];
}

async function loadCuriosity() {
  const url = `${CONFIG.ucnrr_base_url}/curiosity/top?user_id=${encodeURIComponent(CONFIG.user_id)}&limit=10`;
  const data = await getJSON(url);
  if (data && Array.isArray(data.items)) {
    state.curiosityTop = data.items;
    return;
  }
  // Fallback: compute from traits (unknown or low UCN -> high curiosity)
  const items = state.traits
    .map(t => ({ trait_key: t.trait_key, curiosity: Number.isFinite(t.curiosity) ? t.curiosity : (t.value ? 30 : 100) }))
    .sort((a, b) => b.curiosity - a.curiosity)
    .slice(0, 10);
  state.curiosityTop = items;
}

async function loadAvatar() {
  const url = `${CONFIG.photo_base_url}/pa_outbound/render?user_id=${encodeURIComponent(CONFIG.user_id)}`;
  const data = await getJSON(url);
  if (data && (data.image_url || data.description)) {
    state.avatar = data;
    return;
  }
  state.avatar = { description: synthesizePaDescription(state.traits) };
}

// ------- Tab renderers -------
function renderUnabridgedTraits() {
  const head = `
    <div class="row">
      <input id="flt" class="input" placeholder="Filter by DNA path / trait / status..." />
      <button id="sortC" class="btn">Sort by Curiosity</button>
      <button id="sortP" class="btn btn-ghost">Sort by Path</button>
    </div>
  `;
  const rows = state.traits.map(tr => {
    const stClass = tr.status === "contradiction" ? "st-contradiction" :
                    tr.status === "ok" ? "st-ok" : "st-unknown";
    const stText = tr.status || "unknown";
    const val = tr.value == null ? "<span class='muted'>—</span>" : escapeHtml(String(tr.value));
    const notes = tr.notes ? escapeHtml(tr.notes) : "";
    return `
      <tr>
        <td>${escapeHtml(tr.dna_path || "")}</td>
        <td><code>${escapeHtml(tr.trait_key || "")}</code></td>
        <td>${val}</td>
        <td>${Number.isFinite(tr.ucn) ? tr.ucn : 0}</td>
        <td>${Number.isFinite(tr.curiosity) ? tr.curiosity : (tr.value ? 30 : 100)}</td>
        <td><span class="status ${stClass}">${escapeHtml(stText)}</span></td>
        <td>${notes}</td>
      </tr>
    `;
  }).join("");
  const table = `
    <table class="table">
      <thead>
        <tr>
          <th>DNA Path</th><th>Trait Key</th><th>Value</th>
          <th>UCN</th><th>Curiosity</th><th>Status</th><th>Notes</th>
        </tr>
      </thead>
      <tbody id="traitsBody">${rows}</tbody>
    </table>
  `;
  elContent.innerHTML = head + table;

  // Wire filters/sorts
  const elF = document.getElementById("flt");
  const elB1 = document.getElementById("sortC");
  const elB2 = document.getElementById("sortP");

  elF.addEventListener("input", () => {
    const q = elF.value.toLowerCase();
    const filtered = state.traits.filter(t =>
      (t.dna_path||"").toLowerCase().includes(q) ||
      (t.trait_key||"").toLowerCase().includes(q) ||
      (t.status||"").toLowerCase().includes(q)
    );
    renderTraitRows(filtered);
  });

  elB1.addEventListener("click", () => {
    const s = [...state.traits].sort((a,b) => (b.curiosity??(b.value?30:100)) - (a.curiosity??(a.value?30:100)));
    renderTraitRows(s);
  });
  elB2.addEventListener("click", () => {
    const s = [...state.traits].sort((a,b) => (a.dna_path||"").localeCompare(b.dna_path||""));
    renderTraitRows(s);
  });

  function renderTraitRows(arr) {
    const body = document.getElementById("traitsBody");
    body.innerHTML = arr.map(tr => {
      const stClass = tr.status === "contradiction" ? "st-contradiction" :
                      tr.status === "ok" ? "st-ok" : "st-unknown";
      const stText = tr.status || "unknown";
      const val = tr.value == null ? "<span class='muted'>—</span>" : escapeHtml(String(tr.value));
      const notes = tr.notes ? escapeHtml(tr.notes) : "";
      return `
        <tr>
          <td>${escapeHtml(tr.dna_path || "")}</td>
          <td><code>${escapeHtml(tr.trait_key || "")}</code></td>
          <td>${val}</td>
          <td>${Number.isFinite(tr.ucn) ? tr.ucn : 0}</td>
          <td>${Number.isFinite(tr.curiosity) ? tr.curiosity : (tr.value ? 30 : 100)}</td>
          <td><span class="status ${stClass}">${escapeHtml(stText)}</span></td>
          <td>${notes}</td>
        </tr>
      `;
    }).join("");
  }
}

function renderRecentEvidence() {
  if (!state.recentEvents.length) {
    elContent.innerHTML = `<div class="empty">No provenance endpoint yet or no events recorded.</div>`;
    return;
  }
  const rows = state.recentEvents.map(e => `
    <tr>
      <td>${escapeHtml(e.ts || "")}</td>
      <td><code>${escapeHtml(e.trait_key || "")}</code></td>
      <td>${e.old == null ? "—" : escapeHtml(String(e.old))} → ${e.new == null ? "—" : escapeHtml(String(e.new))}</td>
      <td>${escapeHtml(e.source || "")}</td>
      <td>${e.confidence == null ? "—" : (Math.round(e.confidence * 100) + "%")}</td>
      <td>${escapeHtml(e.status || "")}</td>
    </tr>
  `).join("");
  elContent.innerHTML = `
    <div class="row"><span class="muted">Most recent first (limit 50)</span></div>
    <table class="table">
      <thead><tr><th>Timestamp</th><th>Trait</th><th>Change</th><th>Source</th><th>Conf.</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderCuriosityAgenda() {
  if (!state.curiosityTop.length) {
    elContent.innerHTML = `<div class="empty">Curiosity endpoint not found; using fallback from current traits (unknown = high curiosity).</div>`;
    return;
  }
  const items = state.curiosityTop.map((c, i) => `
    <tr>
      <td>${i+1}</td>
      <td><code>${escapeHtml(c.trait_key || "")}</code></td>
      <td>${Number.isFinite(c.curiosity) ? c.curiosity : "—"}</td>
      <td>${escapeHtml(c.reason || "")}</td>
      <td><button class="btn btn-ghost" data-trait="${escapeAttr(c.trait_key||"")}">Focus</button></td>
    </tr>
  `).join("");
  elContent.innerHTML = `
    <table class="table">
      <thead><tr><th>#</th><th>Trait</th><th>Curiosity</th><th>Why</th><th></th></tr></thead>
      <tbody>${items}</tbody>
    </table>
    <div class="muted small" style="margin-top:8px;">Click "Focus" to switch to Unabridged Traits and highlight the row.</div>
  `;

  // Focus handler
  elContent.querySelectorAll("button[data-trait]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-trait");
      // Switch to Unabridged
      const idx = tabs.findIndex(t => t[0] === "Unabridged Traits");
      if (idx >= 0) {
        selectTab(idx);
        // Apply filter
        const flt = document.getElementById("flt");
        if (flt) { flt.value = key; flt.dispatchEvent(new Event("input")); }
      }
    });
  });
}

function renderPaAvatar() {
  const img = state.avatar?.image_url ? `<img src="${escapeAttr(state.avatar.image_url)}" alt="avatar" style="max-width:160px;border-radius:10px;border:1px solid #242a36;" />` : "";
  const desc = state.avatar?.description ? escapeHtml(state.avatar.description) : "—";
  elContent.innerHTML = `
    <div class="row">
      <div class="card">${img || `<div class="empty">No image yet. Backend not wired or PaDNA insufficient.</div>`}</div>
      <div class="card" style="flex:1; min-height:120px;">
        <div class="muted small">Description</div>
        <div style="margin-top:6px; line-height:1.5;">${desc}</div>
      </div>
    </div>
    <div class="muted small" style="margin-top:8px;">Read-only preview. When backend is ready, this tab will auto-display generated avatars & text.</div>
  `;
}

function renderDevLogs() {
  elContent.innerHTML = `
    <div class="empty">No /dev/logs endpoint. This tab is a placeholder for future developer logs.</div>
  `;
}

// ------- Boot -------
async function boot() {
  await fetchConfig();
  state.devMode = loadDev();
  elToggle.checked = state.devMode;
  elToggle.addEventListener("change", () => {
    state.devMode = elToggle.checked;
    saveDev(state.devMode);
    mountTabs();
  });

  // Load everything read-only (if services are up)
  await Promise.allSettled([loadRR(), loadTraits(), loadProvenance()]);
  setBadge(state.rr);
  // Curiosity depends on traits
  await loadCuriosity();
  // Avatar depends on traits as well
  await loadAvatar();

  mountTabs();
}
document.addEventListener("DOMContentLoaded", boot);

// ------- Fallbacks & helpers -------
function fallbackTraits() {
  // Minimal leaf sample; expand later or replace with a static v4.0 JSON bundle.
  return [
    { dna_path: "PaDNA > Eye > Iris Color", trait_key: "eye.iris_color", value: null, ucn: 0, curiosity: 100, status: "unknown", notes: "" },
    { dna_path: "PaDNA > Hair > Natural Color", trait_key: "hair.natural_color", value: null, ucn: 0, curiosity: 100, status: "unknown", notes: "" },
    { dna_path: "PaDNA > Skin > Tone", trait_key: "skin.tone", value: null, ucn: 0, curiosity: 100, status: "unknown", notes: "" },
    { dna_path: "HistDNA > Age > Current Age", trait_key: "age.current", value: null, ucn: 0, curiosity: 100, status: "unknown", notes: "" },
    { dna_path: "PsyDNA > Trust > Baseline", trait_key: "psy.trust.baseline", value: null, ucn: 0, curiosity: 100, status: "unknown", notes: "" },
  ];
}

function synthesizePaDescription(traits) {
  // Build a friendly paragraph from whatever PaDNA we have
  const map = new Map(traits.map(t => [t.trait_key, t.value]));
  const hair = map.get("hair.natural_color");
  const eyes = map.get("eye.iris_color");
  const skin = map.get("skin.tone");
  const age  = map.get("age.current");

  const bits = [];
  if (typeof age === "number") bits.push(`appears to be around ${age}`);
  if (eyes) bits.push(`${eyes} eyes`);
  if (hair) bits.push(`${hair} hair`);
  if (skin) bits.push(`${skin} skin tone`);

  if (!bits.length) return "PaDNA description is not available yet. Add a photo or provide a few physical traits to get a preview.";
  return `Based on current PaDNA, you ${bits.join(", ")}. This will refine as new evidence arrives.`;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) { return String(s).replace(/"/g, "&quot;"); }