/**
 * STALCRAFT Market Dashboard - Client Application
 * Adheres strictly to Patch 2 (Names only, no item IDs exposed in UI).
 */

let marketData = null;
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
let priceChart = null;
let activeCatFilter = "";

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupThemeToggle();
  setupFilters();
  setupCatalogSearch();
  setupWatchlistControls();
  loadData();
  loadCatalog();

  document.getElementById("btn-refresh").addEventListener("click", loadData);
  document.getElementById("btn-item-lookup").addEventListener("click", updateItemView);
  document.getElementById("btn-copy-llm").addEventListener("click", copyPromptForLLM);
});

function setupTabs() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      document.getElementById(tabId).classList.add("active");

      if (tabId === "tab-item" && !priceChart) {
        initPriceChart();
      }
    });
  });
}

function setupThemeToggle() {
  const toggleBtn = document.getElementById("theme-toggle");
  toggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("theme-light");
    document.body.classList.toggle("theme-dark");
  });
}

function setupFilters() {
  document.getElementById("signal-search").addEventListener("input", renderSignals);
  document.getElementById("filter-roi").addEventListener("change", renderSignals);
  document.getElementById("filter-conf").addEventListener("change", renderSignals);
  document.getElementById("sort-signals").addEventListener("change", renderSignals);
}

function normalizeSearch(text) {
  if (!text) return "";
  return text.toLowerCase()
    .replace(/ё/g, "е")
    .replace(/["«»„“',.\-_/\\()\[\]]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function loadCatalog() {
  try {
    const res = await fetch("catalog.json");
    if (res.ok) {
      catalogItems = await res.json();
    }
  } catch (e) {
    console.warn("Could not load catalog.json:", e);
  }
}

function setupCatalogSearch() {
  const input = document.getElementById("catalog-search-input");
  input.addEventListener("input", () => {
    renderCatalogResults(input.value);
  });

  document.querySelectorAll(".cat-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeCatFilter = pill.getAttribute("data-cat");
      renderCatalogResults(input.value);
    });
  });
}

function renderCatalogResults(rawQuery) {
  const container = document.getElementById("catalog-results-container");
  const query = normalizeSearch(rawQuery);

  if (!query && !activeCatFilter) {
    container.innerHTML = '<div class="empty-hint text-muted">Введите название для поиска предметов из каталога...</div>';
    return;
  }

  let results = catalogItems.filter(item => {
    if (activeCatFilter && !(item.category || "").includes(activeCatFilter)) {
      return false;
    }
    if (!query) return true;
    const normName = normalizeSearch(`${item.name_ru} ${item.name_en}`);
    return normName.includes(query);
  });

  if (results.length === 0) {
    container.innerHTML = '<div class="empty-hint text-muted">Ничего не найдено. Проверьте написание. Возможно, предмета нет в базе EXBO.</div>';
    return;
  }

  container.innerHTML = results.slice(0, 30).map(item => {
    const iconUrl = item.icon_path
      ? `https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main/ru${item.icon_path}`
      : "";

    return `
      <div class="catalog-item-card">
        <div class="card-icon">
          ${iconUrl ? `<img src="${iconUrl}" alt="" onerror="this.style.display='none'">` : "📦"}
        </div>
        <div class="card-info">
          <div class="card-title">${escapeHtml(item.name_ru || item.name_en)}</div>
          <div class="card-meta">
            <span class="rank-badge ${item.rank}">${formatRank(item.rank)}</span>
            <span class="cat-label">${item.category}</span>
            ${item.source === "manual_override" ? '<span class="override-pill">Добавлено вручную</span>' : ""}
          </div>
        </div>
        <button class="btn-track btn-secondary" onclick="addToWatchlist('${item.item_id}', '${escapeHtml(item.name_ru)}')">+ Отслеживать</button>
      </div>
    `;
  }).join("");
}

window.addToWatchlist = function(itemId, nameRu) {
  const item = catalogItems.find(i => i.item_id === itemId);
  watchlist.push({
    item_id: itemId,
    name_ru: nameRu,
    category: item?.category || "general",
    rank: item?.rank || "DEFAULT",
    enabled: true,
    min_roi: 0.10,
    min_profit: 25000,
    filters: {}
  });
  renderWatchlist();
  alert(`"${nameRu}" добавлен в список отслеживания!`);
};

