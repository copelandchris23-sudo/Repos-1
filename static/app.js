function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const state = {
  q: "",
  filters: {},
  familyQuery: "",
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
  activeFilters: document.getElementById("active-filters"),
  pager: document.getElementById("pager"),
  groups: document.getElementById("filter-groups"),
  clear: document.getElementById("clear-filters"),
  file: document.getElementById("file"),
  uploadStatus: document.getElementById("upload-status"),
  reload: document.getElementById("reload-seed"),
  detail: document.getElementById("detail"),
  detailBody: document.getElementById("detail-body"),
  closeDetail: document.getElementById("close-detail"),
};

function selectedValues(key) {
  return state.filters[key] || [];
}

function isSelected(key, value) {
  return selectedValues(key).includes(value);
}

function queryParams({ includePaging = true } = {}) {
  const query = new URLSearchParams();
  if (state.q) query.set("q", state.q);
  for (const [key, values] of Object.entries(state.filters)) {
    for (const value of values) query.append(key, value);
  }
  if (includePaging) {
    query.set("limit", String(state.limit));
    query.set("offset", String(state.offset));
  }
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
  return [
    plant.growth_habit,
    plant.conservation_status,
    plant.usda_hardiness_zone ? `Zone ${plant.usda_hardiness_zone}` : "",
    plant.family,
    plant.leaf_retention,
  ].filter(Boolean);
}

function renderActiveFilters(groups) {
  const labels = {};
  for (const group of groups || []) {
    for (const option of group.options || []) {
      labels[`${group.key}:${option.value}`] = `${group.label}: ${option.label}`;
    }
  }
  const chips = [];
  for (const [key, values] of Object.entries(state.filters)) {
    for (const value of values) {
      const label = labels[`${key}:${value}`] || `${key}: ${value}`;
      chips.push(
        `<button type="button" class="filter-chip" data-key="${esc(key)}" data-value="${esc(value)}">${esc(label)} <span aria-hidden="true">×</span></button>`
      );
    }
  }
  els.activeFilters.innerHTML = chips.join("");
}

function renderResults(data) {
  els.resultCount.textContent =
    data.total === 0
      ? "No matching plants"
      : `${data.total.toLocaleString()} plants match these characteristics`;
  renderActiveFilters(state.facetGroups);
  if (!data.results.length) {
    els.results.innerHTML = `<li class="empty">Nothing matched. Clear a filter or try a broader trait, such as growth habit or leaf persistence.</li>`;
    els.pager.innerHTML = "";
    return;
  }

  const grouped = [];
  for (const plant of data.results) {
    const genus = plant.genus || plant.scientific_name.split(" ")[0] || "Unknown";
    const last = grouped[grouped.length - 1];
    if (!last || last.genus !== genus) grouped.push({ genus, plants: [plant] });
    else last.plants.push(plant);
  }

  els.results.innerHTML = grouped
    .map((group) => {
      const items = group.plants
        .map((plant) => {
          const title = esc(plant.common_name || plant.scientific_name);
          const latin = plant.scientific_name
            ? `<em>${esc(plant.scientific_name)}</em>`
            : "";
          const tags = tagList(plant)
            .map((tag) => `<span class="tag">${esc(tag)}</span>`)
            .join("");
          const blurb = plant.blurb ? `<p class="blurb">${esc(plant.blurb)}</p>` : "";
          return `<li>
        <article class="result" data-id="${plant.id}">
          <h3>${title}</h3>
          <div>${latin}</div>
          ${blurb}
          <div class="tags">${tags}</div>
        </article>
      </li>`;
        })
        .join("");
      return `<li class="genus-group"><h3 class="genus-heading">${esc(group.genus)}</h3><ol>${items}</ol></li>`;
    })
    .join("");
  const prevDisabled = state.offset === 0 ? "disabled" : "";
  const nextDisabled = state.offset + state.limit >= data.total ? "disabled" : "";
  els.pager.innerHTML = `
    <button type="button" data-dir="prev" ${prevDisabled}>Previous</button>
    <button type="button" data-dir="next" ${nextDisabled}>Next</button>
  `;
}

function optionMarkup(group, option) {
  const checked = isSelected(group.key, option.value);
  const disabled = option.count === 0 && !checked ? "disabled" : "";
  const compact = group.key === "hardiness_zone" ? " compact" : "";
  return `<label class="check${compact}${checked ? " is-on" : ""}">
    <input type="checkbox" data-filter="${esc(group.key)}" value="${esc(option.value)}" ${checked ? "checked" : ""} ${disabled} />
    <span class="check-label">${esc(option.label)}</span>
    <span class="check-count">${option.count.toLocaleString()}</span>
  </label>`;
}

