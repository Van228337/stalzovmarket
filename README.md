# STALCRAFT Market Bot (STALZONE Scanner)

> Полностью бесплатный аналитический сервис и сканер арбитражных сделок аукциона STALCRAFT.
> Бюджет 0 ₽/$. Без постоянно работающих серверов.

---

## 🚀 Быстрый старт за 5 минут

### 1. Локальный запуск (тест без API ключей на Демо-сервере)
```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Запуск Фазы 0 (проверка канала и Cloudflare)
python collector/test_channel.py

# 3. Запуск юнит-тестов
pytest

# 4. Пробный сбор данных
python collector/runner.py --tier hot --dry-run
```

Результаты работы будут сохранены в `data/digest.json`. Откройте `web/index.html` в браузере для просмотра интерактивного дашборда.

---

## 🛠 Архитектура

| Компонент | Решение | Стоимость | Ограничения и защита |
|---|---|---|---|
| **Планировщик & Сборщик** | GitHub Actions (cron) | **0 ₽** | Без лимитов для публичных репозиториев. Keep-alive раз в месяц |
| **База данных** | Supabase Postgres Free | **0 ₽** | Бюджет ≤ 400 МБ из 500 МБ. Авто-очистка устаревших лотов |
| **Аналитика** | Python 3.12 (`httpx`, `numpy`) | **0 ₽** | Взвешенная медиана, отсечение выбросов 10%, детектор манипуляций |
| **Дашборд** | GitHub Pages / Cloudflare Pages | **0 ₽** | Статический сайт (HTML5 + CSS + Chart.js) |
| **LLM-Дайджест** | `digest.json` + `prompts/llm_analyst.md` | **0 ₽** | Компактный JSON (≤ 30 КБ) для передачи в нейросеть |

---

## 🔐 Настройка секретов (GitHub Secrets / `.env`)

Для боевого режима укажите секреты в настройках репозитория (`Settings -> Secrets and variables -> Actions`):

| Секрет | Описание | Обязателен |
|---|---|---|
| `STALCRAFT_CLIENT_ID` | `client_id` приложения EXBO | Да (для боевого сервера) |
| `STALCRAFT_CLIENT_SECRET` | `client_secret` приложения EXBO | Да (для боевого сервера) |
| `STALCRAFT_REGION` | Регион игры (`RU`, `EU`, `NA`, `SEA`, `NEA`). По умолчанию: `RU` | Нет |
| `SUPABASE_URL` | URL проекта Supabase | Да (для хранения) |
| `SUPABASE_SERVICE_ROLE_KEY` | Сервисный ключ для записи данных | Да (для хранения) |
| `SUPABASE_DB_URL` | PostgreSQL connection string для миграций | Опционально |
| `TELEGRAM_BOT_TOKEN` | Токен бота Telegram для алертов | Опционально |
| `TELEGRAM_CHAT_ID` | ID чата для получения сигналов | Опционально |

---

## 📊 Формулы и логика сигналов

1. **Честная цена (Fair Price):**
   - Рассчитывается исключительно по истории реальных сделок (`history`), а не по активным лотам.
   - Цены всегда приводятся к единице (`price / amount`).
   - Отсечение 10% крайних выбросов + экспоненциальное затухание по времени (half-life = 3 дня).
2. **Фильтр прибыльности:**
   $$\text{profit\_expected} = (\text{sell\_target} \times (1 - \text{FEE}) - \text{buy\_unit}) \times \text{amount} \ge \text{MIN\_PROFIT}$$
   $$\text{profit\_floor} = (\text{sell\_floor} \times (1 - \text{FEE}) - \text{buy\_unit}) \times \text{amount} \ge 0$$
   Сделка не рекомендуется, если в пессимистичном сценарии (P25) мы теряем капитал!
3. **Модули оружия (`1pyq`):**
   - Декодирование атрибутов `additional.attributes` (слоты: надстройка, отклонение, концепт).
   - Расчёт потенциала (0..190) и точных значений эффектов.
