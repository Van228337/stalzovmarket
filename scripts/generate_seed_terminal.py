import json
import random
from datetime import datetime, timezone, timedelta

def generate_seed():
    now = datetime.now(timezone.utc)

    # 25 Diverse items across all categories and rarities
    items_meta = [
        # Artefacts
        {"item_id": "wg53", "name_ru": "Атом", "category": "artefact/electrophysical", "rank": "RANK_MASTER", "qlt": 2, "ptn": 10, "icon_path": "/icons/artefacts/wg53.png", "median": 2400000, "units_day": 28.5},
        {"item_id": "gyq5", "name_ru": "Спираль", "category": "artefact/electrophysical", "rank": "RANK_MASTER", "qlt": 3, "ptn": 15, "icon_path": "/icons/artefacts/gyq5.png", "median": 8500000, "units_day": 14.2},
        {"item_id": "5rwq", "name_ru": "Осколок", "category": "artefact/electrophysical", "rank": "RANK_MASTER", "qlt": 1, "ptn": 5, "icon_path": "/icons/artefacts/5rwq.png", "median": 750000, "units_day": 34.0},
        {"item_id": "qoq6", "name_ru": "Солнце", "category": "artefact/thermal", "rank": "RANK_MASTER", "qlt": 4, "ptn": 15, "icon_path": "/icons/artefacts/qoq6.png", "median": 14200000, "units_day": 8.1},
        {"item_id": "y5w3", "name_ru": "Призма", "category": "artefact/electrophysical", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/artefacts/y5w3.png", "median": 310000, "units_day": 42.0},
        {"item_id": "k3lo", "name_ru": "Глаз", "category": "artefact/thermal", "rank": "RANK_VETERAN", "qlt": 2, "ptn": 0, "icon_path": "/icons/artefacts/k3lo.png", "median": 450000, "units_day": 19.5},
        {"item_id": "m9pa", "name_ru": "Трансформатор", "category": "artefact/electrophysical", "rank": "RANK_MASTER", "qlt": 5, "ptn": 15, "icon_path": "/icons/artefacts/m9pa.png", "median": 26500000, "units_day": 3.4},
        {"item_id": "d4wq", "name_ru": "Браслет", "category": "artefact/gravity", "rank": "RANK_STALKER", "qlt": 0, "ptn": 0, "icon_path": "/icons/artefacts/d4wq.png", "median": 85000, "units_day": 65.0},
        
        # Containers
        {"item_id": "g35n", "name_ru": "Контейнер «Берлога-6»", "category": "containers", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/containers/g35n.png", "median": 4200000, "units_day": 16.0},
        {"item_id": "j3ml", "name_ru": "Контейнер «КСМ»", "category": "containers", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/containers/j3ml.png", "median": 5800000, "units_day": 11.2},
        {"item_id": "b4pk", "name_ru": "Контейнер «Берлога-4»", "category": "containers", "rank": "RANK_VETERAN", "qlt": 0, "ptn": 0, "icon_path": "/icons/containers/b4pk.png", "median": 1650000, "units_day": 24.0},
        {"item_id": "u8lo", "name_ru": "Улей", "category": "containers", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/containers/u8lo.png", "median": 9800000, "units_day": 9.5},

        # Materials & Tools
        {"item_id": "y3nmw", "name_ru": "Продвинутые запчасти", "category": "other", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/other/y3nmw.png", "median": 44500, "units_day": 260.0},
        {"item_id": "4q7pl", "name_ru": "Продвинутые инструменты", "category": "other", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/other/4q7pl.png", "median": 68000, "units_day": 190.0},
        {"item_id": "l0og1", "name_ru": "Стандартные запчасти", "category": "other", "rank": "RANK_STALKER", "qlt": 0, "ptn": 0, "icon_path": "/icons/other/l0og1.png", "median": 12500, "units_day": 450.0},
        {"item_id": "zzwmm", "name_ru": "Сыворотка изменения", "category": "other", "rank": "RANK_VETERAN", "qlt": 0, "ptn": 0, "icon_path": "/icons/other/zzwmm.png", "median": 185000, "units_day": 85.0},
        {"item_id": "m1tk", "name_ru": "Катализатор аномалий", "category": "other", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/other/m1tk.png", "median": 95000, "units_day": 120.0},

        # Weapons & Armor
        {"item_id": "w1fn", "name_ru": "FN F2000 Тактический", "category": "weapon/assault_rifle", "rank": "RANK_MASTER", "qlt": 0, "ptn": 10, "icon_path": "/icons/weapon/w1fn.png", "median": 18500000, "units_day": 4.5},
        {"item_id": "a3sk", "name_ru": "Скат-10", "category": "armor/combined", "rank": "RANK_MASTER", "qlt": 0, "ptn": 15, "icon_path": "/icons/armor/a3sk.png", "median": 34000000, "units_day": 2.1},
        {"item_id": "v5pr", "name_ru": "ВСС «Винторез»", "category": "weapon/sniper_rifle", "rank": "RANK_VETERAN", "qlt": 0, "ptn": 5, "icon_path": "/icons/weapon/v5pr.png", "median": 3900000, "units_day": 15.0},
        {"item_id": "c2cb", "name_ru": "Центурион", "category": "armor/combat", "rank": "RANK_MASTER", "qlt": 0, "ptn": 10, "icon_path": "/icons/armor/c2cb.png", "median": 22000000, "units_day": 3.8},
        {"item_id": "k8ak", "name_ru": "АК-15", "category": "weapon/assault_rifle", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/weapon/k8ak.png", "median": 7200000, "units_day": 18.0},
        {"item_id": "s9sh", "name_ru": "Protecta", "category": "weapon/shotgun_rifle", "rank": "RANK_STALKER", "qlt": 0, "ptn": 0, "icon_path": "/icons/weapon/s9sh.png", "median": 890000, "units_day": 22.0},
        {"item_id": "b1pk", "name_ru": "Рюкзак «Десантник»", "category": "backpacks", "rank": "RANK_VETERAN", "qlt": 0, "ptn": 0, "icon_path": "/icons/backpacks/b1pk.png", "median": 520000, "units_day": 35.0},
        {"item_id": "m4bg", "name_ru": "Магазин 60 патронов 5.45", "category": "attachment/mag", "rank": "RANK_MASTER", "qlt": 0, "ptn": 0, "icon_path": "/icons/attachment/m4bg.png", "median": 1450000, "units_day": 27.0},
    ]

    rarity_names = {
        0: "Обычный",
        1: "Необычный",
        2: "Особый",
        3: "Редкий",
        4: "Исключительный",
        5: "Легендарный",
        6: "Уникальный",
    }

    # Generate 42 Signals
    signals = []
    for i in range(42):
        item = items_meta[i % len(items_meta)]
        median = item["median"]
        discount_pct = round(random.uniform(0.12, 0.38), 3)
        buy_unit = int(median * (1.0 - discount_pct))
        # Ensure clean numbers
        buy_unit = round(buy_unit, -3) if buy_unit > 50000 else round(buy_unit, -1)
        sell_target = int(median * 0.98)
        amount = random.choice([1, 1, 1, 2, 5, 10]) if item["category"] == "other" else 1
        
        # After 5% fee
        fee = sell_target * amount * 0.05
        net_revenue = (sell_target * amount) - fee
        total_cost = buy_unit * amount
        expected_profit = int(net_revenue - total_cost)
        roi = round(expected_profit / total_cost, 3)

        conf = round(random.uniform(0.62, 0.94), 2)
        qlt = item.get("qlt", 0)
        ptn = item.get("ptn", 0)

        seg_label = f"{rarity_names[qlt]} (+{ptn})" if "artefact" in item["category"] else ("Заточка +10" if ptn > 0 else "Стандарт")
        seg_key = f"q{qlt}:p{ptn}" if "artefact" in item["category"] else "default"

        minutes_ago = random.randint(1, 45)
        created_time = (now - timedelta(minutes=minutes_ago)).isoformat()
        hours_left = random.randint(2, 23)
        minutes_left = random.randint(5, 58)

        reasons = [
            f"Выкуп за {buy_unit:,} ₽ при медиане {median:,} ₽ (дисконт {int(discount_pct*100)}%)".replace(",", " "),
            f"Высокий суточный спрос: ~{item['units_day']} шт/сут на RU сервере",
            f"Чистая маржа с учётом комиссии аукциона 5%: +{expected_profit:,} ₽".replace(",", " "),
            f"Слабое давление предложения: в стакане всего {random.randint(4, 25)} конкурентных лотов"
        ]

        caveats = [
            f"Задержка данных API EXBO ~10 минут — проверьте наличие лота в игре",
            f"Комиссия аукциона 5% вычитается автоматически при получении денег на почту"
        ]

        signals.append({
            "id": 1000 + i,
            "item_id": item["item_id"],
            "name_ru": item["name_ru"],
            "category": item["category"],
            "rank": item["rank"],
            "icon_path": item["icon_path"],
            "qlt": qlt,
            "ptn": ptn,
            "segment_key": seg_key,
            "segment_label": seg_label,
            "lot": {
                "buy_unit": buy_unit,
                "amount": amount,
                "total_buyout": buy_unit * amount,
            },
            "plan": {
                "sell_target_unit": sell_target,
                "sell_floor_unit": int(median * 0.92),
                "expected_profit": expected_profit,
                "roi": roi,
            },
            "fair": {
                "median_3d": median,
                "p25_3d": int(median * 0.94),
                "p75_3d": int(median * 1.06),
            },
            "discount_pct": round(discount_pct * 100, 1),
            "confidence": conf,
            "confidence_label": "Смело" if conf >= 0.75 else ("Осторожно" if conf >= 0.60 else "Рискованно"),
            "orderbook_depth": random.randint(3, 48),
            "sales_3d": int(item["units_day"] * 3),
            "created_at_human": f"{minutes_ago} мин назад",
            "time_left_human": f"{hours_left}ч {minutes_left}м",
            "is_new": minutes_ago <= 15,
            "reasons": reasons,
            "caveats": caveats,
            "status": "new",
        })

    # Sort signals by expected profit desc
    signals.sort(key=lambda s: s["plan"]["expected_profit"], reverse=True)

    # Generate 5 Open Positions & 4 Closed Positions
    positions = [
        {
            "id": 1,
            "item_id": "wg53",
            "name_ru": "Атом",
            "segment_label": "Особый (+10)",
            "amount": 1,
            "buy_price_unit": 1850000,
            "buy_time": (now - timedelta(hours=3, minutes=20)).strftime("%d.%m %H:%M"),
            "status": "open",
            "target_sell_price": 2350000,
            "break_even_price": 1947368,
            "expected_profit": 382500,
            "roi": 0.207,
            "warning": "Рынок стабилен, рекомендация: выставить в пиковый час (19:00 - 22:00)"
        },
        {
            "id": 2,
            "item_id": "y3nmw",
            "name_ru": "Продвинутые запчасти",
            "segment_label": "Стандарт",
            "amount": 25,
            "buy_price_unit": 38000,
            "buy_time": (now - timedelta(hours=5)).strftime("%d.%m %H:%M"),
            "status": "open",
            "target_sell_price": 44000,
            "break_even_price": 40000,
            "expected_profit": 95000,
            "roi": 0.100,
            "warning": "Ликвидность высокая (260 шт/сут), уйдет за 30-60 минут"
        },
        {
            "id": 3,
            "item_id": "g35n",
            "name_ru": "Контейнер «Берлога-6»",
            "segment_label": "Стандарт",
            "amount": 1,
            "buy_price_unit": 3400000,
            "buy_time": (now - timedelta(hours=8)).strftime("%d.%m %H:%M"),
            "status": "open",
            "target_sell_price": 4150000,
            "break_even_price": 3578947,
            "expected_profit": 542500,
            "roi": 0.159,
            "warning": "Конкуренция низкая, держите целевую цену"
        },
        {
            "id": 4,
            "item_id": "gyq5",
            "name_ru": "Спираль",
            "segment_label": "Редкий (+15)",
            "amount": 1,
            "buy_price_unit": 6200000,
            "buy_time": (now - timedelta(days=1, hours=2)).strftime("%d.%m %H:%M"),
            "status": "sold",
            "sold_price_unit": 8300000,
            "sold_time": (now - timedelta(hours=2)).strftime("%d.%m %H:%M"),
            "realized_profit": 1685000,
            "roi": 0.272,
        },
        {
            "id": 5,
            "item_id": "4q7pl",
            "name_ru": "Продвинутые инструменты",
            "segment_label": "Стандарт",
            "amount": 15,
            "buy_price_unit": 56000,
            "buy_time": (now - timedelta(days=2)).strftime("%d.%m %H:%M"),
            "status": "sold",
            "sold_price_unit": 67500,
            "sold_time": (now - timedelta(days=1)).strftime("%d.%m %H:%M"),
            "realized_profit": 121875,
            "roi": 0.145,
        }
    ]

    # Signal Accuracy Panel Statistics (Patch 3 Section 8)
    accuracy_stats = {
        "n_samples": 148,
        "horizon_default": "24h",
        "direction_accuracy_pct": 89.2,
        "direction_ci_wilson": [83.1, 93.3],
        "profit_realizability_pct": 82.4,
        "profit_ci_wilson": [75.5, 87.6],
        "last_7d": {
            "n": 42,
            "direction_accuracy_pct": 92.8,
            "profit_realizability_pct": 85.7,
        },
        "by_confidence": [
            {"tier": "Смело (≥70)", "n": 86, "direction_pct": 94.2, "realizability_pct": 89.5},
            {"tier": "Осторожно (40-69)", "n": 48, "direction_pct": 83.3, "realizability_pct": 72.9},
            {"tier": "Рискованно (<40)", "n": 14, "direction_pct": 71.4, "realizability_pct": 57.1},
        ],
        "by_category": [
            {"category_ru": "Артефакты", "n": 56, "direction_pct": 91.1, "realizability_pct": 83.9},
            {"category_ru": "Материалы и запчасти", "n": 62, "direction_pct": 95.2, "realizability_pct": 91.9},
            {"category_ru": "Контейнеры", "n": 30, "direction_pct": 76.7, "realizability_pct": 66.7},
        ],
        "disclaimer": "Точность рассчитывается по фактическим закрытым сделкам аукциона за указанный горизонт (24ч). Не является финансовой гарантией."
    }

    # Best hour heatmap (Day of week x Hour)
    hour_stats_heatmap = []
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for d_idx, day_name in enumerate(days):
        for h in range(24):
            # Peak activity between 18:00 and 23:00 on weekdays, whole day on weekends
            is_peak = (h >= 18 and h <= 23) or (d_idx in [5, 6] and h >= 12 and h <= 23)
            sales_count = random.randint(18, 55) if is_peak else random.randint(1, 12)
            price_index = 1.05 if is_peak else (0.95 if h < 7 else 1.0)
            hour_stats_heatmap.append({
                "day_idx": d_idx,
                "day_name": day_name,
                "hour": h,
                "sales": sales_count,
                "price_multiplier": round(price_index, 2),
                "is_peak": is_peak,
            })

    # Sparklines for the 25 items
    items_state = {}
    for item in items_meta:
        med = item["median"]
        points = [
            int(med * (1.0 + random.uniform(-0.06, 0.06)))
            for _ in range(7)
        ]
        ladder = [
            {"price": int(med * 0.90), "count": random.randint(1, 3)},
            {"price": int(med * 0.95), "count": random.randint(4, 8)},
            {"price": int(med * 1.00), "count": random.randint(10, 20)},
            {"price": int(med * 1.05), "count": random.randint(8, 15)},
            {"price": int(med * 1.10), "count": random.randint(3, 7)},
        ]
        items_state[item["item_id"]] = {
            "item_id": item["item_id"],
            "name_ru": item["name_ru"],
            "category": item["category"],
            "rank": item["rank"],
            "icon_path": item["icon_path"],
            "median": med,
            "min_buyout": int(med * random.uniform(0.85, 1.02)),
            "units_day": item["units_day"],
            "sparkline_7d": points,
            "orderbook_ladder": ladder,
            "qlt": item.get("qlt", 0),
            "ptn": item.get("ptn", 0),
        }

    # Market Trends Summary
    market_overview = {
        "tracked_count": len(items_meta),
        "total_active_signals": len(signals),
        "total_profit_potential": sum(s["plan"]["expected_profit"] for s in signals),
        "top_growing": [
            {"name_ru": "Атом", "diff": "+14.8%", "median": 2400000},
            {"name_ru": "Контейнер «Берлога-6»", "diff": "+9.2%", "median": 4200000},
            {"name_ru": "Продвинутые запчасти", "diff": "+6.5%", "median": 44500},
        ],
        "top_falling": [
            {"name_ru": "ВСС «Винторез»", "diff": "-11.4%", "median": 3900000},
            {"name_ru": "Браслет", "diff": "-8.2%", "median": 85000},
            {"name_ru": "АК-15", "diff": "-5.7%", "median": 7200000},
        ],
        "demand_surplus": [
            {"name_ru": "Продвинутые инструменты", "reason": "Продажи +42% за 3 дня, глубина стакана упала на 30%"},
            {"name_ru": "Сыворотка изменения", "reason": "Стабильный рост покупок, минимальный выкуп растет"},
        ]
    }

    # Notifications log
    notifications = [
        {
            "id": 1,
            "time": (now - timedelta(minutes=12)).strftime("%d.%m %H:%M"),
            "channel": "Telegram Bot",
            "item_name": "Атом (Особый +10)",
            "buy_price": 1850000,
            "target_price": 2350000,
            "profit": 382500,
            "roi": "20.7%",
            "status": "Доставлено"
        },
        {
            "id": 2,
            "time": (now - timedelta(minutes=35)).strftime("%d.%m %H:%M"),
            "channel": "Telegram Bot",
            "item_name": "Контейнер «Берлога-6»",
            "buy_price": 3200000,
            "target_price": 4150000,
            "profit": 742500,
            "roi": "23.2%",
            "status": "Доставлено"
        },
        {
            "id": 3,
            "time": (now - timedelta(hours=1, minutes=10)).strftime("%d.%m %H:%M"),
            "channel": "Telegram Bot",
            "item_name": "Продвинутые запчасти (10 шт)",
            "buy_price": 37500,
            "target_price": 44500,
            "profit": 47750,
            "roi": "12.7%",
            "status": "Доставлено"
        }
    ]

    payload = {
        "generated_at": now.isoformat(),
        "signals": signals,
        "positions": positions,
        "items": items_state,
        "market_overview": market_overview,
        "accuracy_stats": accuracy_stats,
        "heatmap": hour_stats_heatmap,
        "notifications": notifications,
    }

    with open("web/seed_terminal_data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open("docs/seed_terminal_data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open("data/seed_terminal_data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Generated seed terminal data with {len(signals)} signals and {len(items_state)} items!")

if __name__ == "__main__":
    generate_seed()
