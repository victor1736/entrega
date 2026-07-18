// Dashboard estilo feed — consume la API REST del mismo origen.
const REFRESH_MS = 30000;
const PAGE_SIZE = 8;

let hourlyChart, distChart;
let state = { minMag: null, sortBy: "event_time", location: "", page: 1 };

const $ = (id) => document.getElementById(id);

const SEV = [
  { max: 2, name: "micro", color: "#10b981" },
  { max: 4, name: "menor", color: "#84cc16" },
  { max: 5, name: "ligero", color: "#eab308" },
  { max: 6, name: "moderado", color: "#f59e0b" },
  { max: 7, name: "fuerte", color: "#f97316" },
  { max: 8, name: "mayor", color: "#ef4444" },
  { max: 99, name: "grande", color: "#b91c1c" },
];
function sev(mag) {
  if (mag == null) return { name: "s/d", color: "#8a9099" };
  return SEV.find((s) => mag < s.max) || SEV[SEV.length - 1];
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}
function timeAgo(iso) {
  if (!iso) return "";
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 3600) return `hace ${Math.max(1, Math.round(secs / 60))} min`;
  if (secs < 86400) return `hace ${Math.round(secs / 3600)} h`;
  return `hace ${Math.round(secs / 86400)} d`;
}

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}
function setStatus(ok) {
  $("statusDot").className = "dot " + (ok ? "ok" : "err");
  $("statusText").textContent = ok ? "En línea" : "Sin conexión";
}

async function loadSummary() {
  const s = await getJSON("/metrics/summary");
  $("kpiTotal").textContent = (s.total_events ?? 0).toLocaleString("es");
  $("kpiAvg").textContent = s.avg_magnitude != null ? s.avg_magnitude.toFixed(2) : "—";
  $("kpiMax").textContent = s.max_magnitude != null ? s.max_magnitude.toFixed(1) : "—";
  $("kpiWindows").textContent = s.total_windows ?? 0;
}

function eqCard(e) {
  const s = sev(e.magnitude);
  const mag = e.magnitude != null ? e.magnitude.toFixed(1) : "—";
  const maps = `https://www.google.com/maps/search/?api=1&query=${e.latitude},${e.longitude}`;
  return `
  <article class="card post">
    <div class="post-head">
      <div class="mag-avatar" style="background:${s.color}">${mag}<small>MAG</small></div>
      <div class="post-meta">
        <div class="post-loc">${e.location ?? "Ubicación desconocida"}</div>
        <div class="post-sub">
          <span class="sev-chip" style="background:${s.color}22;color:${s.color}">${s.name}</span>
          <span>${timeAgo(e.event_time)}</span>
          <span>· ${fmtDate(e.event_time)}</span>
        </div>
      </div>
      <div class="post-actions">
        <a class="map-link" href="${maps}" target="_blank" rel="noopener">📍 Ver mapa</a>
      </div>
    </div>
    <div class="post-body">
      <div class="field"><span>Profundidad</span><b>${e.depth != null ? e.depth.toFixed(1) + " km" : "—"}</b></div>
      <div class="field"><span>Latitud</span><b>${e.latitude.toFixed(3)}</b></div>
      <div class="field"><span>Longitud</span><b>${e.longitude.toFixed(3)}</b></div>
      <div class="field"><span>Ventana</span><b>${e.window}h</b></div>
    </div>
  </article>`;
}

async function loadFeed(reset = true) {
  if (reset) state.page = 1;
  let path = `/earthquakes?page=${state.page}&page_size=${PAGE_SIZE}&sort_by=${state.sortBy}&sort_dir=desc`;
  if (state.minMag != null) path += `&min_magnitude=${state.minMag}`;
  if (state.location) path += `&location=${encodeURIComponent(state.location)}`;

  const data = await getJSON(path);
  const feed = $("feed");
  const html = data.items.map(eqCard).join("");

  if (reset) {
    feed.innerHTML = data.items.length
      ? html
      : `<div class="card feed-empty">Sin eventos que coincidan. La ingesta corre cada 3 min.</div>`;
  } else {
    feed.insertAdjacentHTML("beforeend", html);
  }
  $("feedMeta").textContent = `${data.meta.total} eventos · página ${data.meta.page}/${data.meta.total_pages || 1}`;
  $("loadMore").style.display = data.meta.page < data.meta.total_pages ? "block" : "none";
}

