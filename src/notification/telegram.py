import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramNotifier:
    """
    Simple Telegram bot notifier for trading events.
    Send messages when trades happen or important events occur.
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.enabled else None

        if self.enabled:
            print("[Telegram] Notifications enabled")
        else:
            print("[Telegram] Notifications disabled (no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"[Telegram] Failed to send message: {e}")
            return False

    def notify_trade(self, action: str, symbol: str, price: float, amount: float,
                     usd_value: float, pnl: Optional[float] = None, reason: str = ""):
        """Send notification for a trade execution."""
        emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "🔄"
        text = f"{emoji} <b>{action}</b> {symbol}\n"
        text += f"Price: <code>${price:,.2f}</code>\n"
        text += f"Amount: <code>{amount:.6f}</code>\n"
        text += f"Value: <code>${usd_value:,.2f}</code>"

        if pnl is not None:
            pnl_emoji = "✅" if pnl >= 0 else "❌"
            text += f"\nPnL: {pnl_emoji} <code>${pnl:+.2f}</code>"

        if reason:
            text += f"\n<i>{reason}</i>"

        self.send(text)

    def notify_self_correction(self, mistakes: int, lessons_added: int):
        """Send notification when self-correction finds mistakes."""
        if mistakes == 0:
            text = "✅ <b>Self-Correction</b>\nAll DeepSeek decisions in the last 2 hours were correct."
        else:
            text = f"⚠️ <b>Self-Correction</b>\nFound <b>{mistakes}</b> mistake(s).\n"
            text += f"Added <b>{lessons_added}</b> new lesson(s) to DeepSeek."
            text += "\nSystem paused 30 seconds for correction."

        self.send(text)

    def notify_portfolio(self, cash: float, total_equity: float, holdings: dict):
        """Send a portfolio summary (used on 2-hour cycle)."""
        text = "📊 <b>Portfolio Update</b>\n"
        text += f"Cash: <code>${cash:,.2f}</code>\n"
        text += f"Equity: <code>${total_equity:,.2f}</code>\n"
        if holdings:
            h_str = ", ".join([f"{k}:{v['amount']:.4f}" for k, v in holdings.items()])
            text += f"Holdings: <code>{h_str}</code>"
        else:
            text += "Holdings: <i>none</i>"

        self.send(text)
