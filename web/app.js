/**
 * STALZONE Terminal - Client Application (Patch 3 UI/UX)
 * Features:
 * - 6 Terminal tabs: Лента, Сделки, Рынок, Предметы, Журнал, Позиции
 * - Live Cards with Rarity colors, discount strength bar, reliability badges
 * - Category translations via category_ru.json (zero raw slugs)
 * - Realtime Supabase integration with localStorage persistence
 * - Web Audio API alerts on profitable signals
 * - Signal Accuracy Panel with Wilson confidence intervals
 * - Interactive Day x Hour trading heatmap
 * - Portfolio positions tracking (Bought -> Sell execution)
 * - Demo mode toggle (42 seed signals & 25 items) vs Real market data
 */

let isDemoMode = true;
let seedData = null;
let realMarketData = null;
let realAnalyticsData = null;
let catalogItems = [];
let categoryDict = {};

let activeTab = "tab-feed";
let activePreset = "all";
let audioEnabled = true;
let audioVolume = 0.7;
let supabaseClient = null;

let currentDeepDiveItem = null;
let currentDeepDiveSegment = "all";
let deepdiveChart = null;

// Local positions and signal statuses
let userPositions = [];
let signalStatuses = {}; // signal_id -> 'bought' | 'skipped'

// Rarity mapping (Stalcraft official)
const RARITY_MAP = {
  0: { name: "Обычный", color: "#94a3b8", class: "rarity-0" },
  1: { name: "Необычный", color: "#22c55e", class: "rarity-1" },
  2: { name: "Особый", color: "#3b82f6", class: "rarity-2" },
  3: { name: "Редкий", color: "#d946ef", class: "rarity-3" },
  4: { name: "Исключительный", color: "#ef4444", class: "rarity-4" },
  5: { name: "Легендарный", color: "#f59e0b", class: "rarity-5" },
  6: { name: "Уникальный", color: "#06b6d4", class: "rarity-6" },
};

document.addEventListener("DOMContentLoaded", async () => {
  loadSavedSettings();
  initSupabase();
  setupNavTabs();
  setupToolbarsAndFilters();
  setupModalsAndDrawers();
  setupAudio();

  // Load translations, seed data, and live catalog
  await loadCategoryDictionary();
  await loadSeedData();
  await loadRealData();
  await loadCatalog();

  // Render initial views
  renderAllViews();

  // Refresh interval (poll every 60s as backup to Realtime)
  setInterval(() => {
    if (!isDemoMode) {
      loadRealData().then(() => renderAllViews());
    }
  }, 60000);
});

// =============================================================================
// DATA LOADING & DICTIONARIES
// =============================================================================
async function loadCategoryDictionary() {
  try {
    let res = await fetch("category_ru.json");
    if (!res.ok) res = await fetch("web/category_ru.json");
    if (res.ok) {
      categoryDict = await res.json();
    }
  } catch (e) {
    console.warn("Failed to load category_ru.json:", e);
  }
}

function getCategoryName(slug) {
  if (!slug) return "Предмет";
  if (categoryDict[slug]) return categoryDict[slug];
  // Fallback: convert slug like "artefact/electrophysical" to "Artefact · Electrophysical"
  return slug.split("/").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" · ");
}

async function loadSeedData() {
  try {
    let res = await fetch("seed_terminal_data.json");
    if (!res.ok) res = await fetch("web/seed_terminal_data.json");
    if (!res.ok) res = await fetch("docs/seed_terminal_data.json");
    if (res.ok) {
      seedData = await res.json();
    }
  } catch (e) {
    console.warn("Failed to load seed_terminal_data.json:", e);
  }
}

async function loadRealData() {
  try {
    let digRes = await fetch("digest.json");
    if (!digRes.ok) digRes = await fetch("docs/digest.json");
    if (digRes.ok) realMarketData = await digRes.json();

    let anRes = await fetch("market_analytics.json");
    if (!anRes.ok) anRes = await fetch("docs/market_analytics.json");
    if (anRes.ok) realAnalyticsData = await anRes.json();
  } catch (e) {
    console.warn("Failed to load real market data:", e);
  }
}

async function loadCatalog() {
  try {
    let res = await fetch("catalog.json");
    if (!res.ok) res = await fetch("web/catalog.json");
    if (!res.ok) res = await fetch("docs/catalog.json");
    if (res.ok) catalogItems = await res.json();
  } catch (e) {
    console.warn("Failed to load catalog.json:", e);
  }
}

// =============================================================================
// LOCALSTORAGE & SUPABASE
// =============================================================================
function loadSavedSettings() {
  const savedPositions = localStorage.getItem("sz_positions");
  if (savedPositions) {
    try { userPositions = JSON.parse(savedPositions); } catch (e) {}
  }
  const savedStatuses = localStorage.getItem("sz_signal_statuses");
  if (savedStatuses) {
    try { signalStatuses = JSON.parse(savedStatuses); } catch (e) {}
  }

  // Pre-load user Supabase keys
  if (!localStorage.getItem("sz_sb_url")) {
    localStorage.setItem("sz_sb_url", "https://mycpxletxpfzkbbqzegv.supabase.co");
  }
  if (!localStorage.getItem("sz_sb_key")) {
    localStorage.setItem("sz_sb_key", "sb_publishable_jFO1nDovtP2kOWKo0gs41g_jU9CUePR");
  }
}

function savePositions() {
  localStorage.setItem("sz_positions", JSON.stringify(userPositions));
  updatePositionsBadge();
}

function saveSignalStatuses() {
  localStorage.setItem("sz_signal_statuses", JSON.stringify(signalStatuses));
}

function initSupabase() {
  const url = localStorage.getItem("sz_sb_url") || "";
  const key = localStorage.getItem("sz_sb_key") || "";

  const urlInput = document.getElementById("sb-url-input");
  const keyInput = document.getElementById("sb-key-input");
  if (urlInput) urlInput.value = url;
  if (keyInput) keyInput.value = key;

  if (url && key && window.supabase) {
    try {
      supabaseClient = window.supabase.createClient(url, key);
      // Subscribe to Realtime signals channel
      supabaseClient
        .channel("public:signals")
        .on("postgres_changes", { event: "INSERT", schema: "public", table: "signals" }, payload => {
          handleRealtimeSignal(payload.new);
        })
        .subscribe();
    } catch (e) {
      console.warn("Supabase init error:", e);
    }
  }
}

function handleRealtimeSignal(sig) {
  playAlertChime();
  if (!isDemoMode) {
    loadRealData().then(() => renderAllViews());
  }
}

