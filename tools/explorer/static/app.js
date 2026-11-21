"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (x) => String(x ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const OUTCOMES = {
  correct: { label: "Correct", cls: "ok", color: "#1E7A46" },
  abstained_correctly: { label: "Abstained correctly", cls: "ok", color: "#1E7A46" },
  confident_wrong: { label: "Wrong but passed", cls: "bad", color: "#B3302A" },
  invented: { label: "Invented", cls: "bad", color: "#B3302A" },
  caught_wrong: { label: "Wrong, caught", cls: "warn", color: "#D69A2D" },
  unverifiable_right: { label: "Right, unusable evidence", cls: "info", color: "#6577C9" },
  missed: { label: "Missed", cls: "", color: "#A4AAB3" },
  invalid: { label: "Invalid output", cls: "", color: "#C9CDD3" },
};
const CATEGORY = {
  scale_or_unit: "Scale or unit", wrong_period_or_column: "Wrong period or column", wrong_item: "Wrong item",
  wrong_line: "Wrong line quoted", wrong_page: "Wrong page cited", span_not_verbatim: "Quote not verbatim",
  missed: "Missed", invalid: "Invalid format", invented: "Invented",
};
const CHECK = { parse: "output does not parse", page: "cited page not shown", span: "quote not on the page", value: "value not in the quote" };
const SLICES = { S1: "Main statements, current", S2: "Main statements, prior", S3: "Quarter vs year-to-date", S4: "Notes", S5: "Segments", S6: "Numbers in prose", S7: "Units and per-share", S8: "Not in the pages" };
const WHY = ["Units stated away from the number", "Many columns on the line", "Period or year-to-date confusion", "Number written in words or prose", "Similar or ambiguous labels", "Segment table", "Question wording unclear", "Answer key looks wrong"];

const state = { set: null, sets: [], models: [], list: [], current: null, detail: null, order: "id", setup: "C1", tab: "key", server: {} };

const outcomeChip = (o) => { const x = OUTCOMES[o] || { label: o || "?", cls: "" }; return `<span class="chip ${x.cls}">${esc(x.label)}</span>`; };
const scoreChip = (ok, n) => {
  if (!n) return `<span class="score">–</span>`;
  const r = ok / n; const cls = r >= 0.7 ? "hi" : r >= 0.4 ? "mid" : "lo";
  return `<span class="score ${cls}" title="${ok} of ${n} models correct (plain setup)">${ok}/${n}</span>`;
};
const fmtPeriod = (p) => !p ? "—" : p.instant ? `As of ${p.instant}` : `${p.start} → ${p.end}`;
const fmtNum = (v) => typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: 4 }) : esc(v);

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2600);
}
function setSegment(el, v) { $$("button", el).forEach((b) => b.classList.toggle("on", b.dataset.v === v)); }

/* ------------------------------------------------------------ boot */
async function boot() {
  [state.sets, state.models] = await Promise.all([api("/api/sets"), api("/api/models")]);
  $("#set-select").innerHTML = state.sets.map((s) => `<option value="${s.key}">${esc(s.title)} · ${s.questions.toLocaleString()} questions</option>`).join("");
  $("#model-select").innerHTML = state.models.map((m) => `<option value="${m.name}">${esc(m.name)}${m.supplementary ? " (suppl.)" : ""}</option>`).join("");
  $("#slice").innerHTML = `<option value="">All</option>` + Object.entries(SLICES).map(([k, v]) => `<option value="${k}">${k} · ${v}</option>`).join("");
  $("#rv-why").innerHTML = WHY.map((w) => `<button type="button" data-v="${esc(w)}">${esc(w)}</button>`).join("");
  bind();
  const link = Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
  state.link = link.q ? link : null;
  if (link.set && state.sets.some((x) => x.key === link.set)) $("#set-select").value = link.set;
  if (link.q) state.current = link.q;
  selectSet($("#set-select").value || state.sets[0].key);
  if (link.q) openQuestion(link.q);
  pollServer();
}

