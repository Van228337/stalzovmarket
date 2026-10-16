"""Telegram Alert Dispatcher.

Sends formatted trade opportunity signals to Telegram with:
- Item name and segment
- Unit buy price and expected sell target
- Net profit after 5% fee and ROI
- Estimated days/hours to liquidate
- Confidence score and core reason
- Rate-limiting (max alerts/hour) and fingerprint deduplication
"""

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set
import httpx

logger = logging.getLogger("telegram-notifier")

CACHE_DIR = Path("cache")
SENT_ALERTS_FILE = CACHE_DIR / "sent_alerts.json"


class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        max_alerts_per_hour: int = 15,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.max_alerts_per_hour = max_alerts_per_hour
        self.sent_fingerprints: Set[str] = self._load_sent_cache()
        self.alert_timestamps: List[float] = []
        self.proxy = os.getenv("TELEGRAM_PROXY_URL") or os.getenv("HTTPS_PROXY")
        self.is_offline = False

    def _load_sent_cache(self) -> Set[str]:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if SENT_ALERTS_FILE.exists():
            try:
                with open(SENT_ALERTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data)
            except Exception:
                return set()
        return set()

    def _save_sent_cache(self):
        try:
            with open(SENT_ALERTS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.sent_fingerprints)[-500:], f)
        except Exception as e:
            logger.warning(f"Could not persist sent alerts cache: {e}")

    def is_rate_limited(self) -> bool:
        now = time.time()
        self.alert_timestamps = [t for t in self.alert_timestamps if now - t < 3600]
        return len(self.alert_timestamps) >= self.max_alerts_per_hour

    async def send_message(self, text: str) -> bool:
        """Send raw HTML message to Telegram chat."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping alert.")
            return False

        if self.is_offline:
            logger.warning("Telegram is unreachable on this network (timeout/blocked). Skipping alert.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            client_kwargs = {"timeout": 4.0}
            if self.proxy:
                client_kwargs["proxy"] = self.proxy

            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram message delivered successfully.")
                    return True
                else:
                    logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
                    return False
        except (httpx.ConnectTimeout, httpx.ConnectError) as e:
            logger.warning(f"Telegram connection timed out (api.telegram.org may be blocked on local ISP without proxy): {e}")
            self.is_offline = True
            return False
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram alert: {e}")
            return False

    async def notify_signal(self, signal: Dict[str, Any]) -> bool:
        """Format and send trade signal alert if not duplicate or rate-limited."""
        key = f"{signal.get('item_id')}_{signal.get('lot', {}).get('buy_unit')}_{signal.get('segment')}"
        if key in self.sent_fingerprints:
            return False

        if self.is_rate_limited():
            logger.warning("Hourly Telegram alert limit reached, suppressing alert.")
            return False

        name = signal.get("name_ru", signal.get("item_id", "Предмет"))
        segment = signal.get("segment_label") or signal.get("segment", "Стандарт")
        plan = signal.get("plan", {})
        lot = signal.get("lot", {})
        fair = signal.get("fair", {})
        liquidity = signal.get("liquidity", {})

        buy_price = lot.get("buy_unit", 0)
        sell_target = plan.get("sell_target_unit", 0)
        profit = plan.get("expected_profit", 0)
        roi = plan.get("roi", 0) * 100
        days = liquidity.get("days_to_sell_est", 1.0)
        hours = round(days * 24, 1)
        conf = round(signal.get("confidence", 0) * 100)

        msg = (
            f"🎯 <b>ВЫГОДНЫЙ ЛОТ: {name}</b>\n"
            f"Сегмент: <i>{segment}</i>\n\n"
            f"💰 <b>Покупка:</b> {buy_price:,.0f} ₽\n"
            f"🎯 <b>Продавать за:</b> {sell_target:,.0f} ₽\n"
            f"📈 <b>Чистый профит:</b> +{profit:,.0f} ₽ (ROI <b>{roi:.1f}%</b>)\n"
            f"⏱ <b>Срок реализации:</b> ~{hours} ч. (ликвидность: {liquidity.get('units_per_day', 0)} шт/сут)\n"
            f"🛡 <b>Уверенность:</b> {conf}%\n\n"
            f"💡 <i>{plan.get('list_when', 'Выставлять сразу')}</i>\n"
            f"⚠️ <i>Проверьте наличие лота на аукционе в игре перед выкупом!</i>"
        )

        sent = await self.send_message(msg)
        if sent:
            self.sent_fingerprints.add(key)
            self._save_sent_cache()
            self.alert_timestamps.append(time.time())
        return sent