function renderFilters(data) {
  state.facetGroups = data.groups || [];
  const familyFocus = document.activeElement && document.activeElement.id === "family-filter-q";
  const familyQuery = state.familyQuery;
  els.groups.innerHTML = state.facetGroups
    .map((group) => {
      let options = group.options || [];
      let search = "";
      if (group.dynamic) {
        search = `<input id="family-filter-q" type="search" placeholder="Find a family" value="${esc(familyQuery)}" />`;
        if (familyQuery) {
          const needle = familyQuery.toLowerCase();
          options = options.filter((option) => option.label.toLowerCase().includes(needle));
        }
      }
      const extraClass = group.key === "hardiness_zone" ? " check-grid" : "";
      return `<section class="filter-group" data-group="${esc(group.key)}">
        <h2>${esc(group.label)}</h2>
        ${search}
        <div class="check-list${extraClass}">
          ${options.map((option) => optionMarkup(group, option)).join("") || `<p class="filter-empty">No values for the current list.</p>`}
        </div>
      </section>`;
    })
    .join("");
  if (familyFocus) {
    const input = document.getElementById("family-filter-q");
    if (input) {
      input.focus();
      input.setSelectionRange(familyQuery.length, familyQuery.length);
    }
  }
  renderActiveFilters(state.facetGroups);
}

async function runSearch() {
  const data = await api(`/api/search?${queryParams()}`);
  renderResults(data);
}

async function loadFacets() {
  const data = await api(`/api/facets?${queryParams({ includePaging: false })}`);
  renderFilters(data);
  return data;
}

async function refresh() {
  await Promise.all([loadFacets(), runSearch()]);
}

async function loadStats() {
  const data = await api("/api/stats");
  els.stats.textContent = `${data.count.toLocaleString()} plants indexed from ${data.source}`;
}

async function openPlant(id) {
  const plant = await api(`/api/plants/${id}`);
  const extraFields = Object.entries(plant.extra || {})
    .filter(([, value]) => value)
    .map(([label, value]) => [label, value]);
  const fields = [
    ["Scientific name", plant.scientific_name],
    ["Common name", plant.common_name],
    ["Synonyms", plant.synonyms],
    ["Family", plant.family],
    ["Genus", plant.genus],
    ["Growth habit", plant.growth_habit],
    ["Conservation status", plant.conservation_status],
    ["Duration", plant.duration],
    ["Native range", plant.native_status],
    ["USDA hardiness zone", plant.usda_hardiness_zone],
    ["Mature height (ft)", plant.height_mature_ft],
    ["Leaf persistence", plant.leaf_retention],
    ["Flower color", plant.flower_color],
    ["Bloom period", plant.bloom_period],
    ["Drought tolerance", plant.drought_tolerance],
    ["Shade tolerance", plant.shade_tolerance],
    ["Lifespan", plant.lifespan],
    ["USDA symbol", plant.usda_symbol],
    ...extraFields,
  ].filter(([, value]) => value);
  els.detailBody.innerHTML = `
    <h2>${esc(plant.common_name || plant.scientific_name)}</h2>
    <p><em>${esc(plant.scientific_name || "")}</em></p>
    <div class="detail-grid">
      ${fields
        .map(([label, value]) => `<div>${esc(label)}</div><div>${esc(value)}</div>`)
        .join("")}
    </div>
  `;
  els.detail.showModal();
}

function setFilter(key, value, checked) {
  const current = new Set(selectedValues(key));
  if (checked) current.add(value);
  else current.delete(value);
  if (current.size) state.filters[key] = [...current];
  else delete state.filters[key];
  state.offset = 0;
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.q = els.q.value.trim();
  state.offset = 0;
  els.suggest.hidden = true;
  refresh();
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
      return `<li><button type="button" data-q="${esc(label)}">${esc(label)} <em>${esc(item.scientific_name)}</em></button></li>`;
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
  refresh();
});

els.groups.addEventListener("change", (event) => {
  const input = event.target.closest("input[type=checkbox][data-filter]");
  if (!input) return;
  setFilter(input.dataset.filter, input.value, input.checked);
  refresh();
});

els.groups.addEventListener("input", (event) => {
  if (event.target.id !== "family-filter-q") return;
  state.familyQuery = event.target.value.trim();
  const group = (state.facetGroups || []).find((item) => item.key === "family");
  if (!group) return;
  const list = event.target.parentElement.querySelector(".check-list");
  const needle = state.familyQuery.toLowerCase();
  const options = (group.options || []).filter((option) =>
    option.label.toLowerCase().includes(needle)
  );
  list.innerHTML =
    options.map((option) => optionMarkup(group, option)).join("") ||
    `<p class="filter-empty">No families match that name.</p>`;
});

els.clear.addEventListener("click", () => {
  state.filters = {};
  state.familyQuery = "";
  state.offset = 0;
  refresh();
});

els.activeFilters.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-key]");
  if (!button) return;
  setFilter(button.dataset.key, button.dataset.value, false);
  refresh();
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
    await Promise.all([loadStats(), refresh()]);
  } catch (error) {
    els.uploadStatus.textContent = error.message;
  }
});

els.reload.addEventListener("click", async () => {
  els.uploadStatus.textContent = "Restoring combined catalog…";
  const result = await api("/api/reload-seed", { method: "POST" });
  els.uploadStatus.textContent = `Restored ${result.count.toLocaleString()} plants.`;
  state.offset = 0;
  await Promise.all([loadStats(), refresh()]);
});

els.closeDetail.addEventListener("click", () => els.detail.close());

loadStats();
refresh();