function bind() {
  $("#set-select").onchange = (e) => selectSet(e.target.value);
  let t; $("#search").oninput = () => { clearTimeout(t); t = setTimeout(loadList, 200); };
  ["#company", "#form", "#slice"].forEach((s) => ($(s).onchange = loadList));
  $$("#order button").forEach((b) => (b.onclick = () => { state.order = b.dataset.v; setSegment($("#order"), b.dataset.v); loadList(); }));
  $$("#tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
  $$("#setup button").forEach((b) => (b.onclick = () => { if (!b.disabled) { state.setup = b.dataset.v; setSegment($("#setup"), b.dataset.v); } }));
  $("#load-btn").onclick = loadModel;
  $("#stop-btn").onclick = stopModel;
  $("#model-select").onchange = () => { updateSetupAvailability(); renderLiveNote(); };
  $("#edit-prompt").onchange = (e) => { $("#prompt").readOnly = !e.target.checked; $("#edit-note").hidden = !e.target.checked; if (e.target.checked) $("#prompt-box").open = true; };
  $("#ask-btn").onclick = askModel;
  $$("#rv-gold button, #rv-checker button").forEach((b) => (b.onclick = () => setSegment(b.parentElement, b.dataset.v)));
  $("#rv-why").onclick = (e) => { if (e.target.dataset.v) e.target.classList.toggle("on"); };
  $("#save-review").onclick = saveReview;
  $("#insp-close").onclick = closeInspector;
  $$("#insp-view button").forEach((b) => (b.onclick = () => setInspView(b.dataset.v)));
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if (e.key === "/") { e.preventDefault(); $("#search").focus(); }
    if (e.key === "Escape") closeInspector();
    if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); move(1); }
    if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); move(-1); }
  });
  updateSetupAvailability();
}

function selectSet(key) {
  state.set = key;
  const s = state.sets.find((x) => x.key === key);
  $("#company").innerHTML = `<option value="">All companies</option>` + s.companies.map((c) => `<option value="${c.ticker}">${esc(c.ticker)} · ${esc(c.company)} (${c.questions})</option>`).join("");
  loadList();
}

/* ------------------------------------------------------------ list */
async function loadList() {
  const q = new URLSearchParams({ company: $("#company").value, form: $("#form").value, slice: $("#slice").value, order: state.order, search: $("#search").value.trim() });
  state.list = await api(`/api/sets/${state.set}/questions?${q}`);
  $("#list-count").textContent = `${state.list.length.toLocaleString()} question${state.list.length === 1 ? "" : "s"}`;
  $("#qlist").innerHTML = state.list.map((it) => `
    <div class="qitem${it.id === state.current ? " on" : ""}" data-id="${it.id}">
      <div class="qitem-top"><span class="qitem-id">${it.id}</span>${scoreChip(it.ok, it.n)}<span class="chip">${it.slice}</span><span class="chip">${it.form}</span>
        ${it.wrong_passed ? `<span class="chip bad" title="At least one model gave a wrong answer that passed every check">wrong passed</span>` : ""}
        <span class="spacer"></span>${it.reviewed ? `<span class="dot-rev" title="Reviewed"></span>` : ""}</div>
      <div class="qitem-q">${esc(it.question)}</div>
      <div class="qitem-co">${esc(it.company)}</div>
    </div>`).join("") || `<div class="empty">No questions match these filters.</div>`;
  $$(".qitem").forEach((el) => (el.onclick = () => openQuestion(el.dataset.id)));
  if (!state.current && state.list.length) openQuestion(state.list[0].id);
}
function move(d) {
  const i = state.list.findIndex((x) => x.id === state.current);
  const n = state.list[Math.max(0, Math.min(state.list.length - 1, i + d))];
  if (n && n.id !== state.current) openQuestion(n.id);
}

