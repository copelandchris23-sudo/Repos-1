const state = {
  q: "",
  family: "",
  growthHabit: "",
  offset: 0,
  limit: 20,
};

const els = {
  form: document.getElementById("search-form"),
  q: document.getElementById("q"),
  suggest: document.getElementById("suggest"),
  stats: document.getElementById("stats"),
  results: document.getElementById("results"),
  resultCount: document.getElementById("result-count"),
  pager: document.getElementById("pager"),
  family: document.getElementById("family-filter"),
  habits: document.getElementById("habit-filters"),
  file: document.getElementById("file"),
  uploadStatus: document.getElementById("upload-status"),
  reload: document.getElementById("reload-seed"),
  detail: document.getElementById("detail"),
  detailBody: document.getElementById("detail-body"),
  closeDetail: document.getElementById("close-detail"),
};

function params() {
  const query = new URLSearchParams({
    q: state.q,
    family: state.family,
    growth_habit: state.growthHabit,
    limit: String(state.limit),
    offset: String(state.offset),
  });
  return query.toString();
}

async function api(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

function tagList(plant) {
  return [plant.growth_habit, plant.family, plant.duration].filter(Boolean);
}

function renderResults(data) {
  els.resultCount.textContent =
    data.total === 0
      ? "No matching plants"
      : `${data.total.toLocaleString()} plants`;
  if (!data.results.length) {
    els.results.innerHTML = `<li class="empty">Nothing matched that search. Try a genus, a common name, or a trait such as evergreen.</li>`;
    els.pager.innerHTML = "";
    return;
  }
  els.results.innerHTML = data.results
    .map((plant) => {
      const title = plant.common_name || plant.scientific_name;
      const latin = plant.scientific_name ? `<em>${plant.scientific_name}</em>` : "";
      const tags = tagList(plant)
        .map((tag) => `<span class="tag">${tag}</span>`)
        .join("");
      return `<li>
        <article class="result" data-id="${plant.id}">
          <h3>${title}</h3>
          <div>${latin}</div>
          <div class="tags">${tags}</div>
        </article>
      </li>`;
    })
    .join("");
  const prevDisabled = state.offset === 0 ? "disabled" : "";
  const nextDisabled = state.offset + state.limit >= data.total ? "disabled" : "";
  els.pager.innerHTML = `
    <button type="button" data-dir="prev" ${prevDisabled}>Previous</button>
    <button type="button" data-dir="next" ${nextDisabled}>Next</button>
  `;
}

async function runSearch() {
  const data = await api(`/api/search?${params()}`);
  renderResults(data);
}

async function loadFacets() {
  const data = await api("/api/facets");
  const habits = ["Tree", "Shrub", "Subshrub"];
  els.habits.innerHTML = ["All", ...habits]
    .map((habit) => {
      const value = habit === "All" ? "" : habit;
      const active = state.growthHabit === value ? "active" : "";
      return `<button type="button" class="chip ${active}" data-habit="${value}">${habit}</button>`;
    })
    .join("");
  const current = els.family.value;
  els.family.innerHTML =
    `<option value="">All families</option>` +
    data.family
      .slice(0, 60)
      .map(
        (item) =>
          `<option value="${item.value}">${item.value} (${item.count})</option>`
      )
      .join("");
  els.family.value = current;
}

async function loadStats() {
  const data = await api("/api/stats");
  els.stats.textContent = `${data.count.toLocaleString()} plants indexed from ${data.source}`;
}

async function openPlant(id) {
  const plant = await api(`/api/plants/${id}`);
  const fields = [
    ["Scientific name", plant.scientific_name],
    ["Common name", plant.common_name],
    ["Synonyms", plant.synonyms],
    ["Family", plant.family],
    ["Genus", plant.genus],
    ["Growth habit", plant.growth_habit],
    ["Duration", plant.duration],
    ["Native status", plant.native_status],
    ["Mature height (ft)", plant.height_mature_ft],
    ["Leaf retention", plant.leaf_retention],
    ["Flower color", plant.flower_color],
    ["Bloom period", plant.bloom_period],
    ["Drought tolerance", plant.drought_tolerance],
    ["Shade tolerance", plant.shade_tolerance],
    ["Lifespan", plant.lifespan],
    ["USDA symbol", plant.usda_symbol],
  ].filter(([, value]) => value);
  els.detailBody.innerHTML = `
    <h2>${plant.common_name || plant.scientific_name}</h2>
    <p><em>${plant.scientific_name || ""}</em></p>
    <div class="detail-grid">
      ${fields
        .map(([label, value]) => `<div>${label}</div><div>${value}</div>`)
        .join("")}
    </div>
  `;
  els.detail.showModal();
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.q = els.q.value.trim();
  state.offset = 0;
  els.suggest.hidden = true;
  runSearch();
});

els.q.addEventListener("input", async () => {
  const q = els.q.value.trim();
  if (q.length < 2) {
    els.suggest.hidden = true;
    return;
  }
  const data = await api(`/api/suggest?q=${encodeURIComponent(q)}`);
  if (!data.results.length) {
    els.suggest.hidden = true;
    return;
  }
  els.suggest.hidden = false;
  els.suggest.innerHTML = data.results
    .map((item) => {
      const label = item.common_name || item.scientific_name;
      return `<li><button type="button" data-q="${label}">${label} <em>${item.scientific_name}</em></button></li>`;
    })
    .join("");
});

els.suggest.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  els.q.value = button.dataset.q;
  state.q = button.dataset.q;
  state.offset = 0;
  els.suggest.hidden = true;
  runSearch();
});

els.habits.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-habit]");
  if (!button) return;
  state.growthHabit = button.dataset.habit;
  state.offset = 0;
  for (const chip of els.habits.querySelectorAll(".chip")) {
    chip.classList.toggle("active", chip === button);
  }
  runSearch();
});

els.family.addEventListener("change", () => {
  state.family = els.family.value;
  state.offset = 0;
  runSearch();
});

els.results.addEventListener("click", (event) => {
  const card = event.target.closest("[data-id]");
  if (card) openPlant(card.dataset.id);
});

els.pager.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  state.offset += button.dataset.dir === "next" ? state.limit : -state.limit;
  state.offset = Math.max(0, state.offset);
  runSearch();
});

els.file.addEventListener("change", async () => {
  const file = els.file.files[0];
  if (!file) return;
  const body = new FormData();
  body.append("file", file);
  els.uploadStatus.textContent = "Indexing…";
  try {
    const result = await api("/api/upload", { method: "POST", body });
    els.uploadStatus.textContent = `Indexed ${result.count.toLocaleString()} records from ${result.source}.`;
    state.offset = 0;
    await Promise.all([loadStats(), loadFacets(), runSearch()]);
  } catch (error) {
    els.uploadStatus.textContent = error.message;
  }
});

els.reload.addEventListener("click", async () => {
  els.uploadStatus.textContent = "Restoring starter catalog…";
  const result = await api("/api/reload-seed", { method: "POST" });
  els.uploadStatus.textContent = `Restored ${result.count.toLocaleString()} plants.`;
  state.offset = 0;
  await Promise.all([loadStats(), loadFacets(), runSearch()]);
});

els.closeDetail.addEventListener("click", () => els.detail.close());

loadStats();
loadFacets();
runSearch();
