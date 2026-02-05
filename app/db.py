import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("app/data/expenses.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            merchant TEXT,
            date TEXT,
            total REAL,
            currency TEXT,
            category TEXT,
            notes TEXT,
            receipt_text TEXT,
            status TEXT,
            reasons TEXT,
            flags TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def insert_expense(payload: Dict[str, Any]) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO expenses
        (employee_id, merchant, date, total, currency, category, notes, receipt_text, status, reasons, flags, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("employee_id"),
            payload.get("merchant"),
            payload.get("date"),
            payload.get("total"),
            payload.get("currency"),
            payload.get("category"),
            payload.get("notes"),
            payload.get("receipt_text"),
            payload.get("status"),
            payload.get("reasons"),
            payload.get("flags"),
            payload.get("created_at"),
        ),
    )
    conn.commit()
    expense_id = cur.lastrowid
    conn.close()
    return int(expense_id)


def list_expenses(limit: int = 200) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def list_expenses_by_employee(employee_id: str) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM expenses WHERE employee_id = ? ORDER BY date DESC",
        (employee_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def find_duplicate(merchant: str, total: float, date: str, employee_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM expenses
        WHERE employee_id = ? AND merchant = ? AND total = ? AND date = ?
        ORDER BY id DESC LIMIT 1
        """,
        (employee_id, merchant, total, date),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None