function setupWatchlistControls() {
  document.getElementById("btn-export-wl").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(watchlist, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "watchlist.json";
    a.click();
  });

  document.getElementById("btn-import-wl").addEventListener("click", () => {
    const jsonStr = prompt("Вставьте JSON списка отслеживания:");
    if (jsonStr) {
      try {
        const parsed = JSON.parse(jsonStr);
        if (Array.isArray(parsed)) {
          watchlist = parsed;
          renderWatchlist();
          alert("Список отслеживания успешно импортирован!");
        }
      } catch (e) {
        alert("Неверный формат JSON");
      }
    }
  });

  renderWatchlist();
}

function renderWatchlist() {
  const tbody = document.getElementById("watchlist-tbody");
  if (!tbody) return;

  if (watchlist.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Список отслеживания пуст. Добавьте предметы из каталога.</td></tr>';
    return;
  }

  tbody.innerHTML = watchlist.map((item, idx) => {
    return `
      <tr>
        <td><strong>${escapeHtml(item.name_ru)}</strong></td>
        <td><span class="cat-label">${escapeHtml(item.category)}</span></td>
        <td><span class="status-pill ${item.enabled ? 'active' : 'paused'}">${item.enabled ? 'Активен' : 'Пауза'}</span></td>
        <td>${((item.min_roi || 0.10) * 100).toFixed(0)}%</td>
        <td>${(item.min_profit || 25000).toLocaleString("ru-RU")} ₽</td>
        <td>
          <button class="btn-sm btn-secondary" onclick="toggleWatchlist(${idx})">${item.enabled ? 'Пауза' : 'Вкл'}</button>
          <button class="btn-sm btn-danger" onclick="removeWatchlist(${idx})">Удалить</button>
        </td>
      </tr>
    `;
  }).join("");
}

window.toggleWatchlist = function(index) {
  if (watchlist[index]) {
    watchlist[index].enabled = !watchlist[index].enabled;
    renderWatchlist();
  }
};

window.removeWatchlist = function(index) {
  if (confirm(`Удалить "${watchlist[index]?.name_ru}" из отслеживания?`)) {
    watchlist.splice(index, 1);
    renderWatchlist();
  }
};

async function loadData() {
  const statusText = document.getElementById("data-status-text");
  statusText.innerText = "Обновление данных...";

  try {
    let res = await fetch("digest.json");
    if (!res.ok) {
      res = await fetch("../data/digest.json");
    }
    if (!res.ok) {
      res = await fetch("data/digest.json");
    }
    if (!res.ok) throw new Error("digest.json not found");
    marketData = await res.json();
    statusText.innerText = "Рынок синхронизирован";
    document.getElementById("data-age").innerText = `Возраст данных: ${marketData.data_freshness_minutes || 10} мин`;
    document.getElementById("current-region").innerText = marketData.region || "RU";
    document.getElementById("config-json-display").innerText = JSON.stringify(marketData.config, null, 2);

    renderSignals();
  } catch (e) {
    statusText.innerText = "Режим ожидания (демо-данные)";
    renderDummyData();
  }
}

function renderSignals() {
  const tbody = document.getElementById("signals-tbody");
  if (!marketData || !marketData.top_opportunities) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Нет активных сигналов</td></tr>';
    return;
  }

  const query = normalizeSearch(document.getElementById("signal-search").value);
  const minRoi = parseFloat(document.getElementById("filter-roi").value) || 0;
  const minConf = parseFloat(document.getElementById("filter-conf").value) || 0;
  const sortBy = document.getElementById("sort-signals").value;

  let list = marketData.top_opportunities.filter(opp => {
    const nameMatch = normalizeSearch(opp.name_ru || "").includes(query);
    const roiMatch = (opp.plan?.roi || 0) >= minRoi;
    const confMatch = (opp.confidence || 0) >= minConf;
    return nameMatch && roiMatch && confMatch;
  });

  list.sort((a, b) => {
    if (sortBy === "profit") return (b.plan?.expected_profit || 0) - (a.plan?.expected_profit || 0);
    if (sortBy === "roi") return (b.plan?.roi || 0) - (a.plan?.roi || 0);
    if (sortBy === "confidence") return (b.confidence || 0) - (a.confidence || 0);
    if (sortBy === "days") return (a.liquidity?.days_to_sell_est || 0) - (b.liquidity?.days_to_sell_est || 0);
    return 0;
  });

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Подходящих сигналов по выбранным фильтрам не найдено</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(opp => {
    const confClass = opp.confidence >= 0.75 ? "conf-high" : "conf-mid";
    const reasonsHtml = (opp.reasons || []).map(r => `<div>• ${escapeHtml(r)}</div>`).join("");

    return `
      <tr>
        <td>
          <strong>${escapeHtml(opp.name_ru || "Предмет")}</strong>
          <div class="small text-muted">${escapeHtml(opp.segment_label || opp.segment || "Стандарт")}</div>
        </td>
        <td>${formatPrice(opp.lot?.buy_unit)} ₽</td>
        <td>${formatPrice(opp.plan?.sell_target_unit)} ₽</td>
        <td class="profit-badge">+${formatPrice(opp.plan?.expected_profit)} ₽</td>
        <td>${((opp.plan?.roi || 0) * 100).toFixed(1)}%</td>
        <td>~${opp.liquidity?.days_to_sell_est || 1} дн.</td>
        <td><span class="confidence-bar ${confClass}">${Math.round((opp.confidence || 0) * 100)}%</span></td>
        <td class="reasons-tooltip">${reasonsHtml}</td>
      </tr>
    `;
  }).join("");
}

