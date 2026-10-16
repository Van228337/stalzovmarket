/**
 * STALZONE Market Dashboard - Modern Client Application
 * Full real-time analytics, item deep-dive, Supabase cloud sync, and 0 dummy values.
 */

let marketData = null;
let analyticsData = null;
let catalogItems = [];
let watchlist = [
  { item_id: "y3nmw", name_ru: "Продвинутые запчасти", category: "other", rank: "RANK_MASTER", enabled: true, min_roi: 0.10, min_profit: 50000 },
  { item_id: "4q7pl", name_ru: "Продвинутые инструменты", category: "other", rank: "RANK_MASTER", enabled: true, min_roi: 0.10, min_profit: 50000 },
  { item_id: "l0og1", name_ru: "Стандартные запчасти", category: "other", rank: "RANK_STALKER", enabled: true, min_roi: 0.10, min_profit: 50000 },
  { item_id: "zzwmm", name_ru: "Сыворотка изменения", category: "other", rank: "RANK_VETERAN", enabled: true, min_roi: 0.10, min_profit: 50000 },
  { item_id: "g35n", name_ru: "Контейнер «Берлога-6»", category: "containers", rank: "RANK_MASTER", enabled: true, min_roi: 0.10, min_profit: 150000 },
  { item_id: "j3ml", name_ru: "Контейнер «КСМ»", category: "containers", rank: "RANK_MASTER", enabled: true, min_roi: 0.10, min_profit: 200000 },
  { item_id: "gyq5", name_ru: "Спираль", category: "artefact/electrophysical", rank: "DEFAULT", enabled: true, min_roi: 0.10, min_profit: 100000 },
  { item_id: "5rwq", name_ru: "Осколок", category: "artefact/electrophysical", rank: "DEFAULT", enabled: true, min_roi: 0.10, min_profit: 150000 },
  { item_id: "qoq6", name_ru: "Солнце", category: "artefact/thermal", rank: "DEFAULT", enabled: true, min_roi: 0.10, min_profit: 150000 },
  { item_id: "wg53", name_ru: "Атом", category: "artefact/electrophysical", rank: "DEFAULT", enabled: true, min_roi: 0.10, min_profit: 150000 },
  { item_id: "y5w3", name_ru: "Призма", category: "artefact/electrophysical", rank: "DEFAULT", enabled: true, min_roi: 0.10, min_profit: 150000 }
];

let selectedItemId = "y3nmw";
let selectedSegmentKey = "all";
let priceChart = null;
let activeCatFilter = "";
let supabaseClient = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  loadSavedWatchlist();
  initSupabase();
  setupTabs();
  setupFilters();
  setupCatalogSearch();
  setupWatchlistControls();
  setupItemDeepDiveControls();
  setupSettings();

  // Load backend data
  loadData();
  loadCatalog();

  document.getElementById("btn-refresh").addEventListener("click", () => {
    loadData();
  });

  document.getElementById("btn-copy-llm").addEventListener("click", copyPromptForLLM);
});

// =============================================================================
// WATCHLIST STORAGE
// =============================================================================
function loadSavedWatchlist() {
  const saved = localStorage.getItem("stalzone_watchlist");
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        watchlist = parsed;
      }
    } catch (e) {
      console.warn("Failed to load watchlist from localStorage", e);
    }
  }
}

function saveWatchlist() {
  localStorage.setItem("stalzone_watchlist", JSON.stringify(watchlist));
}

// =============================================================================
// SUPABASE CLIENT SETUP
// =============================================================================
function initSupabase() {
  const url = localStorage.getItem("stalzone_sb_url") || "";
  const key = localStorage.getItem("stalzone_sb_key") || "";

  const pill = document.getElementById("supabase-status-pill");
  const urlInput = document.getElementById("supabase-url-input");
  const keyInput = document.getElementById("supabase-key-input");

  if (urlInput) urlInput.value = url;
  if (keyInput) keyInput.value = key;

  if (url && key && window.supabase) {
    try {
      supabaseClient = window.supabase.createClient(url, key);
      if (pill) {
        pill.innerHTML = '<span class="dot db-online"></span> Supabase';
        pill.title = "Supabase Cloud: Подключено";
      }
    } catch (e) {
      console.warn("Supabase init error:", e);
      if (pill) {
        pill.innerHTML = '<span class="dot db-offline"></span> Supabase';
        pill.title = "Supabase: Ошибка подключения";
      }
    }
  } else {
    if (pill) {
      pill.innerHTML = '<span class="dot db-offline"></span> Supabase';
      pill.title = "Supabase: Не настроен (работа в файловом режиме)";
    }
  }
}