async function loadDistribution() {
  const data = await getJSON("/metrics?page=1&page_size=200");
  const totals = {};
  data.items.forEach((m) =>
    Object.entries(m.magnitude_distribution || {}).forEach(([k, v]) => (totals[k] = (totals[k] || 0) + v))
  );
  const order = ["micro", "minor", "light", "moderate", "strong", "major", "great", "unknown"];
  const colors = ["#10b981","#84cc16","#eab308","#f59e0b","#f97316","#ef4444","#b91c1c","#8a9099"];
  const labels = [], values = [], cols = [];
  order.forEach((k, i) => { if (totals[k]) { labels.push(k); values.push(totals[k]); cols.push(colors[i]); } });

  if (distChart) { distChart.data.labels = labels; distChart.data.datasets[0].data = values; distChart.data.datasets[0].backgroundColor = cols; distChart.update(); return; }
  distChart = new Chart($("distChart"), {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: cols, borderWidth: 2, borderColor: "#fff" }] },
    options: { cutout: "64%", plugins: { legend: { position: "bottom", labels: { color: "#4a4f57", boxWidth: 10, font: { family: "Inter", size: 11 } } } } },
  });
}

async function loadHourly() {
  const data = await getJSON("/metrics?page=1&page_size=12");
  const m = data.items.slice().reverse();
  const labels = m.map((x) => x.window.slice(8) + "h");
  const counts = m.map((x) => x.earthquake_count);
  if (hourlyChart) { hourlyChart.data.labels = labels; hourlyChart.data.datasets[0].data = counts; hourlyChart.update(); return; }
  hourlyChart = new Chart($("hourlyChart"), {
    type: "bar",
    data: { labels, datasets: [{ data: counts, backgroundColor: "#2f6df6", borderRadius: 6, barThickness: 14 }] },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#8a9099", font: { size: 10 } } },
        y: { grid: { color: "#eef0f3" }, ticks: { color: "#8a9099", font: { size: 10 }, precision: 0 }, beginAtZero: true },
      },
    },
  });
}

async function loadReports() {
  const data = await getJSON("/reports?page=1&page_size=6");
  const box = $("reportsList");
  if (!data.items.length) { box.innerHTML = `<p class="muted small" style="padding:0 18px 14px">Aún no hay reportes. El DAG de Airflow los genera cada hora.</p>`; return; }
  box.innerHTML = data.items.map((r) => `
    <div class="report-item">
      <div class="rt">${r.window}h · ${r.total_events} eventos</div>
      <div class="rd">${fmtDate(r.generated_at)}</div>
      <div class="rstats">
        <span>Prom. <b>${r.average_magnitude ?? "—"}</b></span>
        <span>Máx. <b>${r.max_magnitude ?? "—"}</b></span>
      </div>
      <div class="tags">${(r.top_locations || []).map((l) => `<span class="tag">${l}</span>`).join("")}</div>
    </div>`).join("");
}

async function refreshAll() {
  try {
    await Promise.all([loadSummary(), loadFeed(true), loadDistribution(), loadHourly(), loadReports()]);
    setStatus(true);
  } catch (e) { console.error(e); setStatus(false); }
}

// Eventos UI
$("applyFilter").addEventListener("click", () => {
  const v = parseFloat($("minMag").value);
  state.minMag = isNaN(v) ? null : v;
  state.sortBy = $("sortBy").value;
  loadFeed(true);
});
$("loadMore").addEventListener("click", () => { state.page++; loadFeed(false); });
let searchT;
$("searchInput").addEventListener("input", (e) => {
  clearTimeout(searchT);
  searchT = setTimeout(() => { state.location = e.target.value.trim(); loadFeed(true); }, 400);
});

refreshAll();
setInterval(() => { loadSummary(); loadDistribution(); loadHourly(); loadReports(); if (state.page === 1) loadFeed(true); }, REFRESH_MS);