/* ------------------------------------------------------------ detail */
async function openQuestion(id) {
  state.current = id;
  $$(".qitem").forEach((el) => el.classList.toggle("on", el.dataset.id === id));
  $(`.qitem[data-id="${id}"]`)?.scrollIntoView({ block: "nearest" });
  const d = await api(`/api/sets/${state.set}/questions/${id}`);
  if (state.current !== id) return;
  state.detail = d;
  $("#empty").hidden = true; $("#detail").hidden = false;
  $("#crumbs").innerHTML = `<span>${esc(d.company)}</span><span>·</span><span>${d.form}</span><span>·</span><span>report date ${d.report_date}</span><span>·</span><span class="mono">${d.id}</span>`;
  $("#qtitle").textContent = d.question;
  $("#qmeta").innerHTML = `<span class="chip primary">${d.slice} · ${SLICES[d.slice] || ""}</span>${d.subtype ? `<span class="chip">${esc(d.subtype)}</span>` : ""}
    ${d.score.n ? `<span class="chip">${d.score.ok} of ${d.score.n} models correct (plain)</span>` : ""}
    ${d.edgar ? `<a href="${esc(d.edgar)}" target="_blank" rel="noopener" class="chip info">Open filing on SEC EDGAR ↗</a>` : ""}`;
  $("#ans-count").textContent = d.answers.length || "";
  $("#rev-flag").textContent = d.review ? "✓" : "";
  renderKey(d); renderPages(d); renderAnswers(d); renderLive(d); renderReview(d);
  showTab(state.tab);
  if (state.link && state.link.q === id) {
    const l = state.link; state.link = null;
    if (l.view === "pages") insp.view = "pages";
    if (l.locate === "key") { const t = keyTarget(d); if (t) openInspector(t); }
    else if (l.locate && l.locate.startsWith("model:")) {
      const [, model, setup] = l.locate.split(":");
      const a = d.answers.find((x) => x.model === model && x.setup === setup);
      const t = modelTarget(d, a, `${model} · ${setup}`); if (t) openInspector(t);
    }
  } else if (!$("#inspector").hidden) { const t = keyTarget(d); if (t) openInspector(t); else closeInspector(); }
  history.replaceState(null, "", `#set=${state.set}&q=${id}`);
}
function showTab(tab) {
  state.tab = tab;
  $$("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  $$(".panel").forEach((p) => (p.hidden = p.dataset.panel !== tab));
  if (tab === "pages") $(".pagebox li.hl")?.scrollIntoView({ block: "center" });
}

function renderKey(d) {
  const g = d.gold;
  const dist = {};
  d.answers.filter((a) => a.setup === "C1").forEach((a) => (dist[a.outcome] = (dist[a.outcome] || 0) + 1));
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  const bar = total ? `<div class="bar">${Object.entries(OUTCOMES).filter(([k]) => dist[k]).map(([k, v]) => `<span style="width:${(100 * dist[k]) / total}%;background:${v.color}" title="${v.label}: ${dist[k]}"></span>`).join("")}</div>
    <div class="legend">${Object.entries(OUTCOMES).filter(([k]) => dist[k]).map(([k, v]) => `<span><i style="background:${v.color}"></i>${v.label} ${dist[k]}</span>`).join("")}</div>` : `<p class="muted">No stored answers for this question.</p>`;
  const answer = g.status !== "found"
    ? `<div class="card"><div class="card-head"><h3>Answer key</h3></div><div class="bigvalue" style="color:var(--ink)">not_found</div><p class="muted">The requested item or period is not on the pages given to the model. The correct response is to say so.</p></div>`
    : `<div class="card"><div class="card-head"><h3>Answer key</h3><button class="locate-btn" data-locate="key">Show in filing ↗</button></div>
        <div class="bigvalue"><span class="locatable" data-locate="key" title="Show where this value is in the filing">${esc(g.display)}</span></div>
        <div class="muted small">from the filer's inline XBRL tag</div><div class="muted" style="margin:4px 0 16px">${esc(g.scale_words)} · ${esc(g.unit)}${g.negative ? " · negative in XBRL (sign is not graded)" : ""}</div>
        <dl class="kv">
          <dt>Full value</dt><dd class="mono">${fmtNum(g.value)}</dd>
          <dt>Period</dt><dd>${esc(fmtPeriod(g.period))}</dd>
          <dt>Segment</dt><dd>${g.dims.length ? g.dims.map((x) => `<span class="chip">${esc(x.member)}</span>`).join(" ") : "—"}</dd>
          <dt>XBRL concept</dt><dd><code>${esc(g.concept)}</code></dd>
          <dt>Filer's label</dt><dd>${esc(g.label)}</dd>
        </dl></div>`;
  const evidence = g.status === "found"
    ? `<div class="card"><div class="card-head"><h3>Evidence</h3><span class="muted small">page ${esc(g.evidence_page)}</span></div><div class="evidence locatable" data-locate="key" title="Show in the filing">${esc(g.evidence_line)}</div>
       <p class="muted small" style="margin-top:10px">A correct answer quotes this line (or a verbatim part of it) and cites page ${esc(g.evidence_page)}.</p></div>`
    : "";
  $("#panel-key").innerHTML = `<div class="grid-2">${answer}<div>${evidence}<div class="card"><div class="card-head"><h3>How the models did</h3><span class="muted small">plain setup</span></div>${bar}</div></div></div>`;
  bindLocate($("#panel-key"), (k) => (k === "key" ? keyTarget(d) : null));
}

function renderPages(d) {
  const answerIdx = Math.max(0, d.pages.findIndex((p) => p.is_answer));
  const tabs = d.pages.map((p, i) => `<button data-i="${i}" class="${i === answerIdx ? "on" : ""}">Page ${esc(p.label)}${p.is_answer ? " · answer" : ""}</button>`).join("");
  $("#panel-pages").innerHTML = `<p class="muted small" style="margin-top:0">The three pages exactly as the models saw them, in the order they were given. The answer line is highlighted.</p>
    <div class="page-tabs">${tabs}</div><div class="pagebox" id="pagebox"></div>`;
  const show = (i) => {
    const p = d.pages[i];
    $("#pagebox").innerHTML = `<ol>${p.text.split("\n").map((ln, j) => `<li class="${j === p.highlight_line ? "hl" : ""}">${esc(ln) || " "}</li>`).join("")}</ol>`;
    $$("#panel-pages .page-tabs button").forEach((b) => b.classList.toggle("on", +b.dataset.i === i));
    $("#pagebox li.hl")?.scrollIntoView({ block: "center" });
  };
  $$("#panel-pages .page-tabs button").forEach((b) => (b.onclick = () => show(+b.dataset.i)));
  show(answerIdx);
}

function renderAnswers(d, filter = "all") {
  if (!d.answers.length) { $("#panel-answers").innerHTML = `<div class="card"><p class="muted">No stored benchmark answers for this question.</p></div>`; return; }
  const rows = d.answers.filter((a) => filter === "all" || a.setup === filter);
  const seg = ["all", "C1", "C2", "C3"].map((v) => `<button data-v="${v}" class="${v === filter ? "on" : ""}">${v === "all" ? "All setups" : v}</button>`).join("");
  $("#panel-answers").innerHTML = `<div class="toolbar"><div class="segmented" id="ans-filter">${seg}</div><span class="muted small">Click a row for the raw output and reasoning.</span></div>
    <table class="data"><thead><tr><th>Model</th><th>Setup</th><th>Outcome</th><th>Value</th><th>Scale</th><th>Page</th><th>Quoted line</th><th>Why</th></tr></thead><tbody>
    ${rows.map((a, i) => `<tr class="row" data-i="${i}"><td><b>${esc(a.model)}</b></td><td>${a.setup}</td><td>${outcomeChip(a.outcome)}</td>
      <td class="mono">${a.status === "found" && a.span ? `<span class="locatable" data-locate="${i}" title="Show where this answer is in the filing">${esc(a.value)}</span>` : a.status === "not_found" ? "not_found" : esc(a.value)}</td><td>${esc(a.scale || "")}</td><td>${esc(a.page ?? "")}</td>
      <td><div class="quote${a.span ? " locatable" : ""}" ${a.span ? `data-locate="${i}"` : ""} title="${esc(a.span)}">${esc(a.span || "")}</div></td>
      <td>${esc(CATEGORY[a.category] || "")}${a.failed_check ? `<div class="muted small">check: ${esc(CHECK[a.failed_check] || a.failed_check)}</div>` : ""}</td></tr>
      <tr class="expand" data-for="${i}" hidden><td colspan="8">
        ${a.retried ? `<div class="sub-h">Retried after a failed check · final answer shown</div>` : ""}
        <div class="sub-h">Raw output · ${esc(a.tokens)} tokens · ${esc(a.seconds)} s</div><pre class="block">${esc(a.raw)}</pre>
        ${a.reasoning ? `<div class="sub-h">Reasoning</div><pre class="block">${esc(a.reasoning)}</pre>` : ""}</td></tr>`).join("")}
    </tbody></table>`;
  $$("#ans-filter button").forEach((b) => (b.onclick = () => renderAnswers(d, b.dataset.v)));
  $$("#panel-answers tr.row").forEach((r) => (r.onclick = () => { const e = $(`#panel-answers tr.expand[data-for="${r.dataset.i}"]`); e.hidden = !e.hidden; }));
  bindLocate($("#panel-answers"), (k) => modelTarget(d, rows[+k], `${rows[+k].model} · ${rows[+k].setup}`));
}

/* ------------------------------------------------------------ live */
function selectedModel() { return state.models.find((m) => m.name === $("#model-select").value); }
function updateSetupAvailability() {
  const m = selectedModel(); const c3 = $('#setup button[data-v="C3"]');
  c3.disabled = !(m && m.thinking);
  c3.title = c3.disabled ? "This model has no thinking mode" : "";
  if (c3.disabled && state.setup === "C3") { state.setup = "C1"; setSegment($("#setup"), "C1"); }
}
function renderLiveNote() {
  const s = state.server, m = $("#model-select").value;
  $("#live-model-note").textContent = s.state === "ready" ? (s.model === m ? `Using ${s.model}` : `Loaded: ${s.model} · selected: ${m}`) : "No model loaded";
}
function renderLive(d) {
  $("#prompt").value = d.prompt;
  $("#edit-prompt").checked = false; $("#prompt").readOnly = true; $("#edit-note").hidden = true;
  $("#live-result").innerHTML = "";
  renderLiveNote();
}

async function askModel() {
  const d = state.detail, s = state.server, m = $("#model-select").value;
  if (s.state !== "ready" || s.model !== m) {
    $("#live-result").innerHTML = `<div class="notice"><span>${s.state === "loading" ? `Still loading ${esc(s.model)}…` : `Load <b>${esc(m)}</b> first (top right), then ask.`}</span>${s.state === "loading" ? "" : `<button class="btn" onclick="loadModel()">Load ${esc(m)}</button>`}</div>`;
    return;
  }
  const btn = $("#ask-btn"); btn.disabled = true;
  $("#live-result").innerHTML = `<div class="card"><span class="spinner"></span>Asking ${esc(m)} (${state.setup})…${state.setup === "C3" ? " Thinking can take a few minutes." : ""}</div>`;
  const edited = $("#edit-prompt").checked;
  try {
    const r = await api(`/api/sets/${state.set}/questions/${d.id}/ask`, { method: "POST", body: JSON.stringify({ model: m, setup: state.setup, prompt: edited ? $("#prompt").value : null }) });
    if (state.detail.id !== d.id) return;
    renderLiveResult(d, r, m);
  } catch (e) {
    $("#live-result").innerHTML = `<div class="notice">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
}

function renderLiveResult(d, r, model) {
  if (r.error) { $("#live-result").innerHTML = `<div class="notice">${esc(r.error)}</div>`; return; }
  setTimeout(() => bindLocate($("#live-result"), (k) => (k === "key" ? keyTarget(d) : modelTarget(d, { ...r.answer }, `${model} · live`))), 0);
  const g = d.gold, a = r.answer;
  const key = g.status === "found"
    ? { value: g.display, scale: g.scale_words, page: g.evidence_page, span: g.evidence_line }
    : { value: "not_found", scale: "—", page: "—", span: "—" };
  const ans = a.status === "not_found" ? { value: "not_found", scale: "—", page: "—", span: "—" } : { value: a.value, scale: a.scale, page: a.page, span: a.span };
  const row = (k, mv, kv, same) => k === "Value"
    ? `<div class="k">${k}</div><div class="${same === null ? "" : same ? "match" : "diff"}">${a.status === "found" && a.span ? `<span class="locatable" data-locate="live" title="Show in the filing">${esc(mv)}</span>` : esc(mv)}</div><div>${g.status === "found" ? `<span class="locatable" data-locate="key" title="Show in the filing">${esc(kv)}</span>` : esc(kv)}</div>`
    : `<div class="k">${k}</div><div class="${same === null ? "" : same ? "match" : "diff"}">${esc(mv)}</div><div>${esc(kv)}</div>`;
  const sameVal = r.matches_key === true || (g.status !== "found" && a.status === "not_found");
  const samePage = g.status === "found" && String(a.page) === String(g.evidence_page);
  const stored = r.stored ? `<span class="chip ${r.stored.same_outcome ? "ok" : "warn"}">${r.stored.same_outcome ? "Same outcome as the stored benchmark answer" : `Stored benchmark answer was: ${OUTCOMES[r.stored.outcome]?.label || r.stored.outcome}`}</span>` : "";
  $("#live-result").innerHTML = `
    <div class="card">
      <div class="verdict">${outcomeChip(r.outcome)}<span class="big">${esc(OUTCOMES[r.outcome]?.label || r.outcome)}</span>
        ${r.category ? `<span class="chip">${esc(CATEGORY[r.category] || r.category)}</span>` : ""}${r.edited ? `<span class="chip warn">Edited prompt · not comparable</span>` : ""}${r.retried ? `<span class="chip info">Retried after a failed check</span>` : ""}${stored}</div>
      <div class="grid-2" style="margin-top:16px">
        <div><div class="sub-h" style="margin-top:0">Model answer vs answer key</div>
          <div class="compare"><div class="h"></div><div class="h">${esc(model)}</div><div class="h">Answer key</div>
            ${row("Value", ans.value, key.value, sameVal)}${row("Scale", ans.scale, key.scale, null)}${row("Page", ans.page, key.page, g.status === "found" ? samePage : null)}
            <div class="k">Quoted line</div><div class="mono">${esc(ans.span)}</div><div class="mono">${esc(key.span)}</div></div></div>
        <div><div class="sub-h" style="margin-top:0">Automatic checks</div>
          <div class="steps">${r.steps.map((s) => `<div class="step ${s.state === "n/a" ? "na" : s.state}"><b>${s.state === "pass" ? "✓" : s.state === "fail" ? "✕" : "–"}</b>${esc(s.label)}${s.state === "n/a" ? " (not applicable)" : s.state === "skipped" ? " (not reached)" : ""}</div>`).join("")}</div>
          <p class="muted small" style="margin-top:12px">Passing every check does not mean the answer is right: the checks confirm the evidence, the answer key confirms the value.</p></div>
      </div>
    </div>
    ${r.attempts.map((t, i) => `<div class="card"><div class="card-head"><h3>Attempt ${i + 1}</h3><span class="muted small">${esc(t.tokens)} tokens · ${esc(t.seconds)} s</span></div>
      ${t.retry_message ? `<div class="sub-h" style="margin-top:0">Retry message sent</div><pre class="block">${esc(t.retry_message)}</pre>` : ""}
      <div class="sub-h">Raw output</div><pre class="block">${esc(t.content)}</pre>
      ${t.reasoning ? `<details><summary class="sub-h" style="cursor:pointer">Reasoning (${t.reasoning.length.toLocaleString()} characters)</summary><pre class="block">${esc(t.reasoning)}</pre></details>` : ""}</div>`).join("")}
    <p class="muted small">Click a value above to see it in the filing. Logged to <code>${esc(r.logged_to)}</code>${r.revision ? ` · model revision <code>${esc(r.revision.slice(0, 12))}</code>` : ""}</p>`;
}

/* ------------------------------------------------------------ server */
async function pollServer() {
  try { state.server = await api("/api/server"); } catch { state.server = { state: "error", message: "Explorer backend not reachable" }; }
  const s = state.server;
  $("#server-dot").className = `status-dot ${s.state}`;
  $("#server-msg").textContent = s.state === "loading" ? `Loading ${s.model}… ${s.elapsed || 0} s` : s.message;
  $("#server-msg").title = s.message || "";
  $("#load-btn").disabled = s.state === "loading";
  $("#stop-btn").disabled = s.state !== "ready";
  if (s.state === "ready" && s.model && !pollServer.synced) { $("#model-select").value = s.model; pollServer.synced = true; updateSetupAvailability(); }
  renderLiveNote();
  setTimeout(pollServer, s.state === "loading" ? 1500 : 4000);
}
async function loadModel() {
  const m = $("#model-select").value;
  if (state.server.state === "ready" && state.server.model === m) { toast(`${m} is already loaded`); return; }
  state.server = await api("/api/server/load", { method: "POST", body: JSON.stringify({ model: m }) });
  pollServer.synced = true;
  toast(`Loading ${m}. This usually takes 1–3 minutes.`);
}
async function stopModel() {
  $("#server-msg").textContent = "Stopping…";
  state.server = await api("/api/server/stop", { method: "POST" });
  toast("Model stopped. The GPU is free.");
}

/* ------------------------------------------------------------ review */
function renderReview(d) {
  const r = d.review || {};
  setSegment($("#rv-gold"), r.gold_correct || ""); setSegment($("#rv-checker"), r.agree_with_checker || "");
  $$("#rv-why button").forEach((b) => b.classList.toggle("on", (r.why_hard || []).includes(b.dataset.v)));
  $("#rv-note").value = r.note || "";
  $("#review-when").textContent = d.review ? `Last saved ${d.review.time.replace("T", " ").replace("+00:00", " UTC")}` : "Not reviewed yet";
}
async function saveReview() {
  const d = state.detail;
  const body = {
    gold_correct: $("#rv-gold button.on")?.dataset.v || null, agree_with_checker: $("#rv-checker button.on")?.dataset.v || null,
    why_hard: $$("#rv-why button.on").map((b) => b.dataset.v), note: $("#rv-note").value.trim(),
  };
  if (!body.gold_correct) { toast("Choose whether the answer key is correct."); return; }
  const r = await api(`/api/sets/${state.set}/questions/${d.id}/review`, { method: "POST", body: JSON.stringify(body) });
  d.review = r.saved; renderReview(d);
  $("#rev-flag").textContent = "✓"; $("#review-count").textContent = `${r.reviewed} question${r.reviewed === 1 ? "" : "s"} reviewed in this set`;
  const it = state.list.find((x) => x.id === d.id); if (it && !it.reviewed) { it.reviewed = true; $(`.qitem[data-id="${d.id}"] .spacer`)?.insertAdjacentHTML("afterend", `<span class="dot-rev" title="Reviewed"></span>`); }
  toast("Review saved");
}

/* ------------------------------------------------------------ side-by-side source (inspector) */
const insp = { accession: null, ready: false, pending: [], view: "filing", req: 0, timer: null, last: null };
const squash = (s) => String(s || "").replace(/[\s$]/g, "").toLowerCase();

function keyTarget(d) {
  const g = d.gold;
  if (g.status !== "found") return null;
  return { kind: "key", label: "Answer key (XBRL)", factIndex: g.fact_index, span: g.evidence_line, value: g.display, page: g.evidence_page };
}
function modelTarget(d, a, label) {
  if (!a || a.status !== "found" || !a.span) return null;
  const g = d.gold, samePage = g.status === "found" && String(a.page) === String(g.evidence_page);
  return { kind: "model", label, span: a.span, value: a.value, page: a.page, nearFact: samePage ? g.fact_index : null };
}
function bindLocate(scope, resolve) {
  $$("[data-locate]", scope).forEach((el) => (el.onclick = (e) => {
    e.stopPropagation();
    const t = resolve(el.dataset.locate);
    if (t) openInspector(t); else toast("Nothing to locate for this answer.");
  }));
}
function openInspector(t) {
  const d = state.detail;
  $(".layout").classList.add("with-inspector"); $("#inspector").hidden = false;
  $("#insp-title").textContent = `${t.label}: ${t.value}`;
  $("#insp-status").innerHTML = `<span class="spinner"></span>Finding it in ${esc(d.company)}'s ${esc(d.form)}…`;
  const key = keyTarget(d);
  const msgs = t.kind === "model" && key ? [key, t] : [t];   // show the answer key alongside a model answer
  renderInspectorPages(d, msgs);
  if (insp.accession !== d.accession) {
    insp.accession = d.accession; insp.ready = false; insp.pending = msgs;
    $("#insp-frame").src = `/filing/${encodeURIComponent(d.accession)}`;
    clearTimeout(insp.timer);
    insp.timer = setTimeout(() => { if (!insp.ready) $("#insp-status").innerHTML = `<span class="bad">The original filing is not stored on this machine.</span> Use "Pages shown to the model".`; }, 20000);
  } else if (!insp.ready) insp.pending = msgs;
  else msgs.forEach(sendLocate);
  setInspView(insp.view);
}
function sendLocate(t) {
  insp.req += 1; insp.last = { id: insp.req, t };
  $("#insp-frame").contentWindow.postMessage({ type: "fe-locate", id: insp.req, kind: t.kind, factIndex: t.factIndex ?? null, span: t.span, value: t.value, nearFact: t.nearFact ?? null }, "*");
}
window.addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.type === "fe-ready") { insp.ready = true; clearTimeout(insp.timer); const p = insp.pending; insp.pending = []; p.forEach(sendLocate); }
  if (m.type === "fe-located" && insp.last && m.id === insp.last.id) {
    const t = insp.last.t;
    $("#insp-status").innerHTML = m.found
      ? `<span class="ok">Found</span> · ${esc(m.how)}${t.page != null ? ` · cited page ${esc(t.page)}` : ""}${m.note ? ` · <span class="muted">${esc(m.note)}</span>` : ""}`
      : `<span class="bad">Not found in the original filing.</span> The quoted line may not exist verbatim; check "Pages shown to the model".`;
  }
});
function closeInspector() { $("#inspector").hidden = true; $(".layout").classList.remove("with-inspector"); }
function setInspView(v) {
  insp.view = v; setSegment($("#insp-view"), v);
  $("#insp-frame").hidden = v !== "filing"; $("#insp-pages").hidden = v !== "pages";
  if (v === "pages") $("#insp-pages li.hl-model, #insp-pages li.hl-key")?.scrollIntoView({ block: "center" });
}
function renderInspectorPages(d, targets) {
  const marks = d.pages.map(() => ({}));
  for (const t of targets) {
    d.pages.forEach((p, i) => {
      if (String(p.label) !== String(t.page)) return;
      const lines = p.text.split("\n");
      let j = t.kind === "key" ? p.highlight_line : -1;
      if (j == null || j < 0) {
        const s = squash(t.span);
        j = lines.findIndex((ln) => s && squash(ln).includes(s));
        if (j < 0) j = lines.findIndex((ln) => s && squash(ln).length > 12 && s.includes(squash(ln)));
      }
      if (j >= 0) marks[i][j] = (marks[i][j] || "") + ` hl-${t.kind}`;
    });
  }
  $("#insp-pages").innerHTML = d.pages.map((p, i) => `<div class="phead">=== PAGE ${esc(p.label)} ===${p.is_answer ? " · contains the answer" : ""}</div>
    <ol>${p.text.split("\n").map((ln, j) => `<li class="${marks[i][j] || ""}">${esc(ln) || " "}</li>`).join("")}</ol>`).join("");
}

boot().catch((e) => { document.body.innerHTML = `<p style="padding:40px">Could not start the Explorer: ${esc(e.message)}</p>`; });