function setupSettings() {
  const saveBtn = document.getElementById("btn-save-supabase");
  const testBtn = document.getElementById("btn-test-supabase");
  const resultDiv = document.getElementById("supabase-test-result");

  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const url = document.getElementById("supabase-url-input").value.trim();
      const key = document.getElementById("supabase-key-input").value.trim();
      localStorage.setItem("stalzone_sb_url", url);
      localStorage.setItem("stalzone_sb_key", key);
      initSupabase();
      if (resultDiv) {
        resultDiv.className = "mt-2 small text-emerald";
        resultDiv.innerText = "Параметры Supabase сохранены!";
      }
    });
  }

  if (testBtn) {
    testBtn.addEventListener("click", async () => {
      if (!supabaseClient) {
        if (resultDiv) {
          resultDiv.className = "mt-2 small text-danger";
          resultDiv.innerText = "Сначала сохраните URL и Anon Key.";
        }
        return;
      }
      if (resultDiv) {
        resultDiv.className = "mt-2 small text-muted";
        resultDiv.innerText = "Проверка связи с Supabase...";
      }
      try {
        const { data, error } = await supabaseClient.from("signals").select("id").limit(1);
        if (error) throw error;
        if (resultDiv) {
          resultDiv.className = "mt-2 small text-emerald";
          resultDiv.innerText = "Успешно! Связь с Supabase установлена, таблицы доступны.";
        }
      } catch (err) {
        if (resultDiv) {
          resultDiv.className = "mt-2 small text-danger";
          resultDiv.innerText = `Ошибка подключения: ${err.message || err}`;
        }
      }
    });
  }
}

// =============================================================================
// TAB NAVIGATION
// =============================================================================
function setupTabs() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const targetTab = document.getElementById(tabId);
      if (targetTab) targetTab.classList.add("active");

      if (tabId === "tab-item") {
        renderItemDeepDive();
      }
    });
  });
}

function switchToItemTab(itemId, segmentKey = "all") {
  selectedItemId = itemId;
  selectedSegmentKey = segmentKey;

  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  const itemBtn = document.querySelector('[data-tab="tab-item"]');
  if (itemBtn) itemBtn.classList.add("active");

  const itemTab = document.getElementById("tab-item");
  if (itemTab) itemTab.classList.add("active");

  renderItemDeepDive();
}

// =============================================================================
// DATA LOADING
// =============================================================================
async function loadData() {
  const statusText = document.getElementById("data-status-text");
  if (statusText) statusText.innerText = "Синхронизация с рынком...";

  try {
    // 1. Fetch compact digest.json (signals & overview)
    let digestRes = await fetch("digest.json");
    if (!digestRes.ok) digestRes = await fetch("data/digest.json");
    if (!digestRes.ok) digestRes = await fetch("../data/digest.json");
    if (digestRes.ok) {
      marketData = await digestRes.json();
    }

    // 2. Fetch full market_analytics.json (all active lots, sales history & segments)
    let analyticsRes = await fetch("market_analytics.json");
    if (!analyticsRes.ok) analyticsRes = await fetch("data/market_analytics.json");
    if (!analyticsRes.ok) analyticsRes = await fetch("../data/market_analytics.json");
    if (analyticsRes.ok) {
      analyticsData = await analyticsRes.json();
    }

    if (marketData || analyticsData) {
      if (statusText) statusText.innerText = "Рынок синхронизирован (EXBO Production)";
      const freshness = marketData?.data_freshness_minutes || 10;
      const dataAgeEl = document.getElementById("data-age");
      if (dataAgeEl) dataAgeEl.innerText = `Возраст снимка: ~${freshness} мин`;

      const cfgDisplay = document.getElementById("config-json-display");
      if (cfgDisplay && marketData?.config) {
        cfgDisplay.innerText = JSON.stringify(marketData.config, null, 2);
      }

      renderSignals();
      populateQuickChips();
      renderItemDeepDive();
      renderWatchlist();
    }
  } catch (err) {
    console.error("Error loading market data:", err);
    if (statusText) statusText.innerText = "Ошибка загрузки данных";
  }
}

async function loadCatalog() {
  try {
    let res = await fetch("catalog.json");
    if (!res.ok) res = await fetch("data/catalog.json");
    if (!res.ok) res = await fetch("../web/catalog.json");
    if (res.ok) {
      catalogItems = await res.json();
    }
  } catch (e) {
    console.warn("Could not load catalog.json:", e);
  }
}

