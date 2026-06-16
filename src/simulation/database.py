import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

DB_PATH = Path("trading.db")

class TradingDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()
        # Portfolio snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT UNIQUE,
                cash_usd REAL,
                total_equity REAL
            )
        """)
        # Current holdings (latest state)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                symbol TEXT PRIMARY KEY,
                amount REAL,
                avg_buy_price REAL,
                last_updated TEXT
            )
        """)
        # Trade log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,           -- BUY or SELL
                price REAL,
                amount REAL,
                usd_value REAL,
                fee REAL,
                notes TEXT
            )
        """)
        # Signal history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                action TEXT,
                score REAL,
                confidence REAL,
                rsi REAL,
                macd_hist REAL,
                close_price REAL,
                model TEXT
            )
        """)
        # DeepSeek decision log for xAI 15-min review
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deepseek_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                action TEXT,
                confidence REAL,
                reason TEXT,
                close_price REAL,
                rsi REAL,
                macd_hist REAL,
                ema_trend TEXT,
                volume_ratio REAL,
                price_15min_later REAL,
                xai_judgment TEXT,           -- CORRECT / WRONG / REVIEWED
                xai_correction TEXT
            )
        """)
        self.conn.commit()

    def save_snapshot(self, timestamp: str, cash: float, total_equity: float):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO portfolio_snapshots (timestamp, cash_usd, total_equity)
            VALUES (?, ?, ?)
        """, (timestamp, cash, total_equity))
        self.conn.commit()

    def get_latest_portfolio(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        row = cur.execute("""
            SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        if row:
            return {"cash": row["cash_usd"], "total_equity": row["total_equity"], "timestamp": row["timestamp"]}
        return {"cash": 900.0, "total_equity": 900.0, "timestamp": None}

    def update_holding(self, symbol: str, amount: float, avg_price: float, ts: str):
        cur = self.conn.cursor()
        if amount <= 0:
            cur.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
        else:
            cur.execute("""
                INSERT OR REPLACE INTO holdings (symbol, amount, avg_buy_price, last_updated)
                VALUES (?, ?, ?, ?)
            """, (symbol, amount, avg_price, ts))
        self.conn.commit()

    def get_holdings(self) -> Dict[str, Dict[str, float]]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT * FROM holdings").fetchall()
        return {r["symbol"]: {"amount": r["amount"], "avg_buy_price": r["avg_buy_price"]} for r in rows}

    def log_trade(self, ts: str, symbol: str, side: str, price: float, amount: float,
                  usd_value: float, fee: float, notes: str = ""):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO trades (timestamp, symbol, side, price, amount, usd_value, fee, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, symbol, side, price, amount, usd_value, fee, notes))
        self.conn.commit()

    def log_signal(self, ts: str, symbol: str, action: str, score: float, confidence: float,
                   rsi: float, macd_hist: float, close_price: float, model: str = ""):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO signals (timestamp, symbol, action, score, confidence, rsi, macd_hist, close_price, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, symbol, action, score, confidence, rsi, macd_hist, close_price, model))
        self.conn.commit()

    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def log_deepseek_decision(self, ts: str, symbol: str, action: str, confidence: float,
                              reason: str, close_price: float, rsi: float, macd_hist: float,
                              ema_trend: str, volume_ratio: float):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO deepseek_decisions
            (timestamp, symbol, action, confidence, reason, close_price, rsi, macd_hist,
             ema_trend, volume_ratio, price_15min_later, xai_judgment, xai_correction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
        """, (ts, symbol, action, confidence, reason, close_price, rsi, macd_hist,
              ema_trend, volume_ratio))
        self.conn.commit()

    def get_unreviewed_deepseek_decisions(self, limit: int = 20):
        cur = self.conn.cursor()
        rows = cur.execute("""
            SELECT * FROM deepseek_decisions
            WHERE xai_judgment IS NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def update_deepseek_judgment(self, decision_id: int, price_15min_later: float,
                                  judgment: str, correction: str = ""):
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE deepseek_decisions
            SET price_15min_later = ?, xai_judgment = ?, xai_correction = ?
            WHERE id = ?
        """, (price_15min_later, judgment, correction, decision_id))
        self.conn.commit()

    def get_performance_report(self, hours: int = 24):
        """Return performance stats for the last N hours."""
        cur = self.conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        # Current equity
        current = cur.execute("""
            SELECT total_equity FROM portfolio_snapshots
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        current_equity = current["total_equity"] if current else 0

        # Start equity (first snapshot in the window)
        start_row = cur.execute("""
            SELECT total_equity FROM portfolio_snapshots
            WHERE timestamp >= ?
            ORDER BY timestamp ASC LIMIT 1
        """, (since,)).fetchone()
        start_equity = start_row["total_equity"] if start_row else current_equity

        # Trades in the period
        trades = cur.execute("""
            SELECT COUNT(*) as cnt,
                   SUM(CASE WHEN side = 'SELL' AND notes LIKE '%pnl=%' 
                            AND CAST(SUBSTR(notes, INSTR(notes, '$')+1) AS REAL) > 0 
                       THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE timestamp >= ?
        """, (since,)).fetchone()

        trade_count = trades["cnt"] if trades else 0
        win_count = trades["wins"] if trades else 0
        win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0

        return_pct = ((current_equity - start_equity) / start_equity * 100) if start_equity > 0 else 0

        return {
            "hours": hours,
            "start_equity": round(start_equity, 2),
            "current_equity": round(current_equity, 2),
            "return_pct": round(return_pct, 2),
            "trade_count": trade_count,
            "win_rate": round(win_rate, 1),
        }

    def close(self):
        self.conn.close()
