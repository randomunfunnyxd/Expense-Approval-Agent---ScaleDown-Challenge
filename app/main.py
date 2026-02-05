from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import find_duplicate, init_db, insert_expense, list_expenses, list_expenses_by_employee
from .policy import load_policy

app = FastAPI(title="Expense Approval Agent")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

DATE_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})"),
]
TOTAL_PATTERN = re.compile(r"(?:total|amount|balance)\s*[:\-]?\s*\$?([0-9]+(?:\.[0-9]{2})?)", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"\b(USD|EUR|GBP|INR|JPY)\b")


def _normalize_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    if re.match(r"\d{1,2}/\d{1,2}/\d{4}", raw):
        month, day, year = raw.split("/")
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None


def _extract_fields(receipt_text: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    lines = [l.strip() for l in receipt_text.splitlines() if l.strip()]
    if lines:
        fields["merchant"] = lines[0][:80]
    for pattern in DATE_PATTERNS:
        match = pattern.search(receipt_text)
        if match:
            fields["date"] = _normalize_date(match.group(1))
            break
    match_total = TOTAL_PATTERN.search(receipt_text)
    if match_total:
        fields["total"] = float(match_total.group(1))
    match_currency = CURRENCY_PATTERN.search(receipt_text)
    if match_currency:
        fields["currency"] = match_currency.group(1)
    return fields


def _month_bounds(dt: datetime) -> (datetime, datetime):
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month - timedelta(microseconds=1)
    return start, end


def _sum_employee_monthly(employee_id: str, target_date: datetime) -> float:
    start, end = _month_bounds(target_date)
    expenses = list_expenses_by_employee(employee_id)
    total = 0.0
    for exp in expenses:
        if not exp.get("date"):
            continue
        try:
            exp_date = datetime.fromisoformat(exp["date"])
        except ValueError:
            continue
        if start <= exp_date <= end and exp.get("total"):
            total += float(exp["total"])
    return total


def _evaluate_policy(payload: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    flags: List[str] = []
    required_fields = policy.get("required_fields", [])
    hard_limits = policy.get("hard_limits", {})
    allowed_categories = set(policy.get("allowed_categories", []))
    suspicious_keywords = [k.lower() for k in policy.get("suspicious_keywords", [])]
    receipt_rules = policy.get("receipt_rules", {})

    # Required fields
    for field in required_fields:
        if not payload.get(field):
            reasons.append(f"Missing required field: {field}")

    # Category
    category = payload.get("category")
    if category and category not in allowed_categories:
        reasons.append("Category not allowed by policy")

    # Amount limits
    total = payload.get("total")
    if total is not None:
        if total > float(hard_limits.get("max_single_expense", 0)):
            reasons.append("Single expense exceeds company limit")
        if category == "meals" and total > float(hard_limits.get("max_meal", 0)):
            reasons.append("Meal expense exceeds limit")
        if category == "lodging" and total > float(hard_limits.get("max_lodging_per_night", 0)):
            reasons.append("Lodging expense exceeds nightly limit")
        if category == "transport" and total > float(hard_limits.get("max_transport", 0)):
            reasons.append("Transport expense exceeds limit")
        if category == "misc" and total > float(hard_limits.get("max_misc", 0)):
            reasons.append("Misc expense exceeds limit")

    # Receipt rules
    receipt_text = (payload.get("receipt_text") or "").strip()
    require_receipt_over = float(receipt_rules.get("require_receipt_over", 0))
    allow_manual_under = float(receipt_rules.get("allow_manual_notes_under", 0))
    if total is not None and total > require_receipt_over and not receipt_text and not payload.get("receipt_file"):
        reasons.append("Receipt required for this amount")
    if total is not None and total <= allow_manual_under and not receipt_text:
        flags.append("Manual note allowed but no receipt text provided")

    # Date rules
    max_days = int(receipt_rules.get("max_days_after_purchase", 0))
    if payload.get("date"):
        try:
            d = datetime.fromisoformat(payload["date"])
            if datetime.utcnow() - d > timedelta(days=max_days):
                reasons.append("Receipt is too old")
        except ValueError:
            reasons.append("Invalid date format")

    # Keyword flags
    haystack = " ".join([receipt_text.lower(), (payload.get("notes") or "").lower()])
    for kw in suspicious_keywords:
        if kw in haystack:
            flags.append(f"Suspicious keyword detected: {kw}")

    # Duplicate
    if payload.get("merchant") and payload.get("total") and payload.get("date"):
        dupe = find_duplicate(payload["merchant"], float(payload["total"]), payload["date"], payload["employee_id"])
        if dupe:
            flags.append("Possible duplicate expense found")

    status = "approved"
    if reasons:
        status = "denied"
    elif flags:
        status = "consider"

    return {"status": status, "reasons": reasons, "flags": flags}


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def index() -> HTMLResponse:
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/submit")
async def submit_expense(
    employee_id: str = Form(...),
    category: str = Form(""),
    total: str = Form(""),
    date: str = Form(""),
    merchant: str = Form(""),
    currency: str = Form(""),
    notes: str = Form(""),
    receipt_text: str = Form(""),
    receipt_file: Optional[UploadFile] = File(None),
) -> JSONResponse:
    policy = load_policy()
    payload: Dict[str, Any] = {
        "employee_id": employee_id.strip(),
        "category": category.strip() or None,
        "total": float(total) if total.strip() else None,
        "date": _normalize_date(date) if date.strip() else None,
        "merchant": merchant.strip() or None,
        "currency": currency.strip() or policy.get("currency", "USD"),
        "notes": notes.strip() or None,
        "receipt_text": receipt_text.strip() or None,
        "receipt_file": receipt_file.filename if receipt_file else None,
        "created_at": datetime.utcnow().isoformat(),
    }

    # If receipt text exists, attempt to fill missing fields
    if payload.get("receipt_text"):
        extracted = _extract_fields(payload["receipt_text"])
        for key, value in extracted.items():
            if payload.get(key) in (None, ""):
                payload[key] = value

    decision = _evaluate_policy(payload, policy)
    payload["status"] = decision["status"]
    payload["reasons"] = "; ".join(decision["reasons"])
    payload["flags"] = "; ".join(decision["flags"])

    expense_id = insert_expense(payload)

    monthly_spend = _sum_employee_monthly(employee_id, datetime.utcnow())
    monthly_budget = float(policy.get("monthly_budget_per_employee", 0))

    response = {
        "id": expense_id,
        "status": payload["status"],
        "reasons": decision["reasons"],
        "flags": decision["flags"],
        "monthly_spend": monthly_spend,
        "monthly_budget": monthly_budget,
        "remaining_budget": max(0.0, monthly_budget - monthly_spend),
    }
    return JSONResponse(response)


@app.get("/api/expenses")
def get_expenses() -> JSONResponse:
    return JSONResponse({"items": list_expenses(300)})


@app.get("/api/summary")
def get_summary() -> JSONResponse:
    expenses = list_expenses(500)
    by_status: Dict[str, int] = {"approved": 0, "denied": 0, "consider": 0}
    by_category: Dict[str, float] = {}
    monthly_totals: Dict[str, float] = {}

    for exp in expenses:
        status = exp.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        category = exp.get("category") or "uncategorized"
        amount = float(exp.get("total") or 0.0)
        by_category[category] = by_category.get(category, 0.0) + amount
        if exp.get("date"):
            month = exp["date"][:7]
            monthly_totals[month] = monthly_totals.get(month, 0.0) + amount

    return JSONResponse(
        {
            "by_status": by_status,
            "by_category": by_category,
            "monthly_totals": monthly_totals,
        }
    )
