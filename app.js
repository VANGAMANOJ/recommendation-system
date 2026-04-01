/**
 * Best Choice Engine — Frontend JS
 * Handles geolocation, category/filter selection, API calls, and card rendering.
 */

/* ── STATE ── */
const state = {
  lat: null,
  lng: null,
  category: "restaurant",
  filter: "best",
  apiKey: "",
  lastResults: null,
};

/* ── DOM REFS ── */
const apiKeyInput     = document.getElementById("apiKey");
const toggleKeyBtn    = document.getElementById("toggleKey");
const locationText    = document.getElementById("locationText");
const searchBtn       = document.getElementById("searchBtn");
const resultsSection  = document.getElementById("resultsSection");
const catPills        = document.querySelectorAll(".cat-pill");
const filterBtns      = document.querySelectorAll(".filter-btn");

/* ── INIT ── */
window.addEventListener("DOMContentLoaded", () => {
  restoreState();
  detectLocation();
});

/* ── RESTORE LAST SEARCH ── */
function restoreState() {
  const saved = localStorage.getItem("bce_state");
  if (!saved) return;
  try {
    const s = JSON.parse(saved);
    if (s.apiKey)   { apiKeyInput.value = s.apiKey; state.apiKey = s.apiKey; }
    if (s.category) { state.category = s.category; setActiveCategory(s.category); }
    if (s.filter)   { state.filter   = s.filter;   setActiveFilter(s.filter); }
  } catch {}
}

function persistState() {
  localStorage.setItem("bce_state", JSON.stringify({
    apiKey:   state.apiKey,
    category: state.category,
    filter:   state.filter,
  }));
}

/* ── API KEY ── */
apiKeyInput.addEventListener("input", () => {
  state.apiKey = apiKeyInput.value.trim();
  updateSearchBtn();
});

toggleKeyBtn.addEventListener("click", () => {
  const isPass = apiKeyInput.type === "password";
  apiKeyInput.type = isPass ? "text" : "password";
  toggleKeyBtn.textContent = isPass ? "🙈" : "👁";
});

/* ── GEOLOCATION ── */
function detectLocation() {
  if (!navigator.geolocation) {
    locationText.textContent = "Geolocation not supported";
    return;
  }
  locationText.textContent = "Detecting…";
  navigator.geolocation.getCurrentPosition(
    pos => {
      state.lat = pos.coords.latitude;
      state.lng = pos.coords.longitude;
      locationText.textContent =
        `${state.lat.toFixed(4)}°N, ${state.lng.toFixed(4)}°E`;
      updateSearchBtn();
    },
    err => {
      locationText.textContent = "Location denied — enter manually";
      console.warn("Geolocation error:", err.message);
    },
    { timeout: 8000 }
  );
}

/* ── CATEGORY SELECTION ── */
catPills.forEach(pill => {
  pill.addEventListener("click", () => {
    state.category = pill.dataset.cat;
    setActiveCategory(state.category);
  });
});

function setActiveCategory(cat) {
  catPills.forEach(p => p.classList.toggle("active", p.dataset.cat === cat));
}

/* ── FILTER SELECTION ── */
filterBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    state.filter = btn.dataset.filter;
    setActiveFilter(state.filter);
    // Re-run search with new filter if we have results
    if (state.lat && state.apiKey) doSearch();
  });
});

function setActiveFilter(f) {
  filterBtns.forEach(b => b.classList.toggle("active", b.dataset.filter === f));
}

/* ── SEARCH BUTTON ── */
function updateSearchBtn() {
  searchBtn.disabled = !(state.lat && state.apiKey);
}

searchBtn.addEventListener("click", doSearch);

