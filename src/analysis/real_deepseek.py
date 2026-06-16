import os
import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from src.analysis.base_analyzer import BaseAnalyzer

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
LESSONS_FILE = Path(__file__).parent / "deepseek_lessons.md"

class RealDeepSeekAnalyzer(BaseAnalyzer):
    """
    Real DeepSeek API analyzer using deepseek-v4-flash.
    Lessons from xAI reviews are automatically appended to the prompt.
    """

    name = "deepseek-real"

    def __init__(self, model: str = None):
        # Support both flash (fast) and pro (deeper) models
        default_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.model = model or default_model
        self.client = None
        if DEEPSEEK_API_KEY:
            self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.lessons = self._load_lessons()

    def _load_lessons(self) -> str:
        if LESSONS_FILE.exists():
            content = LESSONS_FILE.read_text()
            # Only take the part after the marker
            if "<!-- xAI will append new lessons below this line -->" in content:
                return content.split("<!-- xAI will append new lessons below this line -->", 1)[1].strip()
        return ""

    def _build_prompt(self, df: pd.DataFrame, symbol: str) -> str:
        latest = df.iloc[-1]
        prev5 = df.tail(6).to_dict("records")

        prompt = f"""You are a fast crypto trading assistant for {symbol}.
Current price: {latest['close']:.2f}
RSI(14): {latest.get('rsi', 50):.1f}
MACD hist: {latest.get('macd_hist', 0):.4f}
EMA20 / EMA50: {latest.get('ema_20', 0):.2f} / {latest.get('ema_50', 0):.2f}
Volume vs SMA20: {latest.get('volume', 0) / max(latest.get('volume_sma', 1), 1):.2f}x

Recent 6 candles (open, high, low, close):
"""
        for r in prev5:
            prompt += f"  {r['open_time']:%H:%M} O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f}\n"

        prompt += """
Return ONLY valid JSON:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "reason": "short explanation"
}
"""

        if self.lessons:
            prompt = "=== Lessons from previous xAI reviews (learn from these) ===\n" + self.lessons + "\n\n" + prompt
        return prompt

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        # Always compute indicators first (reuse logic from fast analyzer)
        from src.analysis.fast_deepseek import FastDeepSeekAnalyzer
        local = FastDeepSeekAnalyzer()
        local_result = local.analyze(df, symbol)

        if not self.client:
            return {**local_result, "model": "deepseek-local-fallback"}

        try:
            prompt = self._build_prompt(df, symbol)
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            data = json.loads(content)

            return {
                "action": data.get("action", "HOLD").upper(),
                "confidence": float(data.get("confidence", 0.5)),
                "score": (1 if data.get("action") == "BUY" else -1 if data.get("action") == "SELL" else 0) * data.get("confidence", 0.5),
                "reason": data.get("reason", "deepseek api"),
                "model": self.name,
                "indicators": local_result["indicators"],
            }
        except Exception as e:
            # Fallback on any error
            return {**local_result, "model": "deepseek-local-error", "reason": f"api error: {str(e)[:60]}"}