function initPriceChart() {
  const ctx = document.getElementById("priceChart").getContext("2d");
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["6 дн назад", "5 дн назад", "4 дн назад", "3 дн назад", "2 дн назад", "Вчера", "Сегодня"],
      datasets: [
        {
          label: "Медианная цена продажи",
          data: [280000, 290000, 285000, 295000, 310000, 305000, 315000],
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          fill: true,
          tension: 0.3,
        },
        {
          label: "P25 (Пессимистичный floor)",
          data: [260000, 265000, 260000, 270000, 280000, 280000, 285000],
          borderColor: "#94a3b8",
          borderDash: [5, 5],
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#94a3b8" } } },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } }
      }
    }
  });
}

function updateItemView() {
  document.getElementById("metric-median").innerText = "305,000 ₽";
  document.getElementById("metric-p25-p75").innerText = "280k - 330k ₽";
  document.getElementById("metric-liquidity").innerText = "18.5 шт/сут";
  document.getElementById("metric-volatility").innerText = "7.8%";
  if (priceChart) priceChart.update();
}

function renderDummyData() {
  marketData = {
    region: "RU",
    data_freshness_minutes: 10,
    config: { auction_fee_rate: 0.05, listing_fee: 0, capital: 10000000, min_roi: 0.10 },
    top_opportunities: [
      {
        item_id: "1pyq",
        name_ru: "Фокусный Уходящий «Снайпер»",
        segment: "1pyq:aiming_speed_modifier_pre:recoil_suf:marksman:q1",
        lot: { buy_unit: 210000 },
        fair: { median_3d: 310000, p25_3d: 285000, p75_3d: 340000 },
        liquidity: { units_per_day: 12.0, days_to_sell_est: 1.2 },
        plan: { buy_max_unit: 260000, sell_target_unit: 310000, sell_floor_unit: 285000, expected_profit: 84500, roi: 0.402 },
        confidence: 0.82,
        reasons: ["Покупка 210k против медианы 3д 310k (n=45)", "Ликвидность 12 шт/сут", "ROI 40.2% с учётом комиссии 5%"],
        caveats: ["Задержка данных ~10 мин"],
      }
    ]
  };
  renderSignals();
  document.getElementById("config-json-display").innerText = JSON.stringify(marketData.config, null, 2);
}

function formatPrice(num) {
  if (num === null || num === undefined) return "--";
  return Math.round(num).toLocaleString("ru-RU");
}

function formatRank(rank) {
  if (!rank) return "";
  return rank.replace("RANK_", "");
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

async function copyPromptForLLM() {
  let textToCopy = "";
  try {
    const res = await fetch("../data/prompt_for_external_llm.txt");
    if (res.ok) {
      textToCopy = await res.text();
    }
  } catch (e) {
    console.warn("Could not fetch prompt_for_external_llm.txt directly:", e);
  }

  if (!textToCopy && marketData) {
    textToCopy = `Ты — аналитик внутриигрового рынка STALCRAFT.
Правила:
1. Используй ТОЛЬКО числа из дайджеста. Все цены за штуку.
2. Комиссия аукциона: 5% с цены продажи.
3. Укажи: что покупать, макс. цену покупки, цель продажи, срок в часах, ожидаемый профит и риски.

Дайджест:
\`\`\`json
${JSON.stringify(marketData, null, 2)}
\`\`\``;
  }

  if (textToCopy) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      alert("✅ Готовый промпт и актуальный дайджест рынка скопированы в буфер обмена!\n\nПросто вставьте (Ctrl+V) в ChatGPT, Claude, DeepSeek или Gemini.");
    }).catch(err => {
      prompt("Скопируйте текст вручную:", textToCopy);
    });
  } else {
    alert("Данные дайджеста ещё не сформированы. Запустите сборщик данных.");
  }
}