/* ── MAIN SEARCH FLOW ── */
async function doSearch() {
  if (!state.lat || !state.apiKey) return;
  persistState();
  showLoading();

  try {
    const resp = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key:  state.apiKey,
        lat:      state.lat,
        lng:      state.lng,
        category: state.category,
        filter:   state.filter,
      }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      showError(data.error || "Something went wrong.");
      return;
    }

    if (!data.results || data.results.length === 0) {
      showEmpty(data.message || "No results found nearby.");
      return;
    }

    renderResults(data.results, data.total_found);

  } catch (err) {
    showError("Network error. Check your connection and try again.");
    console.error(err);
  }
}

/* ── RENDER STATES ── */
function showLoading() {
  resultsSection.innerHTML = `
    <div class="loading-state">
      <div class="loading-ring"></div>
      <p class="loading-text">Finding the best nearby ${state.category}s…</p>
    </div>`;
}

function showError(msg) {
  resultsSection.innerHTML = `
    <div class="message-box">
      <div class="msg-icon">⚠️</div>
      <p>${escHtml(msg)}</p>
    </div>`;
}

function showEmpty(msg) {
  resultsSection.innerHTML = `
    <div class="message-box">
      <div class="msg-icon">🔍</div>
      <p>${escHtml(msg)}</p>
    </div>`;
}

/* ── RENDER RESULTS ── */
function renderResults(results, totalFound) {
  state.lastResults = results;
  const label = `Top ${results.length} of ${totalFound} nearby`;

  let html = `
    <div class="results-header">
      <span class="results-title">Best ${capFirst(state.category)}s Near You</span>
      <span class="results-count">${label}</span>
    </div>`;

  results.forEach((place, idx) => {
    html += buildCard(place, idx + 1);
  });

  resultsSection.innerHTML = html;
}

function buildCard(p, rank) {
  const rankClass = rank === 1 ? "rank-1" : "";
  const scoreDisplay = (p.score * 10).toFixed(1);

  // Rating stars
  const stars = "★".repeat(Math.round(p.rating || 0)) +
                "☆".repeat(5 - Math.round(p.rating || 0));

  // Open status badge
  let openBadge = "";
  if (p.open_now === true)  openBadge = `<span class="open-badge open">Open now</span>`;
  if (p.open_now === false) openBadge = `<span class="open-badge closed">Closed</span>`;

  // Price dots
  const priceDots = buildPriceDots(p.price_level);

  // Review count formatted
  const reviews = p.reviews >= 1000
    ? `${(p.reviews/1000).toFixed(1)}k reviews`
    : `${p.reviews} reviews`;

  return `
  <article class="place-card ${rankClass}" aria-label="${escHtml(p.name)}">
    <div class="card-left">
      <span class="place-tag">${escHtml(p.tag)}</span>
      <h2 class="place-name">${escHtml(p.name)}</h2>
      <div class="place-meta">
        <span class="meta-item">
          <span class="rating-star">★</span>
          <span class="rating-value">${p.rating || "N/A"}</span>
          <span style="color:var(--text-dim)">(${reviews})</span>
        </span>
        <span class="meta-item">
          <span class="icon">📍</span> ${escHtml(p.distance)}
        </span>
        ${priceDots ? `<span class="meta-item">${priceDots}</span>` : ""}
        ${openBadge}
      </div>
      <p class="place-address">${escHtml(p.address)}</p>
    </div>
    <div class="card-right">
      <div class="score-pill">
        <div class="score-num">${scoreDisplay}</div>
        <div class="score-label">Score</div>
      </div>
      <a class="btn-maps" href="${escHtml(p.maps_url)}" target="_blank" rel="noopener">
        🗺 Open in Maps
      </a>
    </div>
  </article>`;
}

function buildPriceDots(level) {
  if (level === null || level === undefined) return "";
  let html = `<span style="font-size:11px;color:var(--text-dim);margin-right:2px">₹</span>
              <span class="price-dots">`;
  for (let i = 1; i <= 4; i++) {
    html += `<span class="price-dot ${i <= level ? "active" : ""}"></span>`;
  }
  return html + "</span>";
}

/* ── UTILS ── */
function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function capFirst(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