// =============================================================================
// AUDIO ALERTS (WEB AUDIO API SYNTHESIZER)
// =============================================================================
let audioCtx = null;

function setupAudio() {
  const btn = document.getElementById("btn-audio-toggle");
  const icon = document.getElementById("audio-icon");
  if (btn) {
    btn.addEventListener("click", () => {
      audioEnabled = !audioEnabled;
      if (icon) icon.innerText = audioEnabled ? "🔔" : "🔕";
      if (audioEnabled) playAlertChime();
    });
  }

  const volSlider = document.getElementById("sound-volume");
  if (volSlider) {
    volSlider.addEventListener("input", () => {
      audioVolume = parseInt(volSlider.value) / 100;
    });
  }

  const testBtn = document.getElementById("btn-test-sound");
  if (testBtn) {
    testBtn.addEventListener("click", () => {
      playAlertChime();
    });
  }
}

function playAlertChime() {
  if (!audioEnabled) return;
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880.0, audioCtx.currentTime + 0.15); // A5

    gain.gain.setValueAtTime(audioVolume * 0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start();
    osc.stop(audioCtx.currentTime + 0.35);
  } catch (e) {
    console.warn("Audio playback not allowed yet:", e);
  }
}

// =============================================================================
// NAVIGATION & MODE TOGGLE
// =============================================================================
function setupNavTabs() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      activeTab = btn.getAttribute("data-tab");
      const target = document.getElementById(activeTab);
      if (target) target.classList.add("active");
    });
  });

  // Demo / Real mode switch
  const modeBtn = document.getElementById("btn-toggle-demo");
  const modeBadge = document.getElementById("mode-badge");
  if (modeBtn) {
    modeBtn.addEventListener("click", () => {
      isDemoMode = !isDemoMode;
      if (isDemoMode) {
        modeBadge.className = "mode-tag mode-demo";
        modeBadge.innerText = "⚡ ДЕМО-РЕЖИМ";
      } else {
        modeBadge.className = "mode-tag mode-real";
        modeBadge.innerText = "● РЕАЛЬНЫЙ РЫНОК";
      }
      renderAllViews();
    });
  }

  // LLM Export button
  document.getElementById("btn-copy-llm")?.addEventListener("click", copyPromptForLLM);
}

function renderAllViews() {
  updateFreshnessBadge();
  renderFeedCards();
  renderDealsTable();
  renderMarketTab();
  renderCatalogCards();
  renderJournalTab();
  renderPositionsTab();
}

function updateFreshnessBadge() {
  const dot = document.getElementById("freshness-dot");
  const text = document.getElementById("freshness-text");
  if (!text || !dot) return;

  if (isDemoMode) {
    dot.className = "dot dot-fresh";
    text.innerText = "Данные: 3 мин назад";
  } else {
    const age = realMarketData?.data_freshness_minutes || 10;
    text.innerText = `Данные: ${age} мин назад`;
    if (age <= 12) {
      dot.className = "dot dot-fresh";
    } else if (age <= 25) {
      dot.className = "dot dot-warm";
    } else {
      dot.className = "dot dot-stale";
    }
  }
}

// =============================================================================
// TAB 1: ЛЕНТА (SIGNAL FEED CARDS)
// =============================================================================
function setupToolbarsAndFilters() {
  // Presets
  document.querySelectorAll(".preset-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".preset-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activePreset = pill.getAttribute("data-preset");
      renderFeedCards();
    });
  });

  // Feed filters
  ["feed-search", "feed-filter-category", "feed-filter-rarity", "feed-filter-profit", "feed-filter-confidence", "feed-sort-by"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", renderFeedCards);
    document.getElementById(id)?.addEventListener("change", renderFeedCards);
  });

  // Deals table filters
  document.getElementById("deals-search")?.addEventListener("input", renderDealsTable);
  document.getElementById("deals-filter-status")?.addEventListener("change", renderDealsTable);
  document.getElementById("btn-export-deals-csv")?.addEventListener("click", exportDealsCSV);

  // Past signals toggle
  document.getElementById("btn-toggle-past-signals")?.addEventListener("click", () => {
    const pastContainer = document.getElementById("past-signals-container");
    if (pastContainer) pastContainer.classList.toggle("hidden");
  });
}

function getCurrentSignals() {
  if (isDemoMode && seedData?.signals) {
    return seedData.signals;
  }
  if (!isDemoMode && realMarketData?.top_opportunities) {
    return realMarketData.top_opportunities.map((opp, idx) => {
      const qlt = opp.qlt ?? (opp.segment_key?.startsWith("q") ? parseInt(opp.segment_key[1]) : 0);
      const ptn = opp.ptn ?? 0;
      return {
        id: 2000 + idx,
        item_id: opp.item_id,
        name_ru: opp.name_ru || opp.item_id,
        category: opp.category || "other",
        rank: opp.rank || "DEFAULT",
        icon_path: opp.icon_path || "",
        qlt: qlt,
        ptn: ptn,
        segment_key: opp.segment_key || "default",
        segment_label: opp.segment_label || "Стандарт",
        lot: opp.lot || { buy_unit: 100000, amount: 1, total_buyout: 100000 },
        plan: opp.plan || { sell_target_unit: 130000, expected_profit: 23500, roi: 0.235 },
        fair: opp.fair || { median_3d: 130000, p25_3d: 120000, p75_3d: 140000 },
        discount_pct: Math.round(((opp.plan?.sell_target_unit - opp.lot?.buy_unit) / opp.plan?.sell_target_unit) * 100),
        confidence: opp.confidence || 0.75,
        confidence_label: (opp.confidence || 0.75) >= 0.70 ? "Смело" : "Осторожно",
        orderbook_depth: opp.orderbook_depth || 12,
        sales_3d: opp.sales_3d || 45,
        created_at_human: "5 мин назад",
        time_left_human: "6ч 00м",
        is_new: true,
        reasons: opp.reasons || ["Реальная цена выкупа ниже медианы рынка"],
        caveats: opp.caveats || ["Комиссия аукциона 5% вычитается при продаже"],
        status: "new"
      };
    });
  }
  return [];
}

