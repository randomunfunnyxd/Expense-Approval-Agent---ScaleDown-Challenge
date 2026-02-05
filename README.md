# Expense Approval Agent

A simple FastAPI app that takes receipt images and/or receipt text, applies a company policy, and returns an **approved / denied / consider** decision. It also tracks monthly budgets and shows an interactive dashboard.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: `http://127.0.0.1:8000`

## How the decision works

- Policy lives in `policy.yaml` (edit freely).
- The agent checks required fields, category limits, receipt rules, and suspicious keywords.
- If it finds blocking issues → **denied**.
- If it finds non-blocking risk flags → **consider**.
- Otherwise → **approved**.

## Inputs supported

- Receipt text (paste OCR output or manual notes)
- Optional receipt image upload (stored only as filename for now)

To add OCR, plug in a service (e.g., Tesseract, AWS Textract, Google Vision) in `app/main.py` where receipt text is handled.

## Dashboard

The dashboard shows:
- Status breakdown
- Spend by category
- Monthly trend
- Recent expenses
- Budget remaining for the last submitted employee

Data is stored in a local SQLite database: `app/data/expenses.db`.

## Policy editing

Open `policy.yaml` and update limits, categories, or receipt rules. The service reloads policy on each request so changes apply immediately.
