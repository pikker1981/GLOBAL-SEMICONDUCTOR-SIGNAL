const state = {
  items: [],
  filteredItems: [],
  filters: {
    content: "all",
    region: "all",
    source: "all"
  },
  query: "",
  currentPage: 1,
  pageSize: 10
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

const paginationEls = createPaginationElements();

function createPaginationElements() {
  const wrapper = document.createElement("div");
  wrapper.id = "paginationBlock";
  wrapper.className = "hidden";
  wrapper.style.marginTop = "22px";

  const meta = document.createElement("div");
  meta.id = "paginationMeta";
  meta.className = "feed-meta";
  meta.style.justifyContent = "center";

  const controls = document.createElement("div");
  controls.id = "paginationControls";
  controls.className = "filters";
  controls.style.justifyContent = "center";
  controls.style.marginTop = "12px";

  wrapper.appendChild(meta);
  wrapper.appendChild(controls);

  els.feedList.insertAdjacentElement("afterend", wrapper);

  return { wrapper, meta, controls };
}

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
  if (Number.isNaN(date.getTime())) return value;
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
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(date);
}

function getSourceType(item) {
  if (item.source_type) return item.source_type;
  if (item.type === "paper") return "arXiv";
  if (item.source === "arXiv") return "arXiv";
  if (String(item.content_mode || "").toLowerCase().includes("k_invest")) return "K-INVEST";
  if (String(item.content_mode || "").toLowerCase().includes("rss")) return "RSS";
  if (item.type === "news") return "GDELT";
  return "UNKNOWN";
}

function getSourceBadgeClass(sourceType) {
  const normalized = String(sourceType || "").toLowerCase();
  if (normalized === "rss") return "source-rss";
  if (normalized === "gdelt") return "source-gdelt";
  if (normalized === "arxiv") return "source-arxiv";
  if (normalized === "k-invest") return "source-k-invest";
  return "source-unknown";
}

