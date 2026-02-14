const form = document.getElementById("searchForm");
const input = document.getElementById("q");
const topSel = document.getElementById("top");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

function setStatus(msg, isError=false){
  statusEl.textContent = msg || "";
  statusEl.className = "status" + (isError ? " err" : "");
}
function escapeHtml(s){
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function renderResults(payload){
  resultsEl.innerHTML = "";
  setStatus(`Resultados: ${payload.total}`);
  if(!payload.results.length){
    resultsEl.innerHTML = `<div class="card"><p class="snip">No se encontraron coincidencias.</p></div>`;
    return;
  }
  for(const r of payload.results){
    const html = `
      <article class="card">
        <div class="title">
          <span class="badge">[${String(r.docid).padStart(4,'0')}]</span>
          <span class="cat">(${escapeHtml(r.categoria)})</span>
        </div>
        <p class="snip">${escapeHtml(r.snippet)}</p>
      </article>`;
    resultsEl.insertAdjacentHTML("beforeend", html);
  }
}
async function doSearch(q){
  const top = Number(topSel.value || 10);
  setStatus("Buscando...");
  resultsEl.innerHTML = "";
  const url = `/search?q=${encodeURIComponent(q)}&top=${top}`;
  const res = await fetch(url);
  const data = await res.json();
  if(!res.ok){
    setStatus(data.error || "Error", true);
    resultsEl.innerHTML = `<div class="card"><p class="snip err">${escapeHtml(data.error || "Error")}</p></div>`;
    return;
  }
  renderResults(data);
}
form.addEventListener("submit", (e)=>{
  e.preventDefault();
  const q = input.value.trim();
  if(!q) return;
  doSearch(q);
});