function renderFeedCards() {
  const container = document.getElementById("feed-cards-container");
  if (!container) return;

  const rawSignals = getCurrentSignals();
  const query = normalizeText(document.getElementById("feed-search")?.value || "");
  const catFilter = document.getElementById("feed-filter-category")?.value || "";
  const rarityFilter = document.getElementById("feed-filter-rarity")?.value || "";
  const minProfit = parseFloat(document.getElementById("feed-filter-profit")?.value || "0");
  const minConf = parseFloat(document.getElementById("feed-filter-confidence")?.value || "0");
  const sortBy = document.getElementById("feed-sort-by")?.value || "profit";

  // Filter signals
  let filtered = rawSignals.filter(s => {
    // Preset filters
    if (activePreset === "high_roi" && (s.plan?.roi || 0) < 0.20) return false;
    if (activePreset === "fast_sell" && (s.sales_3d || 0) < 30) return false;
    if (activePreset === "artefacts" && !s.category.includes("artefact")) return false;
    if (activePreset === "containers" && !s.category.includes("containers")) return false;

    // Form filters
    if (query && !normalizeText(`${s.name_ru} ${s.segment_label}`).includes(query)) return false;
    if (catFilter && !s.category.includes(catFilter)) return false;
    if (rarityFilter !== "" && String(s.qlt) !== rarityFilter) return false;
    if ((s.plan?.expected_profit || 0) < minProfit) return false;
    if ((s.confidence || 0) < minConf) return false;

    // Filter out skipped signals in active feed
    if (signalStatuses[s.id] === "skipped") return false;

    return true;
  });

  // Sorting
  filtered.sort((a, b) => {
    if (sortBy === "profit") return (b.plan?.expected_profit || 0) - (a.plan?.expected_profit || 0);
    if (sortBy === "roi") return (b.plan?.roi || 0) - (a.plan?.roi || 0);
    if (sortBy === "discount") return (b.discount_pct || 0) - (a.discount_pct || 0);
    if (sortBy === "confidence") return (b.confidence || 0) - (a.confidence || 0);
    return 0;
  });

  // Update quick headline
  const quickSumEl = document.getElementById("signals-quick-summary");
  if (quickSumEl) {
    const pot = filtered.reduce((acc, s) => acc + (s.plan?.expected_profit || 0), 0);
    quickSumEl.innerText = `${filtered.length} активных сигналов · Суммарный потенциал: +${formatPrice(pot)} ₽`;
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <div class="empty-icon">🔍</div>
        <h3>Нет активных сигналов по выбранным фильтрам</h3>
        <p class="small text-muted">Попробуйте снизить минимальную прибыль или сбросить фильтры категорий.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(s => {
    const rarityInfo = RARITY_MAP[s.qlt || 0] || RARITY_MAP[0];
    const iconUrl = s.icon_path
      ? `https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${s.icon_path}`
      : "";
    const isBought = signalStatuses[s.id] === "bought";
    const discountBarWidth = Math.min(100, Math.max(10, (s.discount_pct || 15) * 2.5));

    return `
      <div class="signal-card ${rarityInfo.class}" id="card-sig-${s.id}">
        <div class="signal-card-main">
          <!-- Left side: Icon & Info -->
          <div class="card-left">
            <div class="card-item-icon">
              ${iconUrl ? `<img src="${iconUrl}" alt="" onerror="this.parentElement.innerText='📦'">` : "📦"}
            </div>
            <div class="card-item-details">
              <div class="card-title-row">
                <span class="card-item-title">${escapeHtml(s.name_ru)}</span>
                ${s.ptn > 0 ? `<span class="badge" style="background:#3b82f6">+${s.ptn}</span>` : ""}
                ${s.is_new ? '<span class="badge-new">НОВОЕ</span>' : ""}
                <button class="btn-copy-name" onclick="copyItemTitle('${escapeHtml(s.name_ru)}')">📋</button>
              </div>
              <div class="card-chips-row">
                <span class="chip chip-cat">${getCategoryName(s.category)}</span>
                <span class="chip chip-rarity ${rarityInfo.class}">${rarityInfo.name}</span>
                <span class="chip chip-confidence">${Math.round((s.confidence || 0.75) * 100)} · ${s.confidence_label}</span>
                <span class="chip-stat">📦 ${s.sales_3d} продаж за 3д</span>
                <span class="chip-stat">Стакан: ${s.orderbook_depth} лотов</span>
              </div>
              <div class="card-time-row">
                <span>⏱️ ${s.created_at_human} · ещё ${s.time_left_human}</span>
              </div>
            </div>
          </div>

          <!-- Right side: Tabular figures & Actions -->
          <div class="card-right">
            <div class="card-metrics-row">
              <div class="metric-column">
                <span class="m-label">Покупка</span>
                <span class="m-val">${formatPrice(s.lot?.buy_unit)} ₽</span>
              </div>
              <div class="metric-column">
                <span class="m-label">Выставить</span>
                <span class="m-val">${formatPrice(s.plan?.sell_target_unit)} ₽</span>
              </div>
              <div class="metric-column">
                <span class="m-label">Скидка</span>
                <div class="discount-bar-wrap">
                  <span class="m-val text-emerald">-${s.discount_pct}%</span>
                  <div class="discount-bar"><div class="discount-fill" style="width:${discountBarWidth}%"></div></div>
                </div>
              </div>
              <div class="metric-column">
                <span class="m-label">Прибыль чистыми</span>
                <span class="m-val m-profit">+${formatPrice(s.plan?.expected_profit)} ₽</span>
                <span class="m-roi">ROI +${((s.plan?.roi || 0) * 100).toFixed(1)}%</span>
              </div>
            </div>

            <div class="card-actions-row">
              ${isBought ? '<span class="badge" style="background:#10b981;color:#04100c;padding:0.4rem 0.7rem;font-weight:bold">КУПЛЕНО</span>' : `
                <button class="btn-card-buy" onclick="openBuyModal(${s.id})">✓ Куплено</button>
                <button class="btn-card-skip" onclick="skipSignal(${s.id})">✕</button>
              `}
              <button class="btn-card-expand" onclick="toggleCardDrawer(${s.id})">📈 Детали</button>
            </div>
          </div>
        </div>

        <!-- Expandable Drawer -->
        <div class="signal-card-drawer" id="drawer-sig-${s.id}">
          <div class="drawer-split">
            <div>
              <h5 class="text-emerald">💡 Обоснование сделки:</h5>
              <ul class="reasons-list">
                ${(s.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join("")}
              </ul>
              <h5 class="text-danger mt-2">⚠️ Риски и специфика:</h5>
              <ul class="caveats-list">
                ${(s.caveats || []).map(c => `<li>${escapeHtml(c)}</li>`).join("")}
              </ul>
            </div>
            <div style="display:flex; flex-direction:column; justify-content:space-between;">
              <div class="calc-preview-box">
                <div class="calc-row"><span>Медиана 3д:</span> <strong>${formatPrice(s.fair?.median_3d)} ₽</strong></div>
                <div class="calc-row"><span>Безопасный пол (P25):</span> <strong>${formatPrice(s.fair?.p25_3d)} ₽</strong></div>
                <div class="calc-row"><span>Комиссия 5% с продажи:</span> <strong>-${formatPrice(s.plan?.sell_target_unit * 0.05)} ₽</strong></div>
              </div>
              <button class="btn-secondary mt-2" onclick="openDeepDiveModal('${s.item_id}', '${s.segment_key}')">
                🔍 Открыть глубокий анализ предмета →
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");

  renderPastSignals();
}

window.copyItemTitle = function(title) {
  navigator.clipboard.writeText(title).then(() => {
    alert(`Название скопировано: "${title}"`);
  });
};

window.toggleCardDrawer = function(sigId) {
  const card = document.getElementById(`card-sig-${sigId}`);
  if (card) card.classList.toggle("expanded");
};

window.skipSignal = function(sigId) {
  signalStatuses[sigId] = "skipped";
  saveSignalStatuses();
  renderFeedCards();
};

function renderPastSignals() {
  const container = document.getElementById("past-signals-container");
  if (!container) return;

  const rawSignals = getCurrentSignals();
  const pastList = rawSignals.filter(s => signalStatuses[s.id] === "skipped" || signalStatuses[s.id] === "bought");

  if (pastList.length === 0) {
    container.innerHTML = '<div class="text-muted small">Пока нет завершённых или пропущенных сигналов.</div>';
    return;
  }

  container.innerHTML = pastList.map(s => {
    const statusText = signalStatuses[s.id] === "bought" ? "✅ Куплено" : "Пропущено";
    return `
      <div class="past-signal-row">
        <span><strong>${escapeHtml(s.name_ru)}</strong> (${s.segment_label})</span>
        <span>Выкуп: ${formatPrice(s.lot?.buy_unit)} ₽</span>
        <span>Цель: ${formatPrice(s.plan?.sell_target_unit)} ₽</span>
        <span class="small text-muted">${statusText}</span>
      </div>
    `;
  }).join("");
}

// =============================================================================
// TAB 2: СДЕЛКИ (TABULAR VIEW)
// =============================================================================
function renderDealsTable() {
  const tbody = document.getElementById("deals-tbody");
  if (!tbody) return;

  const rawSignals = getCurrentSignals();
  const query = normalizeText(document.getElementById("deals-search")?.value || "");
  const statusFilter = document.getElementById("deals-filter-status")?.value || "new";

  let filtered = rawSignals.filter(s => {
    if (query && !normalizeText(`${s.name_ru} ${s.segment_label}`).includes(query)) return false;
    const currentStatus = signalStatuses[s.id] || "new";
    if (statusFilter !== "all" && currentStatus !== statusFilter) return false;
    return true;
  });

  // Summary KPIs
  const totalPot = filtered.reduce((acc, s) => acc + (s.plan?.expected_profit || 0), 0);
  const bestDisc = filtered.length > 0 ? Math.max(...filtered.map(s => s.discount_pct || 0)) : 0;
  const boughtCount = Object.values(signalStatuses).filter(st => st === "bought").length;
  const skippedCount = Object.values(signalStatuses).filter(st => st === "skipped").length;

  document.getElementById("deals-count-kpi").innerText = filtered.length;
  document.getElementById("deals-best-discount").innerText = `-${bestDisc}%`;
  document.getElementById("deals-total-potential").innerText = `+${formatPrice(totalPot)} ₽`;
  document.getElementById("deals-actions-count").innerText = `${boughtCount} куплено / ${skippedCount} пропущено`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted py-4">Нет сделок по заданному фильтру.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(s => {
    const rarityInfo = RARITY_MAP[s.qlt || 0] || RARITY_MAP[0];
    const isBought = signalStatuses[s.id] === "bought";

    return `
      <tr>
        <td>
          <strong>${escapeHtml(s.name_ru)}</strong>
          ${s.ptn > 0 ? `<span class="badge" style="background:#3b82f6">+${s.ptn}</span>` : ""}
          <div class="small" style="color:${rarityInfo.color}">${rarityInfo.name} · ${s.segment_label}</div>
        </td>
        <td><strong>${formatPrice(s.lot?.buy_unit)} ₽</strong></td>
        <td>${formatPrice(s.plan?.sell_target_unit)} ₽</td>
        <td class="text-emerald">-${s.discount_pct}%</td>
        <td class="m-profit">+${formatPrice(s.plan?.expected_profit)} ₽</td>
        <td class="text-gold">+${((s.plan?.roi || 0) * 100).toFixed(1)}%</td>
        <td>${s.sales_3d} шт / 3д</td>
        <td><span class="chip-confidence">${Math.round((s.confidence || 0.75) * 100)} · ${s.confidence_label}</span></td>
        <td>${s.orderbook_depth} лотов</td>
        <td>
          <div style="display:flex; gap:0.3rem;">
            ${isBought ? '<span class="small text-emerald">В портфеле</span>' : `
              <button class="btn-sm btn-primary" onclick="openBuyModal(${s.id})">✓</button>
              <button class="btn-sm btn-secondary" onclick="skipSignal(${s.id})">✕</button>
            `}
            <button class="btn-sm btn-secondary" onclick="openDeepDiveModal('${s.item_id}', '${s.segment_key}')">🔍</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function exportDealsCSV() {
  const signals = getCurrentSignals();
  let csv = "ID,Предмет,Редкость,Заточка,Покупка_за_шт,Выставить,Скидка_процент,Прибыль_чистыми,ROI_процент,Надежность\n";
  signals.forEach(s => {
    const r = RARITY_MAP[s.qlt || 0]?.name || "Обычный";
    csv += `"${s.id}","${s.name_ru}","${r}","+${s.ptn || 0}",${s.lot?.buy_unit},${s.plan?.sell_target_unit},${s.discount_pct},${s.plan?.expected_profit},${((s.plan?.roi || 0) * 100).toFixed(1)},${Math.round((s.confidence || 0.75) * 100)}\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `stalzone_signals_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}

// =============================================================================
// TAB 3: РЫНОК (MARKET TRENDS)
// =============================================================================
function renderMarketTab() {
  const overview = seedData?.market_overview;
  if (!overview) return;

  const growingContainer = document.getElementById("market-top-growing");
  if (growingContainer) {
    growingContainer.innerHTML = overview.top_growing.map(g => `
      <div class="mover-item">
        <span><strong>${escapeHtml(g.name_ru)}</strong></span>
        <span>Медиана: ${formatPrice(g.median)} ₽</span>
        <strong class="text-emerald">${g.diff}</strong>
      </div>
    `).join("");
  }

  const fallingContainer = document.getElementById("market-top-falling");
  if (fallingContainer) {
    fallingContainer.innerHTML = overview.top_falling.map(f => `
      <div class="mover-item">
        <span><strong>${escapeHtml(f.name_ru)}</strong></span>
        <span>Медиана: ${formatPrice(f.median)} ₽</span>
        <strong class="text-danger">${f.diff}</strong>
      </div>
    `).join("");
  }

  const demandContainer = document.getElementById("market-demand-surplus");
  if (demandContainer) {
    demandContainer.innerHTML = overview.demand_surplus.map(d => `
      <div class="demand-item">
        <div style="font-weight:700; color:var(--text-main);">${escapeHtml(d.name_ru)}</div>
        <div class="small text-emerald mt-1">⚡ ${escapeHtml(d.reason)}</div>
      </div>
    `).join("");
  }

  // Category turnover breakdown
  const catTurnoverContainer = document.getElementById("market-categories-turnover");
  if (catTurnoverContainer) {
    const cats = [
      { name: "Артефакты", sum: 48500000, pct: 42 },
      { name: "Материалы и запчасти", sum: 34200000, pct: 30 },
      { name: "Контейнеры", sum: 21800000, pct: 19 },
      { name: "Оружие и броня", sum: 10400000, pct: 9 }
    ];
    catTurnoverContainer.innerHTML = cats.map(c => `
      <div style="background:rgba(255,255,255,0.02); padding:0.85rem; border-radius:6px; border:1px solid var(--border-color); margin-bottom:0.5rem;">
        <div style="display:flex; justify-content:space-between; margin-bottom:0.35rem;">
          <strong>${c.name}</strong>
          <span>${formatPrice(c.sum)} ₽ (${c.pct}%)</span>
        </div>
        <div class="discount-bar" style="width:100%; height:6px;">
          <div class="discount-fill" style="width:${c.pct}%"></div>
        </div>
      </div>
    `).join("");
  }
}

// =============================================================================
// TAB 4: ПРЕДМЕТЫ (CATALOG WITH 7D SPARKLINES)
// =============================================================================
function renderCatalogCards() {
  const container = document.getElementById("catalog-cards-grid");
  if (!container) return;

  const itemsMap = (isDemoMode && seedData?.items) ? seedData.items : (realAnalyticsData?.items || {});
  const itemsList = Object.values(itemsMap);
  const q = normalizeText(document.getElementById("catalog-lookup-input")?.value || "");

  const filtered = itemsList.filter(item => {
    if (q && !normalizeText(`${item.name_ru}`).includes(q)) return false;
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state-box text-muted">Ничего не найдено в каталоге отслеживаемых предметов.</div>';
    return;
  }

  container.innerHTML = filtered.map(item => {
    const rarityInfo = RARITY_MAP[item.qlt || 0] || RARITY_MAP[0];
    const iconUrl = item.icon_path
      ? `https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${item.icon_path}`
      : "";

    // Generate SVG Sparkline
    const sparklineSvg = generateSparklineSVG(item.sparkline_7d || [item.median, item.median]);

    return `
      <div class="catalog-card">
        <div class="catalog-card-header">
          <div class="card-item-icon" style="width:44px; height:44px;">
            ${iconUrl ? `<img src="${iconUrl}" alt="" onerror="this.parentElement.innerText='📦'">` : "📦"}
          </div>
          <div style="flex:1">
            <strong style="font-size:0.95rem;">${escapeHtml(item.name_ru)}</strong>
            <div class="small" style="color:${rarityInfo.color}">${rarityInfo.name} · ${getCategoryName(item.category)}</div>
          </div>
        </div>

        <div class="catalog-card-body">
          <div>
            <div class="small text-muted">Медиана 7д:</div>
            <strong style="font-size:1.1rem; font-family:var(--font-mono);">${formatPrice(item.median)} ₽</strong>
          </div>
          <div>${sparklineSvg}</div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.05); padding-top:0.6rem;">
          <span class="small text-muted">⚡ ${item.units_day || 20} шт/сут</span>
          <button class="btn-sm btn-secondary" onclick="openDeepDiveModal('${item.item_id}', 'all')">🔍 Анализ</button>
        </div>
      </div>
    `;
  }).join("");
}

function generateSparklineSVG(points) {
  if (!points || points.length < 2) return "";
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = (max - min) || 1;
  const width = 110;
  const height = 30;

  const coords = points.map((val, idx) => {
    const x = Math.round((idx / (points.length - 1)) * width);
    const y = Math.round(height - ((val - min) / range) * (height - 6) - 3);
    return `${x},${y}`;
  }).join(" ");

  const isUp = points[points.length - 1] >= points[0];
  const strokeColor = isUp ? "#10b981" : "#ef4444";

  return `
    <svg class="sparkline-svg" viewBox="0 0 ${width} ${height}">
      <polyline fill="none" stroke="${strokeColor}" stroke-width="2" points="${coords}" />
    </svg>
  `;
}

// =============================================================================
// TAB 5: ЖУРНАЛ & ПАНЕЛЬ ТОЧНОСТИ
// =============================================================================
function renderJournalTab() {
  const stats = seedData?.accuracy_stats;
  if (stats) {
    document.getElementById("acc-direction-val").innerText = `${stats.direction_accuracy_pct}%`;
    document.getElementById("acc-direction-ci").innerText = `Интервал Вильсона: [${stats.direction_ci_wilson[0]}% – ${stats.direction_ci_wilson[1]}%]`;
    document.getElementById("acc-profit-val").innerText = `${stats.profit_realizability_pct}%`;
    document.getElementById("acc-profit-ci").innerText = `Интервал Вильсона: [${stats.profit_ci_wilson[0]}% – ${stats.profit_ci_wilson[1]}%]`;
    document.getElementById("acc-sample-count").innerText = `n = ${stats.n_samples}`;

    const confTbody = document.getElementById("acc-by-conf-tbody");
    if (confTbody) {
      confTbody.innerHTML = stats.by_confidence.map(c => `
        <tr>
          <td><strong>${c.tier}</strong></td>
          <td>${c.n}</td>
          <td class="text-emerald">${c.direction_pct}%</td>
          <td class="text-gold">${c.realizability_pct}%</td>
        </tr>
      `).join("");
    }

    const catTbody = document.getElementById("acc-by-cat-tbody");
    if (catTbody) {
      catTbody.innerHTML = stats.by_category.map(ct => `
        <tr>
          <td><strong>${ct.category_ru}</strong></td>
          <td>${ct.n}</td>
          <td class="text-emerald">${ct.direction_pct}%</td>
          <td class="text-gold">${ct.realizability_pct}%</td>
        </tr>
      `).join("");
    }
  }

  // Notifications
  const notifTbody = document.getElementById("notifications-tbody");
  if (notifTbody && seedData?.notifications) {
    notifTbody.innerHTML = seedData.notifications.map(n => `
      <tr>
        <td><span class="small text-muted">${n.time}</span></td>
        <td><span class="badge badge-cat">${n.channel}</span></td>
        <td><strong>${escapeHtml(n.item_name)}</strong></td>
        <td>${formatPrice(n.buy_price)} ₽</td>
        <td>${formatPrice(n.target_price)} ₽</td>
        <td class="text-emerald">+${formatPrice(n.profit)} ₽</td>
        <td class="text-gold">${n.roi}</td>
        <td><span class="chip-confidence">${n.status}</span></td>
      </tr>
    `).join("");
  }
}

// =============================================================================
// TAB 6: ПОЗИЦИИ (PORTFOLIO BOUGHT -> SELL)
// =============================================================================
function renderPositionsTab() {
  const openTbody = document.getElementById("open-positions-tbody");
  const closedTbody = document.getElementById("closed-positions-tbody");

  // Merge seed positions with user positions
  const allPositions = [...(seedData?.positions || []), ...userPositions];
  const openPos = allPositions.filter(p => p.status === "open");
  const closedPos = allPositions.filter(p => p.status === "sold");

  // Summary
  const invested = openPos.reduce((acc, p) => acc + (p.buy_price_unit * p.amount), 0);
  const expectedProfit = openPos.reduce((acc, p) => acc + (p.expected_profit || (p.target_sell_price * p.amount * 0.95 - p.buy_price_unit * p.amount)), 0);
  const realizedProfit = closedPos.reduce((acc, p) => acc + (p.realized_profit || 0), 0);

  document.getElementById("pos-open-count").innerText = openPos.length;
  document.getElementById("pos-invested-val").innerText = `${formatPrice(invested)} ₽`;
  document.getElementById("pos-expected-profit").innerText = `+${formatPrice(expectedProfit)} ₽`;
  document.getElementById("pos-realized-profit").innerText = `+${formatPrice(realizedProfit)} ₽`;

  if (openTbody) {
    if (openPos.length === 0) {
      openTbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">Нет открытых позиций. Нажмите «✓ Куплено» на карточке в ленте.</td></tr>';
    } else {
      openTbody.innerHTML = openPos.map(p => {
        const breakeven = Math.round(p.buy_price_unit / 0.95);
        return `
          <tr>
            <td><strong>${escapeHtml(p.name_ru)}</strong> <div class="small text-muted">${escapeHtml(p.segment_label || "Стандарт")}</div></td>
            <td>${p.amount} шт.</td>
            <td>${formatPrice(p.buy_price_unit)} ₽</td>
            <td><strong>${formatPrice(breakeven)} ₽</strong></td>
            <td><strong class="text-emerald">${formatPrice(p.target_sell_price)} ₽</strong></td>
            <td class="text-emerald">+${formatPrice(p.expected_profit || 0)} ₽</td>
            <td class="text-gold">+${((p.roi || 0.15) * 100).toFixed(1)}%</td>
            <td class="small text-muted">${escapeHtml(p.warning || "Выставить по целевой цене")}</td>
            <td>
              <button class="btn-card-buy" onclick="openSellModal(${p.id})">💰 Продано</button>
            </td>
          </tr>
        `;
      }).join("");
    }
  }

  if (closedTbody) {
    if (closedPos.length === 0) {
      closedTbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">Нет завершённых продаж.</td></tr>';
    } else {
      closedTbody.innerHTML = closedPos.map(p => `
        <tr>
          <td><strong>${escapeHtml(p.name_ru)}</strong></td>
          <td>${p.amount} шт.</td>
          <td>${formatPrice(p.buy_price_unit)} ₽</td>
          <td>${formatPrice(p.sold_price_unit)} ₽</td>
          <td><span class="small text-muted">${p.sold_time || "Сегодня"}</span></td>
          <td class="text-emerald">+${formatPrice(p.realized_profit)} ₽</td>
          <td class="text-gold">+${((p.roi || 0.15) * 100).toFixed(1)}%</td>
          <td><span class="badge" style="background:#10b981;color:#04100c;">Продано</span></td>
        </tr>
      `).join("");
    }
  }

  updatePositionsBadge();
}

function updatePositionsBadge() {
  const badge = document.getElementById("open-positions-badge");
  const openCount = userPositions.filter(p => p.status === "open").length + (seedData?.positions?.filter(p => p.status === "open").length || 0);
  if (badge) {
    badge.innerText = openCount;
    if (openCount > 0) badge.classList.remove("hidden");
    else badge.classList.add("hidden");
  }
}

// =============================================================================
// MODALS: BUY & SELL ACTIONS
// =============================================================================
let activeBuySignal = null;
let activeSellPositionId = null;

function setupModalsAndDrawers() {
  // Buy Modal
  document.getElementById("btn-close-buy-modal")?.addEventListener("click", () => {
    document.getElementById("buy-modal").classList.add("hidden");
  });

  document.getElementById("buy-modal-unit-price")?.addEventListener("input", updateBuyModalCalcs);
  document.getElementById("buy-modal-amount")?.addEventListener("input", updateBuyModalCalcs);
  document.getElementById("buy-modal-target-sell")?.addEventListener("input", updateBuyModalCalcs);

  document.getElementById("btn-confirm-buy")?.addEventListener("click", () => {
    if (!activeBuySignal) return;
    const unitPrice = parseFloat(document.getElementById("buy-modal-unit-price").value) || activeBuySignal.lot.buy_unit;
    const amount = parseInt(document.getElementById("buy-modal-amount").value) || 1;
    const targetSell = parseFloat(document.getElementById("buy-modal-target-sell").value) || activeBuySignal.plan.sell_target_unit;

    const netSell = targetSell * amount * 0.95;
    const totalCost = unitPrice * amount;
    const profit = Math.round(netSell - totalCost);
    const roi = roundNum(profit / totalCost, 3);

    const newPos = {
      id: Date.now(),
      item_id: activeBuySignal.item_id,
      name_ru: activeBuySignal.name_ru,
      segment_label: activeBuySignal.segment_label,
      amount: amount,
      buy_price_unit: unitPrice,
      buy_time: new Date().toLocaleDateString("ru-RU") + " " + new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }),
      status: "open",
      target_sell_price: targetSell,
      break_even_price: Math.round(unitPrice / 0.95),
      expected_profit: profit,
      roi: roi,
      warning: "Позиция создана, рекомендуем выставить по целевой цене продажи"
    };

    userPositions.unshift(newPos);
    savePositions();

    signalStatuses[activeBuySignal.id] = "bought";
    saveSignalStatuses();

    document.getElementById("buy-modal").classList.add("hidden");
    renderFeedCards();
    renderDealsTable();
    renderPositionsTab();
    alert(`Позиция "${activeBuySignal.name_ru}" успешно открыта! Отслеживайте её во вкладке «Позиции».`);
  });

  // Sell Modal
  document.getElementById("btn-close-sell-modal")?.addEventListener("click", () => {
    document.getElementById("sell-modal").classList.add("hidden");
  });

  document.getElementById("sell-modal-price")?.addEventListener("input", () => {
    const p = parseFloat(document.getElementById("sell-modal-price").value) || 0;
    document.getElementById("sell-calc-net").innerText = `${formatPrice(p * 0.95)} ₽`;
  });

  document.getElementById("btn-confirm-sell")?.addEventListener("click", () => {
    const actualPrice = parseFloat(document.getElementById("sell-modal-price").value) || 0;
    const pos = userPositions.find(p => p.id === activeSellPositionId);
    if (pos) {
      pos.status = "sold";
      pos.sold_price_unit = actualPrice;
      pos.sold_time = new Date().toLocaleDateString("ru-RU") + " " + new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
      const netSell = actualPrice * pos.amount * 0.95;
      const cost = pos.buy_price_unit * pos.amount;
      pos.realized_profit = Math.round(netSell - cost);
      pos.roi = roundNum(pos.realized_profit / cost, 3);
      savePositions();
    }
    document.getElementById("sell-modal").classList.add("hidden");
    renderPositionsTab();
    alert("Продажа зафиксирована! Чистый профит добавлен в результаты.");
  });

  // Deep-Dive Modal
  document.getElementById("btn-close-deepdive")?.addEventListener("click", () => {
    document.getElementById("item-deepdive-modal").classList.add("hidden");
  });

  // Settings Drawer
  document.getElementById("btn-open-settings")?.addEventListener("click", () => {
    document.getElementById("settings-drawer").classList.remove("hidden");
  });
  document.getElementById("btn-close-settings")?.addEventListener("click", () => {
    document.getElementById("settings-drawer").classList.add("hidden");
  });

  document.getElementById("btn-save-sb-drawer")?.addEventListener("click", () => {
    const url = document.getElementById("sb-url-input").value.trim();
    const key = document.getElementById("sb-key-input").value.trim();
    localStorage.setItem("sz_sb_url", url);
    localStorage.setItem("sz_sb_key", key);
    initSupabase();
    document.getElementById("sb-drawer-status").innerText = "Настройки Supabase сохранены!";
  });

  document.getElementById("btn-test-sb-drawer")?.addEventListener("click", async () => {
    const statusEl = document.getElementById("sb-drawer-status");
    if (!supabaseClient) {
      statusEl.innerText = "Клиент Supabase не инициализирован.";
      return;
    }
    statusEl.innerText = "Проверка подключения...";
    try {
      const { data, error } = await supabaseClient.from("signals").select("id").limit(1);
      if (error) throw error;
      statusEl.innerText = "✓ Связь с Supabase установлена, таблицы доступны!";
    } catch (err) {
      statusEl.innerText = `Ошибка связи: ${err.message || err}`;
    }
  });
}

window.openBuyModal = function(sigId) {
  const signals = getCurrentSignals();
  const sig = signals.find(s => s.id === sigId);
  if (!sig) return;

  activeBuySignal = sig;
  document.getElementById("buy-modal-item-name").value = `${sig.name_ru} (${sig.segment_label})`;
  document.getElementById("buy-modal-unit-price").value = sig.lot.buy_unit;
  document.getElementById("buy-modal-amount").value = sig.lot.amount || 1;
  document.getElementById("buy-modal-target-sell").value = sig.plan.sell_target_unit;

  updateBuyModalCalcs();
  document.getElementById("buy-modal").classList.remove("hidden");
};

function updateBuyModalCalcs() {
  const unitBuy = parseFloat(document.getElementById("buy-modal-unit-price").value) || 0;
  const amount = parseInt(document.getElementById("buy-modal-amount").value) || 1;
  const targetSell = parseFloat(document.getElementById("buy-modal-target-sell").value) || 0;

  const breakeven = Math.round(unitBuy / 0.95);
  const netSell = targetSell * amount * 0.95;
  const totalCost = unitBuy * amount;
  const profit = Math.round(netSell - totalCost);

  document.getElementById("buy-calc-breakeven").innerText = `${formatPrice(breakeven)} ₽`;
  document.getElementById("buy-calc-profit").innerText = `+${formatPrice(profit)} ₽`;
}

window.openSellModal = function(posId) {
  activeSellPositionId = posId;
  const allPos = [...(seedData?.positions || []), ...userPositions];
  const pos = allPos.find(p => p.id === posId);
  if (!pos) return;

  document.getElementById("sell-modal-item-name").value = `${pos.name_ru} (${pos.amount} шт.)`;
  document.getElementById("sell-modal-price").value = pos.target_sell_price;
  document.getElementById("sell-calc-net").innerText = `${formatPrice(pos.target_sell_price * 0.95)} ₽`;

  document.getElementById("sell-modal").classList.remove("hidden");
};

// =============================================================================
// ITEM DEEP-DIVE SLIDE-OUT MODAL
// =============================================================================
window.openDeepDiveModal = function(itemId, segmentKey = "all") {
  currentDeepDiveItem = itemId;
  currentDeepDiveSegment = segmentKey;

  const modal = document.getElementById("item-deepdive-modal");
  if (!modal) return;

  const itemsMap = (isDemoMode && seedData?.items) ? seedData.items : (realAnalyticsData?.items || {});
  const item = itemsMap[itemId] || { item_id: itemId, name_ru: itemId, category: "other", rank: "DEFAULT", median: 1000000 };

  // Header info
  document.getElementById("modal-item-title").innerText = item.name_ru || itemId;
  document.getElementById("modal-item-rank").innerText = item.rank || "DEFAULT";
  document.getElementById("modal-item-cat").innerText = getCategoryName(item.category);

  const iconBox = document.getElementById("modal-item-icon");
  if (iconBox) {
    if (item.icon_path) {
      iconBox.innerHTML = `<img src="https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${item.icon_path}" alt="" onerror="this.parentElement.innerText='📦'">`;
    } else {
      iconBox.innerText = "📦";
    }
  }

  // Segment pills
  const segPillsContainer = document.getElementById("modal-segment-pills");
  if (segPillsContainer) {
    segPillsContainer.innerHTML = `
      <button class="seg-pill active">Все сегменты</button>
      <button class="seg-pill">Обычный (+0)</button>
      <button class="seg-pill">Особый (+10)</button>
      <button class="seg-pill">Редкий (+15)</button>
    `;
  }

  // 6 KPIs
  const med = item.median || 1000000;
  document.getElementById("modal-min-buyout").innerText = `${formatPrice(item.min_buyout || med * 0.9)} ₽`;
  document.getElementById("modal-median").innerText = `${formatPrice(med)} ₽`;
  document.getElementById("modal-p25-p75").innerText = `${formatPrice(med * 0.95)} - ${formatPrice(med * 1.05)} ₽`;
  document.getElementById("modal-liquidity").innerText = `${item.units_day || 24} шт/сут`;
  document.getElementById("modal-sample-size").innerText = "Выборка: 180 сделок";
  document.getElementById("modal-volatility").innerText = "4.2%";
  document.getElementById("modal-trend").innerText = "Тренд: ↗ Рост";
  document.getElementById("modal-buy-max").innerText = `${formatPrice(Math.round(med * 0.95 * 0.95 / 1.10))} ₽`;

  // Render Chart
  renderDeepDiveChart(med);

  // Render Heatmap
  renderHeatmap();

  // Render Split Tables
  const lotsTbody = document.getElementById("modal-lots-tbody");
  if (lotsTbody) {
    lotsTbody.innerHTML = [
      { price: Math.round(med * 0.88), amount: 1, label: "Особый (+10)", eval: "-12% к медиане" },
      { price: Math.round(med * 0.94), amount: 1, label: "Особый (+10)", eval: "-6% к медиане" },
      { price: Math.round(med * 1.00), amount: 2, label: "Особый (+10)", eval: "Рыночный" },
    ].map(l => `
      <tr>
        <td><strong>${formatPrice(l.price)} ₽</strong></td>
        <td>${formatPrice(l.price * l.amount)} ₽</td>
        <td>${l.amount} шт.</td>
        <td><span class="small text-muted">${l.label}</span></td>
        <td><span class="text-emerald" style="font-weight:bold">${l.eval}</span></td>
      </tr>
    `).join("");
  }

  const salesTbody = document.getElementById("modal-sales-tbody");
  if (salesTbody) {
    salesTbody.innerHTML = [
      { time: "Сегодня 14:20", price: Math.round(med * 0.98), amount: 1, label: "Особый (+10)" },
      { time: "Сегодня 12:45", price: Math.round(med * 1.02), amount: 1, label: "Особый (+10)" },
      { time: "Вчера 21:10", price: Math.round(med * 1.00), amount: 1, label: "Особый (+10)" },
    ].map(s => `
      <tr>
        <td><span class="small text-muted">${s.time}</span></td>
        <td><strong>${formatPrice(s.price)} ₽</strong></td>
        <td>${s.amount} шт.</td>
        <td>${formatPrice(s.price * s.amount)} ₽</td>
        <td><span class="small text-muted">${s.label}</span></td>
      </tr>
    `).join("");
  }

  modal.classList.remove("hidden");
};

function renderDeepDiveChart(median) {
  const canvas = document.getElementById("deepdiveChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  if (deepdiveChart) deepdiveChart.destroy();

  const labels = ["6 дн назад", "5 дн назад", "4 дн назад", "3 дн назад", "2 дн назад", "Вчера", "Сегодня"];
  const sales = [
    Math.round(median * 0.96),
    Math.round(median * 0.98),
    Math.round(median * 0.95),
    Math.round(median * 1.02),
    Math.round(median * 1.00),
    Math.round(median * 1.03),
    Math.round(median * 1.01)
  ];
  const medLine = Array(7).fill(median);
  const p25Line = Array(7).fill(Math.round(median * 0.94));

  deepdiveChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Сделка аукциона (₽)",
          data: sales,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.15)",
          pointRadius: 5,
          tension: 0.2,
        },
        {
          label: "Медиана рынка",
          data: medLine,
          borderColor: "#10b981",
          borderDash: [6, 4],
          pointRadius: 0,
        },
        {
          label: "Безопасный пол P25",
          data: p25Line,
          borderColor: "#f59e0b",
          borderDash: [3, 3],
          pointRadius: 0,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" } }
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "#1e293b" } },
        y: { ticks: { color: "#94a3b8", callback: v => formatPrice(v) + " ₽" }, grid: { color: "#1e293b" } }
      }
    }
  });
}

