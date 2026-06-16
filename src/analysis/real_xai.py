import os
import json
from typing import Dict, Any
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from src.analysis.base_analyzer import BaseAnalyzer

load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_BASE_URL = "https://api.x.ai/v1"

class RealXAIAnalyzer(BaseAnalyzer):
    """
    Real xAI (Grok) API analyzer.
    Runs every 15 minutes. More thoughtful. Can return BOTH for position rotation.
    """

    name = "xai-real"

    def __init__(self, model: str = None):
        self.model = model or os.getenv("XAI_MODEL", "grok-4.3")
        self.client = None
        if XAI_API_KEY:
            self.client = OpenAI(api_key=XAI_API_KEY, base_url=XAI_BASE_URL)

    def _build_prompt(self, df: pd.DataFrame, symbol: str, holdings: dict) -> str:
        latest = df.iloc[-1]
        current_holding = holdings.get(symbol, {"amount": 0})

        prompt = f"""You are an expert crypto portfolio manager using Grok.
We are trading {symbol} on Binance spot. Current holdings: {current_holding['amount']:.6f} coins.

Latest indicators:
- Price: {latest['close']:.2f}
- RSI(14): {latest.get('rsi', 50):.1f}
- MACD histogram: {latest.get('macd_hist', 0):.4f}
- EMA20 vs EMA50 trend strength
- Volume surge: {latest.get('volume', 0) / max(latest.get('volume_sma', 1), 1):.2f}x

Task:
Decide whether to BUY, SELL, BOTH (rotate/switch position), or HOLD.
Consider transaction fees (0.1% each way) and risk.

Return ONLY this JSON:
{
  "action": "BUY" | "SELL" | "BOTH" | "HOLD",
  "confidence": 0.0-1.0,
  "reason": "concise professional reasoning (max 25 words)"
}
"""
        return prompt

    def analyze(self, df: pd.DataFrame, symbol: str = "", holdings: dict = None) -> Dict[str, Any]:
        from src.analysis.deep_xai import DeepXAIAnalyzer
        local = DeepXAIAnalyzer()
        local_result = local.analyze(df, symbol)

        if not self.client:
            return {**local_result, "model": "xai-local-fallback"}

        try:
            prompt = self._build_prompt(df, symbol, holdings or {})
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            data = json.loads(content)

            action = data.get("action", "HOLD").upper()
            conf = float(data.get("confidence", 0.6))

            return {
                "action": action,
                "confidence": conf,
                "score": (1 if action in ("BUY", "BOTH") else -1 if action in ("SELL", "BOTH") else 0) * conf,
                "reason": data.get("reason", "xai api"),
                "model": self.name,
                "indicators": local_result["indicators"],
            }
        except Exception as e:
            return {**local_result, "model": "xai-local-error", "reason": f"api error: {str(e)[:60]}"}
