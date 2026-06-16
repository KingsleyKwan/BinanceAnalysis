import sqlite3
import json
from datetime import datetime
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
                close_price REAL
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
                   rsi: float, macd_hist: float, close_price: float):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO signals (timestamp, symbol, action, score, confidence, rsi, macd_hist, close_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, symbol, action, score, confidence, rsi, macd_hist, close_price))
        self.conn.commit()

    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
