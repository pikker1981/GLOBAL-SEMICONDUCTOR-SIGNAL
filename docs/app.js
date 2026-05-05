const state = {
  items: [],
  filteredItems: [],
  filter: { type: "all", value: "all" },
  query: ""
};

const els = {
  totalCount: document.getElementById("totalCount"),
  newsCount: document.getElementById("newsCount"),
  paperCount: document.getElementById("paperCount"),
  lastUpdated: document.getElementById("lastUpdated"),
  resultCount: document.getElementById("resultCount"),
  activeFilter: document.getElementById("activeFilter"),
  feedList: document.getElementById("feedList"),
  emptyState: document.getElementById("emptyState"),
  searchInput: document.getElementById("searchInput"),
  reloadButton: document.getElementById("reloadButton")
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "Unknown";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function compactDate(value) {
  if (!value) return "UNKNOWN";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(date);
}

function normalizeText(item) {
  return [
    item.title,
    item.snippet,
    item.abstract,
    item.source,
    item.country,
    item.region,
    Array.isArray(item.authors) ? item.authors.join(" ") : ""
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function applyFilters() {
  const query = state.query.trim().toLowerCase();

  state.filteredItems = state.items.filter((item) => {
    const matchesFilter =
      state.filter.type === "all" ||
      (state.filter.type === "type" && item.type === state.filter.value) ||
      (state.filter.type === "region" && item.region === state.filter.value);

    const matchesSearch = !query || normalizeText(item).includes(query);

    return matchesFilter && matchesSearch;
  });

  renderFeed();
}

function renderStats(meta = {}) {
  const total = state.items.length;
  const news = state.items.filter((item) => item.type === "news").length;
  const papers = state.items.filter((item) => item.type === "paper").length;

  els.totalCount.textContent = total;
  els.newsCount.textContent = news;
  els.paperCount.textContent = papers;
  els.lastUpdated.textContent = formatDate(meta.generated_at);
}

function renderFeed() {
  const count = state.filteredItems.length;

  els.resultCount.textContent = `${count} RESULTS`;

  els.activeFilter.textContent =
    state.filter.type === "all"
      ? "FILTER: ALL"
      : `FILTER: ${state.filter.type.toUpperCase()} / ${String(
          state.filter.value
        ).toUpperCase()}`;

  els.emptyState.classList.toggle("hidden", count !== 0);

  els.feedList.innerHTML = state.filteredItems
    .map((item) => {
      const isPaper = item.type === "paper";
      const title = escapeHtml(item.title || "Untitled");
      const desc = escapeHtml(
        item.abstract || item.snippet || "No snippet available."
      );
      const source = escapeHtml(item.source || "Unknown source");
      const region = escapeHtml(item.region || "Global");
      const country = escapeHtml(item.country || "");
      const authors = Array.isArray(item.authors) ? item.authors.join(", ") : "";
      const metaSource = isPaper && authors ? escapeHtml(authors) : source;
      const url = escapeHtml(item.url || "#");
      const pdfUrl = escapeHtml(item.pdf_url || "");

      return `
        <article class="feed-card">
          <div class="card-side">
            <span class="card-kicker">${isPaper ? "PAPER" : "NEWS"}</span>
            <span class="card-region">${region}</span>
            <span class="card-region">${compactDate(item.published_at)}</span>
          </div>

          <div class="card-body">
            <h3 class="card-title">
              <a href="${url}" target="_blank" rel="noopener">${title}</a>
            </h3>

            <p class="card-desc">${desc}</p>

            <div class="card-meta">
              <span>SOURCE: ${metaSource}</span>
              ${country ? `<span>COUNTRY: ${country}</span>` : ""}
              <span>PUBLISHED: ${formatDate(item.published_at)}</span>
            </div>
          </div>

          <div class="card-actions">
            <a class="open-link" href="${url}" target="_blank" rel="noopener">
              OPEN ORIGINAL
            </a>

            ${
              pdfUrl
                ? `<a class="pdf-link" href="${pdfUrl}" target="_blank" rel="noopener">PDF</a>`
                : ""
            }
          </div>
        </article>
      `;
    })
    .join("");
}

async function loadFeed() {
  els.feedList.innerHTML = `
    <div class="empty-state">
      <strong>LOADING SIGNAL</strong>
      <p>latest.json 데이터를 불러오는 중입니다.</p>
    </div>
  `;

  try {
    const response = await fetch(`./data/latest.json?ts=${Date.now()}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();

    state.items = Array.isArray(payload.items) ? payload.items : [];

    state.items.sort(
      (a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0)
    );

    renderStats(payload.meta || {});
    applyFilters();
  } catch (error) {
    console.error(error);

    els.feedList.innerHTML = `
      <div class="empty-state">
        <strong>LOAD FAILED</strong>
        <p>docs/data/latest.json 파일을 불러오지 못했습니다.</p>
      </div>
    `;
  }
}

document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".filter")
      .forEach((item) => item.classList.remove("active"));

    button.classList.add("active");

    state.filter = {
      type: button.dataset.filterType,
      value: button.dataset.filterValue
    };

    applyFilters();
  });
});

els.searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  applyFilters();
});

els.reloadButton.addEventListener("click", loadFeed);

loadFeed();
