# Shaker - FONAFAHE

Collaborative funding system where members contribute savings, build balances, and request loans backed by individual savings, a group of guarantors, or the collective fund.

## Tech Stack

- **Backend**: Python / FastAPI
- **Database**: Supabase (PostgreSQL)
- **Auth**: Google OAuth via Supabase Auth (session cookies; merged identities resolved via `user_auth_aliases`)
- **Frontend**: Jinja2 templates + HTMX + Tailwind CSS (CDN)
- **UI (Material Design)** — The app follows **Google Material Design** (Material 3–style): **Roboto** via Google Fonts, a **blue** primary color system (extended Tailwind theme in `templates/base.html`), **elevation** shadows, a **top app bar** with rounded navigation and **state-layer** hover/focus treatment, and shared **surface/card** styles in `static/css/custom.css` (e.g. `.md-card`, `.md-surface-app`, `.nav-link-m3`)
- **Deployment**: Vercel (serverless via Mangum)

## Features

- **Account Management** — Each member gets a savings account with balance tracking
- **Enrollment** — New users submit a national ID after login; dashboard is available once enrolled. If the ID matches another member, an **identity merge request** is created for admin review instead of linking immediately
- **Profile** — Members can update name, phone, and optional **default contribution amount** (prefilled on the contribution form)
- **Contributions** — Record regular, extraordinary, or initial contributions. **Admins** can record for any account or use **batch mode** for many members at once; **members** can record only for their own account
- **Loans** — Request loans with three backing types:
  - **Individual**: backed by the borrower's own savings
  - **Group**: backed by guarantors who pledge amounts from their balances
  - **Collective**: backed by the fund (max 20% cap per loan, requires admin approval)
- **Balance Reports** — Daily, monthly, and yearly balance snapshots per account
- **Collective Fund Overview** — Total balance, active loans, available lending capacity
- **Admin** — Approve/reject loans, cancel contributions, generate snapshots, and **approve or reject identity merge requests** (`/admin/merge-requests`)

## Project Structure

```
shaker/
├── api/
│   ├── index.py              # FastAPI app, mounts routers and static files
│   ├── config.py             # Settings via pydantic-settings (env vars)
│   ├── database.py           # Supabase client initialization
│   ├── auth.py               # JWT session cookies, auth dependencies, merged-user lookup
│   ├── dependencies.py     # Shared dependencies (templates, DB)
│   ├── routers/
│   │   ├── pages.py          # HTML pages (login, dashboard, enrollment, auth)
│   │   ├── accounts.py
│   │   ├── contributions.py  # Contributions, HTMX, batch HTMX
│   │   ├── loans.py
│   │   ├── reports.py
│   │   ├── profile.py        # Profile page + HTMX update
│   │   └── users.py          # Admin merge requests
│   ├── services/
│   │   ├── account_service.py
│   │   ├── contribution_service.py  # Includes batch RPC
│   │   ├── loan_service.py
│   │   ├── report_service.py
│   │   ├── fund_service.py
│   │   └── user_service.py   # Enrollment, merges, profile
│   └── models/
│       ├── user.py
│       ├── account.py
│       ├── contribution.py
│       ├── loan.py
│       └── report.py
├── templates/                # Jinja2 HTML templates with HTMX
├── static/css/               # Custom CSS (Material-style tokens, HTMX)
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
   - Review the script first: it defines tables, RLS policies, and PL/pgSQL functions (including `approve_identity_merge` and `record_contributions_batch`). If your file begins with `DELETE` statements, only run those against a database where you intend to wipe seed data
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

Open `http://localhost:8000` — sign in with Google. New users get an account automatically, then are redirected to **`/enrollment`** until they submit a national ID. After enrollment, **`/dashboard`** is available.

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

Core tables and functions are defined in `scripts/init_db.sql`:

| Table | Purpose |
|-------|---------|
| `users` | Members linked to Supabase Auth (`national_id`, `default_contribution_amount`, `is_active`, …) |
| `user_auth_aliases` | Secondary auth IDs/emails after an approved identity merge |
| `identity_merge_requests` | Pending or resolved merge requests when two accounts share a national ID |
| `accounts` | Savings accounts with balance |
| `contributions` | Money in (regular, extraordinary, initial) |
| `loans` | Loan requests with backing type and status lifecycle |
| `loan_guarantors` | Group-backed loan guarantor pledges |
| `loan_payments` | Loan repayment records |
| `balance_snapshots` | Daily/monthly/yearly balance history |
| `fund_summary` | Collective fund totals (singleton) |

Atomic financial operations (contributions, loan payments, cancellations, **identity merge approval**, **batch contributions**) use PostgreSQL functions to keep balances and related rows consistent.

## API Endpoints

### Pages (HTML)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/login` | No | Login page with Google OAuth |
| GET | `/auth/callback` | No | OAuth callback (client posts session to `/auth/session`) |
| GET | `/enrollment` | Yes | National ID enrollment (required before dashboard if unset) |
| POST | `/enrollment` | Yes | Submit national ID |
| GET | `/dashboard` | Yes | Balance overview and quick actions |
| GET | `/profile` | Yes | Edit profile and default contribution amount |
| GET | `/accounts` | Yes | Account list |
| GET | `/accounts/{id}` | Yes | Account detail |
| GET | `/contributions` | Yes | Contribution list with filters |
| GET | `/contributions/new` | Yes | New contribution (admin: any account; member: own account only) |
| GET | `/contributions/batch` | Admin | Batch contribution form |
| GET | `/loans` | Yes | Loan list |
| GET | `/loans/request` | Yes | Loan request form |
| GET | `/loans/{id}` | Yes | Loan detail with schedule |
| GET | `/reports/balance` | Yes | Balance report with date range |
| GET | `/reports/fund` | Yes | Collective fund overview |
| GET | `/admin/merge-requests` | Admin | Pending identity merge requests |

### API (JSON / HTMX)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | Health check |
| POST | `/api/contributions` | Yes | Record contribution (member: own account only) |
| POST | `/api/contributions/htmx` | Yes | HTMX: contribution row partial |
| POST | `/api/contributions/batch/htmx` | Admin | HTMX: batch contributions result |
| DELETE | `/api/contributions/{id}` | Admin | Cancel contribution |
| POST | `/api/profile/htmx` | Yes | HTMX: updated profile form |
| POST | `/api/loans` | Yes | Submit loan request |
| POST | `/api/loans/{id}/approve` | Admin | Approve loan |
| POST | `/api/loans/{id}/reject` | Admin | Reject loan |
| POST | `/api/loans/{id}/disburse` | Admin | Mark loan disbursed |
| POST | `/api/loans/{id}/payments` | Admin | Record loan payment |
| GET | `/api/loans/{id}/schedule` | Yes | Amortization schedule |
| POST | `/api/loans/{id}/guarantors` | Yes | Add guarantors (as applicable) |
| GET | `/api/reports/balance` | Yes | Balance snapshot data |
| GET | `/api/reports/fund-summary` | Yes | Fund summary data |
| POST | `/api/admin/snapshots/generate` | Admin | Trigger snapshot generation |
| POST | `/api/merge-requests/{id}/approve` | Admin | Approve identity merge (HTML snippet for HTMX) |
| POST | `/api/merge-requests/{id}/reject` | Admin | Reject merge request |

## License

MIT
