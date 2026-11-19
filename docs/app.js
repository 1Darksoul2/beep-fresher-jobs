const PAGE = 40;
const KEYS = ["q", "role", "city", "type", "source"];
const $ = (id) => document.getElementById(id);
let all = [];
let shown = PAGE;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function ago(iso) {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso)) / 864e5);
  if (isNaN(days)) return "";
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function fill(sel, values, counts) {
  for (const v of values) {
    if (!counts[v]) continue;
    const o = document.createElement("option");
    o.value = v;
    o.textContent = `${v} (${counts[v]})`;
    sel.appendChild(o);
  }
}

function countBy(key) {
  const c = {};
  for (const j of all) if (j[key]) c[j[key]] = (c[j[key]] || 0) + 1;
  return c;
}

function readUrl() {
  const p = new URLSearchParams(location.search);
  for (const k of KEYS) if (p.get(k)) $(k).value = p.get(k);
}

function writeUrl() {
  const p = new URLSearchParams();
  for (const k of KEYS) if ($(k).value) p.set(k, $(k).value);
  history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
}

function filtered() {
  const terms = $("q").value.toLowerCase().split(/\s+/).filter(Boolean);
  const role = $("role").value, city = $("city").value, type = $("type").value, source = $("source").value;
  return all.filter((j) =>
    (!role || j.role === role) &&
    (!city || j.city === city) &&
    (!type || j.type === type) &&
    (!source || j.source === source) &&
    terms.every((t) => j._hay.includes(t))
  );
}

function render() {
  const rows = filtered();
  $("count").textContent = `${rows.length.toLocaleString("en-IN")} of ${all.length.toLocaleString("en-IN")} posts`;
  const list = $("list");
  if (!rows.length) {
    list.innerHTML = `<li class="empty">No posts match these filters.</li>`;
    $("more").hidden = true;
    return;
  }
  list.innerHTML = rows.slice(0, shown).map((j) => `
    <li class="card">
      <a class="title" href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
      <div class="company">${esc(j.company)}${j.location_raw ? " · " + esc(j.location_raw) : ""}</div>
      <div class="chips">
        ${j.type === "Internship" ? `<span class="chip intern">Internship</span>` : `<span class="chip">Job</span>`}
        ${j.role ? `<span class="chip">${esc(j.role)}</span>` : ""}
        ${j.city ? `<span class="chip">${esc(j.city)}</span>` : ""}
        <span class="chip src">${esc(j.source)}${j.posted_at ? " · " + ago(j.posted_at) : ""}</span>
      </div>
    </li>`).join("");
  $("more").hidden = rows.length <= shown;
}

function update() { shown = PAGE; writeUrl(); render(); }

async function init() {
  try {
    const res = await fetch("data/jobs.json", { cache: "no-cache" });
    const data = await res.json();
    all = data.jobs.map((j) => ({ ...j, _hay: [j.title, j.company, j.location_raw, j.role, j.city].join(" ").toLowerCase() }));
    $("updated").textContent = `Updated ${new Date(data.updated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}.`;
    fill($("role"), data.roles, countBy("role"));
    fill($("city"), data.cities, countBy("city"));
    const bySrc = countBy("source");
    const srcNames = Object.keys(bySrc).sort((a, b) => bySrc[b] - bySrc[a]);
    fill($("source"), srcNames, bySrc);
    const companies = new Set(all.map((j) => j.company.toLowerCase())).size;
    $("sources").innerHTML = `<b>${all.length.toLocaleString("en-IN")}</b> posts from <b>${companies.toLocaleString("en-IN")}</b> companies · ` +
      srcNames.map((s) => `${esc(s)} ${bySrc[s]} (${Math.round((bySrc[s] / all.length) * 100)}%)`).join(" · ");
  } catch (e) {
    $("updated").textContent = "Could not load data.";
    return;
  }
  try {
    const run = await (await fetch("data/last_run.json", { cache: "no-cache" })).json();
    if (run.tagging?.model) $("model").textContent = run.tagging.model;
  } catch (_) {}
  readUrl();
  render();
}

let timer;
$("q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(update, 120); });
for (const k of ["role", "city", "type", "source"]) $(k).addEventListener("change", update);
$("more").addEventListener("click", () => { shown += PAGE; render(); });
$("reset").addEventListener("click", () => { for (const k of KEYS) $(k).value = ""; update(); });
init();
