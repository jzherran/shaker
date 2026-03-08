# Shaker - FONAFAHE

Collaborative funding system where members contribute savings, build balances, and request loans backed by individual savings, a group of guarantors, or the collective fund.

## Tech Stack

- **Backend**: Python / FastAPI
- **Database**: Supabase (PostgreSQL)
- **Auth**: Google OAuth via Supabase Auth
- **Frontend**: Jinja2 templates + HTMX + Tailwind CSS (CDN)
- **Deployment**: Vercel (serverless via Mangum)

## Features

- **Account Management** — Each member gets a savings account with balance tracking
- **Contributions** — Record regular, extraordinary, or initial contributions that increase account balances
- **Loans** — Request loans with three backing types:
  - **Individual**: backed by the borrower's own savings
  - **Group**: backed by guarantors who pledge amounts from their balances
  - **Collective**: backed by the fund (max 20% cap per loan, requires admin approval)
- **Balance Reports** — Daily, monthly, and yearly balance snapshots per account
- **Collective Fund Overview** — Total balance, active loans, available lending capacity
- **Admin Panel** — Manage users, record contributions, approve/reject loans, generate snapshots

## Project Structure

```
shaker/
├── api/
│   ├── index.py              # FastAPI app, mounts routers and static files
│   ├── config.py             # Settings via pydantic-settings (env vars)
│   ├── database.py           # Supabase client initialization
│   ├── auth.py               # JWT session cookies, auth dependencies
│   ├── dependencies.py       # Shared dependencies (templates, DB)
│   ├── routers/              # Route handlers
│   │   ├── pages.py          # HTML pages (login, dashboard, callback)
│   │   ├── accounts.py       # Account CRUD
│   │   ├── contributions.py  # Contribution endpoints + HTMX
│   │   ├── loans.py          # Loan lifecycle endpoints
│   │   └── reports.py        # Balance reports and fund summary
│   ├── services/             # Business logic
│   │   ├── account_service.py
│   │   ├── contribution_service.py
│   │   ├── loan_service.py   # Loan validation per backing type
│   │   ├── report_service.py # Snapshot generation and queries
│   │   └── fund_service.py   # Collective fund calculations
│   └── models/               # Pydantic models
│       ├── user.py
│       ├── account.py
│       ├── contribution.py
│       ├── loan.py
│       └── report.py
├── templates/                # Jinja2 HTML templates with HTMX
├── static/css/               # Custom CSS
├── scripts/
│   ├── init_db.sql           # PostgreSQL schema (run in Supabase SQL Editor)
│   ├── seed_data.py          # Test data for development
│   └── generate_snapshots.py # Daily/monthly/yearly balance snapshots
├── requirements.txt
├── vercel.json
└── .env.example
```

## Setup

### 1. Supabase Project

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the contents of `scripts/init_db.sql`
3. Go to **Authentication** → **Providers** → **Google** → enable it
   - You'll need OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
4. Go to **Authentication** → **URL Configuration**:
   - **Site URL**: `http://localhost:8000` (local) or your Vercel URL (production)
   - **Redirect URLs**: add `http://localhost:8000/auth/callback`

### 2. Google Cloud Console

1. Create an OAuth 2.0 Client ID at [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials)
2. **Authorized JavaScript origins**: `http://localhost:8000`
3. **Authorized redirect URIs**: `https://<your-project>.supabase.co/auth/v1/callback`
4. Copy the Client ID and Secret into Supabase Google provider settings

### 3. Environment Variables

```bash
cp .env.example .env
```

Fill in your `.env`:

| Variable | Where to find it |
|----------|-----------------|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase → Settings → API → anon public key |
| `SUPABASE_SERVICE_KEY` | Supabase → Settings → API → service_role key |
| `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `APP_ENV` | `development` locally, `production` on Vercel |

### 4. Run Locally

```bash
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

Open `http://localhost:8000` — sign in with Google, and your user + account will be created automatically.

To make yourself admin, update your user in **Supabase Table Editor** → `users` → set `role` to `admin`.

### 5. Seed Test Data (Optional)

```bash
python -m scripts.seed_data
```

### 6. Deploy to Vercel

1. Add environment variables in **Vercel Dashboard** → project → **Settings** → **Environment Variables**
2. Add your Vercel domain to Google Cloud Console (Authorized JavaScript origins)
3. Add `https://your-app.vercel.app/auth/callback` to Supabase Redirect URLs
4. Deploy:

```bash
vercel --prod
```

## Database Schema

8 tables managed via `scripts/init_db.sql`:

| Table | Purpose |
|-------|---------|
| `users` | Members linked to Supabase Auth |
| `accounts` | Savings accounts with balance |
| `contributions` | Money in (regular, extraordinary, initial) |
| `loans` | Loan requests with backing type and status lifecycle |
| `loan_guarantors` | Group-backed loan guarantor pledges |
| `loan_payments` | Loan repayment records |
| `balance_snapshots` | Daily/monthly/yearly balance history |
| `fund_summary` | Collective fund totals (singleton) |

Atomic financial operations (contributions, payments, cancellations) use PostgreSQL functions to ensure balance consistency.

## API Endpoints

### Pages (HTML)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/login` | No | Login page with Google OAuth |
| GET | `/dashboard` | Yes | Balance overview and quick actions |
| GET | `/accounts` | Yes | Account list |
| GET | `/accounts/{id}` | Yes | Account detail |
| GET | `/contributions` | Yes | Contribution list with filters |
| GET | `/contributions/new` | Admin | New contribution form |
| GET | `/loans` | Yes | Loan list |
| GET | `/loans/request` | Yes | Loan request form |
| GET | `/loans/{id}` | Yes | Loan detail with schedule |
| GET | `/reports/balance` | Yes | Balance report with date range |
| GET | `/reports/fund` | Yes | Collective fund overview |

### API (JSON)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | Health check |
| POST | `/api/contributions` | Admin | Record contribution |
| DELETE | `/api/contributions/{id}` | Admin | Cancel contribution |
| POST | `/api/loans` | Yes | Submit loan request |
| POST | `/api/loans/{id}/approve` | Admin | Approve loan |
| POST | `/api/loans/{id}/reject` | Admin | Reject loan |
| POST | `/api/loans/{id}/disburse` | Admin | Mark loan disbursed |
| POST | `/api/loans/{id}/payments` | Admin | Record loan payment |
| GET | `/api/loans/{id}/schedule` | Yes | Amortization schedule |
| GET | `/api/reports/balance` | Yes | Balance snapshot data |
| GET | `/api/reports/fund-summary` | Yes | Fund summary data |
| POST | `/api/admin/snapshots/generate` | Admin | Trigger snapshot generation |

## License

MIT