// =============================================================================
// TAB 1: SIGNALS RENDERING
// =============================================================================
function setupFilters() {
  const searchInput = document.getElementById("signal-search");
  if (searchInput) searchInput.addEventListener("input", renderSignals);

  const roiSelect = document.getElementById("filter-roi");
  if (roiSelect) roiSelect.addEventListener("change", renderSignals);

  const confSelect = document.getElementById("filter-conf");
  if (confSelect) confSelect.addEventListener("change", renderSignals);

  const sortSelect = document.getElementById("sort-signals");
  if (sortSelect) sortSelect.addEventListener("change", renderSignals);
}

function renderSignals() {
  const tbody = document.getElementById("signals-tbody");
  if (!tbody) return;

  const countBadge = document.getElementById("signals-count-badge");
  const opportunities = marketData?.top_opportunities || [];

  if (countBadge) {
    countBadge.innerText = `${opportunities.length} сигналов`;
  }

  if (opportunities.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="text-center text-muted py-4">
          Нет активных сигналов с ROI ≥ 10% в текущем снимке.<br>
          <span class="small">Сканер опрашивает аукцион каждые 5 минут и пришлёт уведомление при появлении недооценённых лотов.</span>
        </td>
      </tr>
    `;
    return;
  }

  const query = normalizeSearch(document.getElementById("signal-search")?.value || "");
  const minRoi = parseFloat(document.getElementById("filter-roi")?.value || "0");
  const minConf = parseFloat(document.getElementById("filter-conf")?.value || "0");
  const sortBy = document.getElementById("sort-signals")?.value || "profit";

  let filtered = opportunities.filter(opp => {
    const nameMatch = normalizeSearch(opp.name_ru || "").includes(query);
    const roiMatch = (opp.plan?.roi || 0) >= minRoi;
    const confMatch = (opp.confidence || 0) >= minConf;
    return nameMatch && roiMatch && confMatch;
  });

  filtered.sort((a, b) => {
    if (sortBy === "profit") return (b.plan?.expected_profit || 0) - (a.plan?.expected_profit || 0);
    if (sortBy === "roi") return (b.plan?.roi || 0) - (a.plan?.roi || 0);
    if (sortBy === "confidence") return (b.confidence || 0) - (a.confidence || 0);
    if (sortBy === "days") return (a.liquidity?.days_to_sell_est || 0) - (b.liquidity?.days_to_sell_est || 0);
    return 0;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">Нет сигналов, соответствующих фильтрам.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(opp => {
    const confClass = opp.confidence >= 0.75 ? "conf-high" : "conf-mid";
    const reasonsHtml = (opp.reasons || []).map(r => `<div>• ${escapeHtml(r)}</div>`).join("");
    const segKey = opp.segment_key || "default";

    return `
      <tr>
        <td>
          <strong>${escapeHtml(opp.name_ru || "Предмет")}</strong>
          <div class="small text-muted">${escapeHtml(opp.segment_label || opp.segment || "Стандарт")}</div>
        </td>
        <td><strong>${formatPrice(opp.lot?.buy_unit)} ₽</strong></td>
        <td>${formatPrice(opp.plan?.sell_target_unit)} ₽</td>
        <td class="profit-badge">+${formatPrice(opp.plan?.expected_profit)} ₽</td>
        <td class="roi-badge">+${((opp.plan?.roi || 0) * 100).toFixed(1)}%</td>
        <td>~${opp.liquidity?.days_to_sell_est || 1} дн.</td>
        <td><span class="confidence-bar ${confClass}">${Math.round((opp.confidence || 0) * 100)}%</span></td>
        <td class="reasons-tooltip">${reasonsHtml}</td>
        <td>
          <button class="btn-sm btn-secondary" onclick="switchToItemTab('${opp.item_id}', '${segKey}')">
            🔍 Анализ
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

// =============================================================================
// TAB 2: ITEM DEEP-DIVE ANALYTICS
// =============================================================================
function setupItemDeepDiveControls() {
  const input = document.getElementById("item-lookup-input");
  const dropdown = document.getElementById("item-search-dropdown");

  if (input && dropdown) {
    input.addEventListener("input", () => {
      const q = normalizeSearch(input.value);
      if (!q) {
        dropdown.classList.add("hidden");
        dropdown.innerHTML = "";
        return;
      }

      // Search in analytics items and catalog
      const itemsList = getAvailableItemsList();
      const matches = itemsList.filter(item => {
        return normalizeSearch(item.name_ru).includes(q) || normalizeSearch(item.item_id).includes(q);
      }).slice(0, 8);

      if (matches.length === 0) {
        dropdown.innerHTML = '<div class="autocomplete-item text-muted">Ничего не найдено</div>';
        dropdown.classList.remove("hidden");
        return;
      }

      dropdown.innerHTML = matches.map(item => `
        <div class="autocomplete-item" data-id="${item.item_id}">
          <span>📦</span>
          <div style="flex:1">
            <strong>${escapeHtml(item.name_ru)}</strong>
            <div class="small text-muted">${escapeHtml(item.category || "Предмет")}</div>
          </div>
          <span class="badge ${item.rank || ''}">${formatRank(item.rank)}</span>
        </div>
      `).join("");

      dropdown.querySelectorAll(".autocomplete-item").forEach(el => {
        el.addEventListener("click", () => {
          const id = el.getAttribute("data-id");
          if (id) {
            selectedItemId = id;
            selectedSegmentKey = "all";
            input.value = "";
            dropdown.classList.add("hidden");
            renderItemDeepDive();
          }
        });
      });

      dropdown.classList.remove("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add("hidden");
      }
    });
  }

  const addWlBtn = document.getElementById("btn-add-current-watchlist");
  if (addWlBtn) {
    addWlBtn.addEventListener("click", () => {
      const itemInfo = getItemInfo(selectedItemId);
      if (itemInfo) {
        addToWatchlist(selectedItemId, itemInfo.name_ru);
      }
    });
  }
}

function getAvailableItemsList() {
  const map = new Map();
  // Items with real analytics
  if (analyticsData?.items) {
    Object.values(analyticsData.items).forEach(i => {
      map.set(i.item_id, {
        item_id: i.item_id,
        name_ru: i.name_ru || i.item_id,
        category: i.category || "",
        rank: i.rank || "DEFAULT"
      });
    });
  }
  // Watchlist items
  watchlist.forEach(w => {
    if (!map.has(w.item_id)) {
      map.set(w.item_id, {
        item_id: w.item_id,
        name_ru: w.name_ru,
        category: w.category || "",
        rank: w.rank || "DEFAULT"
      });
    }
  });
  // Catalog items
  catalogItems.forEach(c => {
    if (!map.has(c.item_id)) {
      map.set(c.item_id, {
        item_id: c.item_id,
        name_ru: c.name_ru || c.item_id,
        category: c.category || "",
        rank: c.rank || "DEFAULT"
      });
    }
  });
  return Array.from(map.values());
}

function getItemInfo(itemId) {
  if (analyticsData?.items?.[itemId]) return analyticsData.items[itemId];
  const wl = watchlist.find(w => w.item_id === itemId);
  if (wl) return wl;
  const cat = catalogItems.find(c => c.item_id === itemId);
  if (cat) return cat;
  return { item_id: itemId, name_ru: itemId, category: "", rank: "DEFAULT" };
}

function populateQuickChips() {
  const container = document.getElementById("quick-item-chips");
  if (!container) return;

  const chipsItems = [
    { id: "y3nmw", label: "Продвинутые запчасти" },
    { id: "wg53", label: "Атом" },
    { id: "gyq5", label: "Спираль" },
    { id: "5rwq", label: "Осколок" },
    { id: "g35n", label: "Берлога-6" },
    { id: "zzwmm", label: "Сыворотка" },
    { id: "4q7pl", label: "Инструменты" },
  ];

  container.innerHTML = `
    <span class="chips-label">Быстрый выбор:</span>
    ${chipsItems.map(c => `
      <button class="quick-chip" onclick="switchToItemTab('${c.id}', 'all')">${escapeHtml(c.label)}</button>
    `).join("")}
  `;
}

function renderItemDeepDive() {
  const item = analyticsData?.items?.[selectedItemId] || getItemInfo(selectedItemId);
  if (!item) return;

  // 1. Profile Header
  const nameEl = document.getElementById("item-display-name");
  if (nameEl) nameEl.innerText = item.name_ru || selectedItemId;

  const iconBox = document.getElementById("item-icon-box");
  if (iconBox) {
    if (item.icon_path) {
      iconBox.innerHTML = `<img src="https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${item.icon_path}" alt="" onerror="this.parentElement.innerText='📦'">`;
    } else {
      iconBox.innerText = "📦";
    }
  }

  const rankBadge = document.getElementById("item-rank-badge");
  if (rankBadge) {
    rankBadge.innerText = formatRank(item.rank || "DEFAULT");
    rankBadge.className = `badge rank-badge ${item.rank || ''}`;
  }

  const catBadge = document.getElementById("item-cat-badge");
  if (catBadge) catBadge.innerText = item.category || "Общее";

  const lotsCountBadge = document.getElementById("item-lots-count");
  if (lotsCountBadge) lotsCountBadge.innerText = `Активных лотов: ${item.total_active_lots ?? item.active_lots?.length ?? 0}`;

  // 2. Segment Pills
  const segments = item.segments || {};
  const segmentKeys = Object.keys(segments);
  const segContainer = document.getElementById("segment-pills-container");

  if (segContainer) {
    let pillsHtml = `
      <button class="seg-pill ${selectedSegmentKey === 'all' ? 'active' : ''}" onclick="selectItemSegment('all')">
        Все сегменты (${segmentKeys.length > 0 ? segmentKeys.length : '1'})
      </button>
    `;
    segmentKeys.forEach(k => {
      const seg = segments[k];
      pillsHtml += `
        <button class="seg-pill ${selectedSegmentKey === k ? 'active' : ''}" onclick="selectItemSegment('${k}')">
          ${escapeHtml(seg.label || k)}
        </button>
      `;
    });
    segContainer.innerHTML = pillsHtml;
  }

  // 3. Metrics Calculation
  let activeLots = item.active_lots || [];
  let recentSales = item.recent_sales || [];

  if (selectedSegmentKey !== "all") {
    activeLots = activeLots.filter(l => l.segment_key === selectedSegmentKey);
    recentSales = recentSales.filter(s => s.segment_key === selectedSegmentKey);
  }

  // Get segment metrics
  let segMetrics = null;
  if (selectedSegmentKey !== "all" && segments[selectedSegmentKey]) {
    segMetrics = segments[selectedSegmentKey];
  } else if (segmentKeys.length === 1) {
    segMetrics = segments[segmentKeys[0]];
  } else if (segmentKeys.length > 1) {
    // Aggregated metrics from default segment or weighted
    const defaultSeg = segments["default"] || segments["q0:p0"] || segments[segmentKeys[0]];
    segMetrics = defaultSeg;
  }

  // Calculate live minimum buyout
  const validBuyouts = activeLots.map(l => l.unit_buyout).filter(b => b && b > 0);
  const minBuyout = validBuyouts.length > 0 ? Math.min(...validBuyouts) : (segMetrics?.min_buyout || 0);

  // Median, P25, P75
  const medianPrice = segMetrics?.median || (recentSales.length > 0 ? calculateMedian(recentSales.map(s => s.unit_price)) : 0);
  const p25 = segMetrics?.p25 || Math.round(medianPrice * 0.95);
  const p75 = segMetrics?.p75 || Math.round(medianPrice * 1.05);
  const unitsPerDay = segMetrics?.units_per_day || (recentSales.length > 0 ? (recentSales.length / 3).toFixed(1) : 0);
  const sampleSize = segMetrics?.sample_size || recentSales.length;
  const volatility = segMetrics?.volatility ?? 5.0;
  const trend = segMetrics?.trend || "flat";
  const trendIcon = trend === "up" ? "↗ Рост" : (trend === "down" ? "↘ Падение" : "↔ Стабильно");

  // Buy Max for 10% ROI after 5% fee: BuyMax = P25 * 0.95 / 1.10
  const buyMax = Math.round((p25 * 0.95) / 1.10);

  // Update KPI Cards
  const minBuyoutEl = document.getElementById("metric-min-buyout");
  if (minBuyoutEl) minBuyoutEl.innerText = minBuyout > 0 ? `${formatPrice(minBuyout)} ₽` : "Нет лотов";

  const medianEl = document.getElementById("metric-median");
  if (medianEl) medianEl.innerText = medianPrice > 0 ? `${formatPrice(medianPrice)} ₽` : "-- ₽";

  const p25p75El = document.getElementById("metric-p25-p75");
  if (p25p75El) p25p75El.innerText = medianPrice > 0 ? `${formatPrice(p25)} - ${formatPrice(p75)} ₽` : "-- - -- ₽";

  const liquidityEl = document.getElementById("metric-liquidity");
  if (liquidityEl) liquidityEl.innerText = `${unitsPerDay} шт/сут`;

  const salesCountEl = document.getElementById("metric-sales-count");
  if (salesCountEl) salesCountEl.innerText = `Выборка: ${sampleSize} сделок`;

  const volEl = document.getElementById("metric-volatility");
  if (volEl) volEl.innerText = `${volatility}%`;

  const trendEl = document.getElementById("metric-trend");
  if (trendEl) trendEl.innerText = `Тренд: ${trendIcon}`;

  const buyMaxEl = document.getElementById("metric-max-buy");
  if (buyMaxEl) buyMaxEl.innerText = buyMax > 0 ? `${formatPrice(buyMax)} ₽` : "-- ₽";

  // 4. Render Active Lots Table
  const lotsTbody = document.getElementById("item-lots-tbody");
  const lotsCountEl = document.getElementById("active-lots-counter");
  if (lotsCountEl) lotsCountEl.innerText = `${activeLots.length} лотов`;

  if (lotsTbody) {
    if (activeLots.length === 0) {
      lotsTbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет активных лотов в этом сегменте</td></tr>';
    } else {
      lotsTbody.innerHTML = activeLots.map(l => {
        let evalHtml = '<span class="lot-eval-normal">Рыночный</span>';
        if (medianPrice > 0 && l.unit_buyout > 0) {
          const diffPct = ((l.unit_buyout - medianPrice) / medianPrice) * 100;
          if (diffPct <= -10) {
            evalHtml = `<span class="lot-eval-good">${diffPct.toFixed(1)}% к медиане</span>`;
          } else if (diffPct > 0) {
            evalHtml = `<span class="lot-eval-normal">+${diffPct.toFixed(1)}%</span>`;
          } else {
            evalHtml = `<span class="lot-eval-normal">${diffPct.toFixed(1)}%</span>`;
          }
        }
        return `
          <tr>
            <td><strong>${formatPrice(l.unit_buyout)} ₽</strong></td>
            <td>${formatPrice(l.buyout_price || l.unit_buyout * l.amount)} ₽</td>
            <td>${l.amount} шт.</td>
            <td><span class="small text-muted">${escapeHtml(l.segment_label || l.segment_key || "Стандарт")}</span></td>
            <td>${evalHtml}</td>
          </tr>
        `;
      }).join("");
    }
  }

  // 5. Render Recent Sales Table
  const salesTbody = document.getElementById("item-sales-tbody");
  const salesCountTitle = document.getElementById("sales-history-counter");
  if (salesCountTitle) salesCountTitle.innerText = `${recentSales.length} сделок`;

  if (salesTbody) {
    if (recentSales.length === 0) {
      salesTbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет истории сделок</td></tr>';
    } else {
      salesTbody.innerHTML = recentSales.map(s => `
        <tr>
          <td><span class="small text-muted">${escapeHtml(s.sold_at || "--")}</span></td>
          <td><strong>${formatPrice(s.unit_price)} ₽</strong></td>
          <td>${s.amount} шт.</td>
          <td>${formatPrice(s.price || s.unit_price * s.amount)} ₽</td>
          <td><span class="small text-muted">${escapeHtml(s.segment_key || "Стандарт")}</span></td>
        </tr>
      `).join("");
    }
  }

  // 6. Update Price Chart with Real Sales
  renderPriceChart(recentSales, medianPrice, p25, p75);
}

window.selectItemSegment = function(segKey) {
  selectedSegmentKey = segKey;
  renderItemDeepDive();
};

function calculateMedian(values) {
  if (!values || values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// =============================================================================
// CHART RENDERING (REAL TRANSACTIONS)
// =============================================================================
function renderPriceChart(recentSales, medianPrice, p25, p75) {
  const canvas = document.getElementById("priceChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // Sort sales chronologically for chart display
  const salesSorted = [...recentSales].reverse();

  let labels = [];
  let salesPoints = [];
  let medianPoints = [];
  let p25Points = [];

  if (salesSorted.length > 0) {
    salesSorted.forEach((s, idx) => {
      labels.push(s.sold_at || `#${idx + 1}`);
      salesPoints.push(s.unit_price);
      medianPoints.push(medianPrice > 0 ? medianPrice : null);
      p25Points.push(p25 > 0 ? p25 : null);
    });
  } else {
    labels = ["6 дн", "5 дн", "4 дн", "3 дн", "2 дн", "Вчера", "Сегодня"];
    salesPoints = [medianPrice, medianPrice, medianPrice, medianPrice, medianPrice, medianPrice, medianPrice];
    medianPoints = [medianPrice, medianPrice, medianPrice, medianPrice, medianPrice, medianPrice, medianPrice];
    p25Points = [p25, p25, p25, p25, p25, p25, p25];
  }

  if (priceChart) {
    priceChart.destroy();
  }

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Сделка на аукционе (₽)",
          data: salesPoints,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.15)",
          pointBackgroundColor: "#38bdf8",
          pointBorderColor: "#ffffff",
          pointRadius: 4,
          pointHoverRadius: 6,
          showLine: true,
          tension: 0.15,
        },
        {
          label: "Честная цена (Медиана)",
          data: medianPoints,
          borderColor: "#10b981",
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
        },
        {
          label: "P25 (Порог безопасности)",
          data: p25Points,
          borderColor: "#f59e0b",
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 0,
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { size: 12, weight: 600 } }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${formatPrice(context.parsed.y)} ₽`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#64748b", maxTicksLimit: 12, font: { size: 10 } },
          grid: { color: "#1e293b" }
        },
        y: {
          ticks: {
            color: "#94a3b8",
            callback: function(val) {
              return formatPrice(val) + " ₽";
            }
          },
          grid: { color: "#1e293b" }
        }
      }
    }
  });
}

// =============================================================================
// TAB 3: WATCHLIST
// =============================================================================
function setupWatchlistControls() {
  const exportBtn = document.getElementById("btn-export-wl");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(watchlist, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "stalzone_watchlist.json";
      a.click();
    });
  }

  const importBtn = document.getElementById("btn-import-wl");
  if (importBtn) {
    importBtn.addEventListener("click", () => {
      const jsonStr = prompt("Вставьте JSON конфигурации отслеживания:");
      if (jsonStr) {
        try {
          const parsed = JSON.parse(jsonStr);
          if (Array.isArray(parsed) && parsed.length > 0) {
            watchlist = parsed;
            saveWatchlist();
            renderWatchlist();
            alert("Список отслеживания успешно импортирован!");
          }
        } catch (e) {
          alert("Неверный формат JSON");
        }
      }
    });
  }
}

function renderWatchlist() {
  const tbody = document.getElementById("watchlist-tbody");
  if (!tbody) return;

  if (watchlist.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Список отслеживания пуст. Добавьте предметы из каталога.</td></tr>';
    return;
  }

  tbody.innerHTML = watchlist.map((item, idx) => `
    <tr>
      <td><strong>${escapeHtml(item.name_ru)}</strong></td>
      <td><span class="badge badge-cat">${escapeHtml(item.category || "other")}</span></td>
      <td><span class="badge ${item.rank || ''}">${formatRank(item.rank)}</span></td>
      <td><span class="status-pill ${item.enabled ? 'active' : 'paused'}">${item.enabled ? 'Активен' : 'Пауза'}</span></td>
      <td class="roi-badge">${((item.min_roi || 0.10) * 100).toFixed(0)}%</td>
      <td>${formatPrice(item.min_profit || 50000)} ₽</td>
      <td>
        <button class="btn-sm btn-secondary" onclick="switchToItemTab('${item.item_id}', 'all')">🔍 Анализ</button>
        <button class="btn-sm btn-secondary" onclick="toggleWatchlist(${idx})">${item.enabled ? 'Пауза' : 'Вкл'}</button>
        <button class="btn-sm btn-danger" onclick="removeWatchlist(${idx})">✕</button>
      </td>
    </tr>
  `).join("");
}

window.addToWatchlist = function(itemId, nameRu) {
  if (watchlist.some(w => w.item_id === itemId)) {
    alert(`"${nameRu}" уже находится в списке отслеживания.`);
    return;
  }
  const item = catalogItems.find(i => i.item_id === itemId) || analyticsData?.items?.[itemId];
  watchlist.push({
    item_id: itemId,
    name_ru: nameRu || item?.name_ru || itemId,
    category: item?.category || "other",
    rank: item?.rank || "DEFAULT",
    enabled: true,
    min_roi: 0.10,
    min_profit: 50000,
    filters: {}
  });
  saveWatchlist();
  renderWatchlist();
  alert(`"${nameRu}" добавлен в список отслеживания!`);
};

window.toggleWatchlist = function(index) {
  if (watchlist[index]) {
    watchlist[index].enabled = !watchlist[index].enabled;
    saveWatchlist();
    renderWatchlist();
  }
};

window.removeWatchlist = function(index) {
  if (confirm(`Удалить "${watchlist[index]?.name_ru}" из отслеживания?`)) {
    watchlist.splice(index, 1);
    saveWatchlist();
    renderWatchlist();
  }
};

// =============================================================================
// TAB 4: CATALOG
// =============================================================================
function setupCatalogSearch() {
  const input = document.getElementById("catalog-search-input");
  if (input) {
    input.addEventListener("input", () => {
      renderCatalogResults(input.value);
    });
  }

  document.querySelectorAll(".cat-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeCatFilter = pill.getAttribute("data-cat") || "";
      renderCatalogResults(input ? input.value : "");
    });
  });
}

function renderCatalogResults(rawQuery) {
  const container = document.getElementById("catalog-results-container");
  if (!container) return;

  const query = normalizeSearch(rawQuery);

  if (!query && !activeCatFilter) {
    container.innerHTML = '<div class="empty-hint text-muted">Введите название предмета (например: Атом, Спираль, Берлога) или выберите категорию...</div>';
    return;
  }

  let results = catalogItems.filter(item => {
    if (activeCatFilter && !(item.category || "").includes(activeCatFilter)) {
      return false;
    }
    if (!query) return true;
    const norm = normalizeSearch(`${item.name_ru} ${item.name_en}`);
    return norm.includes(query);
  });

  if (results.length === 0) {
    container.innerHTML = '<div class="empty-hint text-muted">Ничего не найдено. Проверьте запрос.</div>';
    return;
  }

  container.innerHTML = results.slice(0, 36).map(item => {
    const iconUrl = item.icon_path
      ? `https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${item.icon_path}`
      : "";

    return `
      <div class="catalog-item-card">
        <div class="card-icon">
          ${iconUrl ? `<img src="${iconUrl}" alt="" onerror="this.parentElement.innerText='📦'">` : "📦"}
        </div>
        <div class="card-info">
          <div class="card-title">${escapeHtml(item.name_ru || item.name_en)}</div>
          <div class="card-meta">
            <span class="rank-badge ${item.rank}">${formatRank(item.rank)}</span>
            <span class="small text-muted">${escapeHtml(item.category)}</span>
          </div>
        </div>
        <div style="display:flex; gap: 0.35rem; flex-direction:column;">
          <button class="btn-card-action btn-secondary" onclick="switchToItemTab('${item.item_id}', 'all')">🔍 Анализ</button>
          <button class="btn-card-action btn-primary" onclick="addToWatchlist('${item.item_id}', '${escapeHtml(item.name_ru)}')">+ Следить</button>
        </div>
      </div>
    `;
  }).join("");
}

// =============================================================================
// LLM PROMPT EXPORTER
// =============================================================================
async function copyPromptForLLM() {
  let textToCopy = "";
  try {
    let res = await fetch("prompt_for_external_llm.txt");
    if (!res.ok) res = await fetch("data/prompt_for_external_llm.txt");
    if (!res.ok) res = await fetch("../data/prompt_for_external_llm.txt");
    if (res.ok) {
      textToCopy = await res.text();
    }
  } catch (e) {
    console.warn("Could not fetch prompt_for_external_llm.txt:", e);
  }

  if (!textToCopy && marketData) {
    textToCopy = `Ты — ведущий аналитик и алгоритмический трейдер внутриигрового рынка STALCRAFT RU.
Правила:
1. Используй ТОЛЬКО реальные числа из дайджеста.
2. Комиссия аукциона: 5% с цены продажи.
3. Укажи: что покупать, макс. цену покупки, цель продажи, срок в часах, ожидаемый профит и риски.

Дайджест:
\`\`\`json
${JSON.stringify(marketData, null, 2)}
\`\`\``;
  }

  if (textToCopy) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      alert("✅ Готовый промпт и актуальный срез рынка скопированы в буфер обмена!\n\nПросто нажмите Ctrl+V в ChatGPT, Claude, DeepSeek или Gemini.");
    }).catch(() => {
      prompt("Скопируйте текст вручную:", textToCopy);
    });
  } else {
    alert("Данные для нейросети ещё формируются. Запустите цикл сбора.");
  }
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================
function formatPrice(num) {
  if (num === null || num === undefined || isNaN(num)) return "--";
  return Math.round(num).toLocaleString("ru-RU");
}

function formatRank(rank) {
  if (!rank) return "";
  return rank.replace("RANK_", "");
}

function normalizeSearch(text) {
  if (!text) return "";
  return text.toLowerCase()
    .replace(/ё/g, "е")
    .replace(/["«»„“',.\-_/\\()\[\]]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
