# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shaker (FONAFAHE) is a collaborative funding system where members contribute savings, build balances, and request loans backed by individual savings, a group of guarantors, or the collective fund. Built with Python/FastAPI + Supabase PostgreSQL, with Jinja2/HTMX frontend.

## Development Commands

```bash
# Run locally (dev server with hot reload)
uvicorn api.index:app --reload --port 8000

# Install dependencies
pip install -r requirements.txt

# Seed test data (requires Supabase connection)
python -m scripts.seed_data

# Generate balance snapshots
python -m scripts.generate_snapshots

# Deploy to Vercel
vercel --prod
```

API docs: `http://localhost:8000/docs` | UI: `http://localhost:8000/`

## Architecture

- **Backend**: FastAPI with routers, services, and Pydantic models
- **Database**: Supabase PostgreSQL with atomic operations via PL/pgSQL functions
- **Auth**: Supabase Auth (Google OAuth) with signed JWT session cookies
- **Frontend**: Jinja2 templates + HTMX + Tailwind CSS CDN (no build step)
- **Deploy**: Vercel (serverless)

### Code Layout

```
api/
├── index.py            # FastAPI app, mounts routers and static files
├── config.py           # pydantic-settings (env vars)
├── database.py         # Supabase client initialization
├── auth.py             # Session management, JWT, get_current_user/require_admin
├── dependencies.py     # Shared dependencies (templates, DB, context)
├── routers/            # Route handlers (pages, accounts, contributions, loans, reports)
├── services/           # Business logic (account, contribution, loan validation, reports, fund)
└── models/             # Pydantic models (user, account, contribution, loan, report)
templates/              # Jinja2 HTML templates with HTMX
static/css/             # Custom CSS (Tailwind via CDN)
scripts/                # DB init SQL, seed data, snapshot generation
```

### Key Design Decisions

- **Service layer pattern**: Routers call services; services call Supabase. No direct DB access in routers.
- **Atomic financial operations**: Contributions and loan payments use PostgreSQL functions (`record_contribution`, `record_loan_payment`, `cancel_contribution`) to ensure balance consistency.
- **Loan backing types**: `individual` (own savings), `group` (guarantors), `collective` (fund with 20% cap). Validation logic in `api/services/loan_service.py`.
- **Available balance**: Account balance minus amounts committed as guarantor on active loans. Used for group backing validation.
- **Balance snapshots**: Generated daily/monthly/yearly by `scripts/generate_snapshots.py`. Stored in `balance_snapshots` table.
- **Fund summary**: Singleton row in `fund_summary` tracking total balance, members, active loans, available lending.
- **Auth flow**: Google OAuth via Supabase JS client -> `/auth/callback` page extracts token -> POST `/auth/session` sets httponly cookie -> server reads cookie via `get_current_user`.

### Database Schema (`scripts/init_db.sql`)

Tables: `users`, `accounts`, `contributions`, `loans`, `loan_guarantors`, `loan_payments`, `balance_snapshots`, `fund_summary`. All use UUID primary keys. RLS enabled (bypassed server-side via service role key).

### Environment Variables (`.env.example`)

`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `SECRET_KEY`