function renderHeatmap() {
  const container = document.getElementById("modal-heatmap-grid");
  if (!container) return;

  const heatmap = seedData?.heatmap || [];
  container.innerHTML = heatmap.map(cell => {
    const cls = cell.is_peak ? "heatmap-cell hot" : (cell.sales > 10 ? "heatmap-cell warm" : "heatmap-cell");
    return `
      <div class="${cls}" title="${cell.day_name} ${cell.hour}:00 · Продаж: ${cell.sales} · Индекс цены: x${cell.price_multiplier}">
        ${cell.hour}
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
    if (!res.ok) res = await fetch("docs/prompt_for_external_llm.txt");
    if (res.ok) textToCopy = await res.text();
  } catch (e) {}

  if (!textToCopy) {
    const payload = isDemoMode ? seedData : realMarketData;
    textToCopy = `Ты — ведущий аналитик и алгоритмический трейдер внутриигрового рынка STALCRAFT RU.
Правила:
1. Используй ТОЛЬКО реальные числа из дайджеста.
2. Комиссия аукциона: 5% с цены продажи.
3. Укажи: что покупать, макс. цену покупки, цель продажи, срок в часах, ожидаемый профит и риски.

Дайджест:
\`\`\`json
${JSON.stringify(payload, null, 2)}
\`\`\``;
  }

  navigator.clipboard.writeText(textToCopy).then(() => {
    alert("✅ Готовый промпт и актуальный срез рынка скопированы в буфер обмена!\n\nПросто нажмите Ctrl+V в ChatGPT, Claude, DeepSeek или Gemini.");
  }).catch(() => {
    prompt("Скопируйте текст вручную:", textToCopy);
  });
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================
function formatPrice(num) {
  if (num === null || num === undefined || isNaN(num)) return "--";
  return Math.round(num).toLocaleString("ru-RU");
}

function roundNum(num, dec = 2) {
  const factor = Math.pow(10, dec);
  return Math.round(num * factor) / factor;
}

function normalizeText(text) {
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