function normalizeText(item) {
  return [
    item.title,
    item.snippet,
    item.abstract,
    item.source,
    item.country,
    item.region,
    getSourceType(item),
    item.insight_type,
    Array.isArray(item.authors) ? item.authors.join(" ") : ""
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function resetPage() {
  state.currentPage = 1;
}

function getTotalPages() {
  return Math.max(1, Math.ceil(state.filteredItems.length / state.pageSize));
}

function clampCurrentPage() {
  const totalPages = getTotalPages();
  if (state.currentPage < 1) state.currentPage = 1;
  if (state.currentPage > totalPages) state.currentPage = totalPages;
}

function applyFilters() {
  const query = state.query.trim().toLowerCase();

  state.filteredItems = state.items.filter((item) => {
    const sourceType = getSourceType(item);

    const matchesContent =
      state.filters.content === "all" ||
      item.type === state.filters.content ||
      (state.filters.content === "k-invest" && sourceType === "K-INVEST");

    const matchesRegion =
      state.filters.region === "all" || item.region === state.filters.region;

    const matchesSource =
      state.filters.source === "all" || sourceType === state.filters.source;

    const matchesSearch = !query || normalizeText(item).includes(query);

    return matchesContent && matchesRegion && matchesSource && matchesSearch;
  });

  clampCurrentPage();
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

function getVisiblePageNumbers(currentPage, totalPages) {
  const maxButtons = 7;
  if (totalPages <= maxButtons) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set();
  pages.add(1);
  pages.add(totalPages);
  pages.add(currentPage);
  pages.add(currentPage - 1);
  pages.add(currentPage + 1);

  if (currentPage <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }

  if (currentPage >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  return Array.from(pages)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
}

function createPaginationButton(label, options = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = options.active ? "filter active" : "filter";
  button.textContent = label;

  if (options.disabled) {
    button.disabled = true;
    button.style.opacity = "0.4";
    button.style.cursor = "not-allowed";
  }

  if (typeof options.onClick === "function") {
    button.addEventListener("click", options.onClick);
  }

  return button;
}

function renderPagination() {
  const totalItems = state.filteredItems.length;
  const totalPages = getTotalPages();
  const currentPage = state.currentPage;

  if (totalItems <= state.pageSize) {
    paginationEls.wrapper.classList.add("hidden");
    paginationEls.meta.textContent = "";
    paginationEls.controls.innerHTML = "";
    return;
  }

  paginationEls.wrapper.classList.remove("hidden");

  const start = (currentPage - 1) * state.pageSize + 1;
  const end = Math.min(currentPage * state.pageSize, totalItems);

  paginationEls.meta.textContent = `PAGE ${currentPage} / ${totalPages} · SHOWING ${start}-${end} OF ${totalItems}`;
  paginationEls.controls.innerHTML = "";

  paginationEls.controls.appendChild(
    createPaginationButton("← PREV", {
      disabled: currentPage === 1,
      onClick: () => {
        if (state.currentPage > 1) {
          state.currentPage -= 1;
          renderFeed();
          scrollToFeedTop();
        }
      }
    })
  );

  const pageNumbers = getVisiblePageNumbers(currentPage, totalPages);

  pageNumbers.forEach((page, index) => {
    const previousPage = pageNumbers[index - 1];

    if (previousPage && page - previousPage > 1) {
      const ellipsis = document.createElement("span");
      ellipsis.textContent = "…";
      ellipsis.style.display = "inline-flex";
      ellipsis.style.alignItems = "center";
      ellipsis.style.padding = "0 4px";
      ellipsis.style.color = "var(--tertiary)";
      ellipsis.style.fontFamily = "var(--font-body)";
      paginationEls.controls.appendChild(ellipsis);
    }

    paginationEls.controls.appendChild(
      createPaginationButton(String(page), {
        active: page === currentPage,
        onClick: () => {
          state.currentPage = page;
          renderFeed();
          scrollToFeedTop();
        }
      })
    );
  });

  paginationEls.controls.appendChild(
    createPaginationButton("NEXT →", {
      disabled: currentPage === totalPages,
      onClick: () => {
        if (state.currentPage < totalPages) {
          state.currentPage += 1;
          renderFeed();
          scrollToFeedTop();
        }
      }
    })
  );
}

function scrollToFeedTop() {
  const feedSection = document.getElementById("feed");
  if (!feedSection) return;
  feedSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderActiveFilterText() {
  const content = String(state.filters.content).toUpperCase();
  const region = String(state.filters.region).toUpperCase();
  const source = String(state.filters.source).toUpperCase();
  els.activeFilter.textContent = `FILTER: TYPE=${content} / REGION=${region} / SOURCE=${source}`;
}

function startTitleTyping(titleEl) {
  if (!titleEl) return;
  const fullTitle = titleEl.dataset.fullTitle || titleEl.textContent || "";
  if (!fullTitle) return;

  if (titleEl._typingTimer) clearInterval(titleEl._typingTimer);

  const chars = Array.from(fullTitle);
  let index = 0;

  titleEl.textContent = "";
  titleEl.classList.add("is-typing");

  const speed = Math.max(8, Math.min(22, Math.floor(520 / Math.max(chars.length, 1))));

  titleEl._typingTimer = setInterval(() => {
    index += 1;
    titleEl.textContent = chars.slice(0, index).join("");

    if (index >= chars.length) {
      clearInterval(titleEl._typingTimer);
      titleEl._typingTimer = null;
      setTimeout(() => titleEl.classList.remove("is-typing"), 350);
    }
  }, speed);
}

function stopTitleTyping(titleEl) {
  if (!titleEl) return;
  if (titleEl._typingTimer) {
    clearInterval(titleEl._typingTimer);
    titleEl._typingTimer = null;
  }
  titleEl.textContent = titleEl.dataset.fullTitle || titleEl.textContent || "";
  titleEl.classList.remove("is-typing");
}

function bindCardTypingEffects() {
  document.querySelectorAll(".feed-card").forEach((card) => {
    const titleEl = card.querySelector(".typing-title");
    if (!titleEl) return;
    const originalTitle = titleEl.dataset.fullTitle || titleEl.textContent || "";
    titleEl.dataset.fullTitle = originalTitle;
    card.addEventListener("mouseenter", () => startTitleTyping(titleEl));
    card.addEventListener("mouseleave", () => stopTitleTyping(titleEl));
  });
}

function renderFeed() {
  const count = state.filteredItems.length;
  const totalPages = getTotalPages();

  clampCurrentPage();

  const startIndex = (state.currentPage - 1) * state.pageSize;
  const endIndex = startIndex + state.pageSize;
  const visibleItems = state.filteredItems.slice(startIndex, endIndex);

  els.resultCount.textContent =
    count === 0 ? "0 RESULTS" : `${count} RESULTS · PAGE ${state.currentPage}/${totalPages}`;

  renderActiveFilterText();
  els.emptyState.classList.toggle("hidden", count !== 0);

  els.feedList.innerHTML = visibleItems
    .map((item) => {
      const isPaper = item.type === "paper";
      const sourceType = getSourceType(item);
      const sourceClass = getSourceBadgeClass(sourceType);
      const rawTitle = item.title || "Untitled";
      const title = escapeHtml(rawTitle);
      const desc = escapeHtml(item.abstract || item.snippet || "No snippet available.");
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
            <span class="source-type-badge ${sourceClass}">${escapeHtml(sourceType)}</span>
            <span class="card-region">${region}</span>
            <span class="card-region">${compactDate(item.published_at)}</span>
          </div>

          <div class="card-body">
            <h3 class="card-title">
              <a
                class="typing-title"
                data-full-title="${title}"
                href="${url}"
                target="_blank"
                rel="noopener"
              >${title}</a>
            </h3>

            <p class="card-desc">${desc}</p>

            <div class="card-meta">
              <span>ORIGIN: ${escapeHtml(sourceType)}</span>
              <span>SOURCE: ${metaSource}</span>
              ${country ? `<span>COUNTRY: ${country}</span>` : ""}
              <span>PUBLISHED: ${formatDate(item.published_at)}</span>
              ${item.insight_type ? `<span>INSIGHT: ${escapeHtml(item.insight_type)}</span>` : ""}
            </div>
          </div>

          <div class="card-actions">
            <a class="open-link" href="${url}" target="_blank" rel="noopener">
              OPEN ORIGINAL
            </a>

            ${pdfUrl ? `<a class="pdf-link" href="${pdfUrl}" target="_blank" rel="noopener">PDF</a>` : ""}
          </div>
        </article>
      `;
    })
    .join("");

  bindCardTypingEffects();
  renderPagination();
}

async function loadFeed() {
  els.feedList.innerHTML = `
    <div class="empty-state">
      <strong>LOADING SIGNAL</strong>
      <p>latest.json 데이터를 불러오는 중입니다.</p>
    </div>
  `;

  paginationEls.wrapper.classList.add("hidden");

  try {
    const response = await fetch(`./data/latest.json?ts=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.items = Array.isArray(payload.items) ? payload.items : [];
    state.items.sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
    resetPage();
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
    paginationEls.wrapper.classList.add("hidden");
  }
}

document.querySelectorAll("[data-filter-group]").forEach((button) => {
  button.addEventListener("click", () => {
    const group = button.dataset.filterGroup;
    const value = button.dataset.filterValue;

    document
      .querySelectorAll(`[data-filter-group="${group}"]`)
      .forEach((item) => item.classList.remove("active"));

    button.classList.add("active");
    state.filters[group] = value;
    resetPage();
    applyFilters();
  });
});

els.searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  resetPage();
  applyFilters();
});

els.reloadButton.addEventListener("click", loadFeed);

/* ================================
   GitHub Actions update integration
   ================================ */
const GITHUB_CONFIG_KEY = "gss_gh_config";

function loadGithubConfig() {
  try {
    return JSON.parse(localStorage.getItem(GITHUB_CONFIG_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveGithubConfig(config) {
  localStorage.setItem(GITHUB_CONFIG_KEY, JSON.stringify(config));
}

const modalEls = {
  overlay: document.getElementById("tokenModal"),
  ownerInput: document.getElementById("ghOwnerInput"),
  repoInput: document.getElementById("ghRepoInput"),
  tokenInput: document.getElementById("ghTokenInput"),
  saveBtn: document.getElementById("tokenModalSave"),
  cancelBtn: document.getElementById("tokenModalCancel"),
  closeBtn: document.getElementById("tokenModalClose")
};

function openTokenModal() {
  const config = loadGithubConfig();
  modalEls.ownerInput.value = config.owner || "";
  modalEls.repoInput.value = config.repo || "";
  modalEls.tokenInput.value = config.token || "";
  modalEls.overlay.classList.remove("hidden");
  modalEls.ownerInput.focus();
}

function closeTokenModal() {
  modalEls.overlay.classList.add("hidden");
}

modalEls.closeBtn.addEventListener("click", closeTokenModal);
modalEls.cancelBtn.addEventListener("click", closeTokenModal);
modalEls.overlay.addEventListener("click", (event) => {
  if (event.target === modalEls.overlay) closeTokenModal();
});

modalEls.saveBtn.addEventListener("click", () => {
  const owner = modalEls.ownerInput.value.trim();
  const repo = modalEls.repoInput.value.trim();
  const token = modalEls.tokenInput.value.trim();
  if (!owner || !repo || !token) {
    alert("Owner, Repo, Token을 모두 입력해주세요.");
    return;
  }
  saveGithubConfig({ owner, repo, token });
  closeTokenModal();
  startUpdate();
});

document.getElementById("settingsButton").addEventListener("click", openTokenModal);

const updateButton = document.getElementById("updateButton");

function setUpdateState(stateName, message) {
  updateButton.disabled = stateName === "loading";
  updateButton.className = `update-btn${stateName !== "idle" ? ` update-btn--${stateName}` : ""}`;
  updateButton.textContent = message;
}

async function triggerWorkflow(owner, repo, token) {
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/update.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ ref: "main" })
    }
  );
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub API ${res.status}: ${body}`);
  }
}

async function pollForCompletion(owner, repo, token, triggeredAt) {
  const maxWaitMs = 5 * 60 * 1000;
  const pollIntervalMs = 10 * 1000;
  const deadline = Date.now() + maxWaitMs;

  await new Promise((resolve) => setTimeout(resolve, 4000));

  while (Date.now() < deadline) {
    try {
      const res = await fetch(
        `https://api.github.com/repos/${owner}/${repo}/actions/workflows/update.yml/runs?per_page=5`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json"
          }
        }
      );

      if (res.ok) {
        const data = await res.json();
        const recentRuns = (data.workflow_runs || []).filter(
          (run) => new Date(run.created_at).getTime() >= triggeredAt - 8000
        );

        if (recentRuns.length > 0) {
          const latest = recentRuns[0];
          const elapsed = Math.round((Date.now() - triggeredAt) / 1000);
          setUpdateState("loading", `◉ 실행 중... (${elapsed}s)`);

          if (latest.status === "completed") {
            if (latest.conclusion === "success") return;
            throw new Error(`워크플로우 종료: ${latest.conclusion}`);
          }
        }
      }
    } catch (pollError) {
      if (pollError.message.startsWith("워크플로우")) throw pollError;
    }

    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }

  throw new Error("타임아웃: 5분 내에 완료되지 않았습니다.");
}

async function startUpdate() {
  const config = loadGithubConfig();
  if (!config.owner || !config.repo || !config.token) {
    openTokenModal();
    return;
  }

  setUpdateState("loading", "⟳ 트리거 중...");
  const triggeredAt = Date.now();

  try {
    await triggerWorkflow(config.owner, config.repo, config.token);
    setUpdateState("loading", "◉ 워크플로우 실행 중...");
    await pollForCompletion(config.owner, config.repo, config.token, triggeredAt);
    setUpdateState("success", "✓ 완료 — 데이터 로드 중");
    await loadFeed();
    setUpdateState("success", "✓ 업데이트 완료");
    setTimeout(() => setUpdateState("idle", "지금 업데이트"), 4000);
  } catch (error) {
    console.error("[Update]", error);
    setUpdateState("error", `✕ ${error.message}`);
    setTimeout(() => setUpdateState("idle", "지금 업데이트"), 5000);
  }
}

updateButton.addEventListener("click", startUpdate);

loadFeed();
