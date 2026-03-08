-- Shaker (FONAFAHE) Database Schema
-- Run this in the Supabase SQL Editor to initialize the database.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS (linked to Supabase Auth via auth.users)
-- ============================================================
CREATE TABLE public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_id UUID UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    national_id TEXT,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_auth_id ON public.users(auth_id);
CREATE INDEX idx_users_email ON public.users(email);

-- ============================================================
-- ACCOUNTS (each user has one savings account)
-- ============================================================
CREATE TABLE public.accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    account_number TEXT UNIQUE NOT NULL,
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT positive_balance CHECK (balance >= 0)
);

CREATE INDEX idx_accounts_user_id ON public.accounts(user_id);

-- ============================================================
-- CONTRIBUTIONS (money coming in)
-- ============================================================
CREATE TABLE public.contributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    contribution_type TEXT NOT NULL DEFAULT 'regular'
        CHECK (contribution_type IN ('regular', 'extraordinary', 'initial')),
    period_year INT NOT NULL,
    period_month INT NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    description TEXT,
    receipt_reference TEXT,
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('pending', 'completed', 'cancelled')),
    created_by UUID REFERENCES public.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contributions_account_id ON public.contributions(account_id);
CREATE INDEX idx_contributions_period ON public.contributions(period_year, period_month);

-- ============================================================
-- LOANS
-- ============================================================
CREATE TABLE public.loans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
    amount_requested NUMERIC(15, 2) NOT NULL CHECK (amount_requested > 0),
    amount_approved NUMERIC(15, 2),
    interest_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.0200,
    term_months INT NOT NULL CHECK (term_months > 0),
    backing_type TEXT NOT NULL
        CHECK (backing_type IN ('individual', 'group', 'collective')),
    status TEXT NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'approved', 'rejected', 'active',
                          'paid', 'defaulted', 'cancelled')),
    purpose TEXT,
    rejection_reason TEXT,
    approved_by UUID REFERENCES public.users(id),
    approved_at TIMESTAMPTZ,
    disbursed_at TIMESTAMPTZ,
    due_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_loans_account_id ON public.loans(account_id);
CREATE INDEX idx_loans_status ON public.loans(status);

-- ============================================================
-- LOAN GUARANTORS (for group-backed loans)
-- ============================================================
CREATE TABLE public.loan_guarantors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    loan_id UUID NOT NULL REFERENCES public.loans(id) ON DELETE CASCADE,
    guarantor_account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
    guaranteed_amount NUMERIC(15, 2) NOT NULL CHECK (guaranteed_amount > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    responded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(loan_id, guarantor_account_id)
);

CREATE INDEX idx_loan_guarantors_loan_id ON public.loan_guarantors(loan_id);
CREATE INDEX idx_loan_guarantors_guarantor ON public.loan_guarantors(guarantor_account_id);

-- ============================================================
-- LOAN PAYMENTS (repayments on active loans)
-- ============================================================
CREATE TABLE public.loan_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    loan_id UUID NOT NULL REFERENCES public.loans(id) ON DELETE RESTRICT,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    principal_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
    interest_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
    payment_number INT NOT NULL,
    receipt_reference TEXT,
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('pending', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_loan_payments_loan_id ON public.loan_payments(loan_id);

-- ============================================================
-- BALANCE SNAPSHOTS (daily/monthly/yearly aggregations)
-- ============================================================
CREATE TABLE public.balance_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('daily', 'monthly', 'yearly')),
    snapshot_date DATE NOT NULL,
    balance NUMERIC(15, 2) NOT NULL,
    total_contributions NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_loan_disbursements NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_loan_payments NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(account_id, snapshot_type, snapshot_date)
);

CREATE INDEX idx_snapshots_account_date ON public.balance_snapshots(account_id, snapshot_date);

-- ============================================================
-- COLLECTIVE FUND SUMMARY (singleton row)
-- ============================================================
CREATE TABLE public.fund_summary (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    total_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_members INT NOT NULL DEFAULT 0,
    total_active_loans NUMERIC(15, 2) NOT NULL DEFAULT 0,
    available_for_lending NUMERIC(15, 2) NOT NULL DEFAULT 0,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.fund_summary (id) VALUES (1);

-- ============================================================
-- ROW-LEVEL SECURITY
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loan_guarantors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loan_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.balance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fund_summary ENABLE ROW LEVEL SECURITY;

-- Service role key bypasses RLS, so these policies are for
-- direct client access only (future use).
CREATE POLICY "Service role full access" ON public.users
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.accounts
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.contributions
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.loans
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.loan_guarantors
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.loan_payments
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.balance_snapshots
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.fund_summary
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- POSTGRESQL FUNCTIONS (atomic operations)
-- ============================================================

-- Record a contribution and update account balance atomically
CREATE OR REPLACE FUNCTION record_contribution(
    p_account_id UUID,
    p_amount NUMERIC,
    p_contribution_type TEXT,
    p_period_year INT,
    p_period_month INT,
    p_description TEXT,
    p_receipt_reference TEXT,
    p_created_by UUID
) RETURNS UUID AS $$
DECLARE
    v_contribution_id UUID;
BEGIN
    INSERT INTO contributions (
        account_id, amount, contribution_type,
        period_year, period_month, description,
        receipt_reference, created_by
    ) VALUES (
        p_account_id, p_amount, p_contribution_type,
        p_period_year, p_period_month, p_description,
        p_receipt_reference, p_created_by
    ) RETURNING id INTO v_contribution_id;

    UPDATE accounts
    SET balance = balance + p_amount, updated_at = NOW()
    WHERE id = p_account_id;

    RETURN v_contribution_id;
END;
$$ LANGUAGE plpgsql;

-- Disburse a loan: set status to active, update balances
CREATE OR REPLACE FUNCTION disburse_loan(
    p_loan_id UUID,
    p_amount NUMERIC
) RETURNS VOID AS $$
DECLARE
    v_account_id UUID;
BEGIN
    SELECT account_id INTO v_account_id
    FROM loans WHERE id = p_loan_id AND status = 'approved';

    IF v_account_id IS NULL THEN
        RAISE EXCEPTION 'Loan not found or not in approved status';
    END IF;

    UPDATE loans
    SET status = 'active', disbursed_at = NOW(), updated_at = NOW()
    WHERE id = p_loan_id;

    -- Loan disbursement does not add to account balance directly;
    -- the money is disbursed externally. This tracks the obligation.
END;
$$ LANGUAGE plpgsql;

-- Record a loan payment
CREATE OR REPLACE FUNCTION record_loan_payment(
    p_loan_id UUID,
    p_amount NUMERIC,
    p_principal NUMERIC,
    p_interest NUMERIC,
    p_payment_number INT,
    p_receipt_reference TEXT
) RETURNS UUID AS $$
DECLARE
    v_payment_id UUID;
    v_total_paid NUMERIC;
    v_amount_approved NUMERIC;
BEGIN
    INSERT INTO loan_payments (
        loan_id, amount, principal_amount, interest_amount,
        payment_number, receipt_reference
    ) VALUES (
        p_loan_id, p_amount, p_principal, p_interest,
        p_payment_number, p_receipt_reference
    ) RETURNING id INTO v_payment_id;

    -- Check if loan is fully paid
    SELECT COALESCE(SUM(principal_amount), 0) INTO v_total_paid
    FROM loan_payments
    WHERE loan_id = p_loan_id AND status = 'completed';

    SELECT amount_approved INTO v_amount_approved
    FROM loans WHERE id = p_loan_id;

    IF v_total_paid >= v_amount_approved THEN
        UPDATE loans SET status = 'paid', updated_at = NOW()
        WHERE id = p_loan_id;
    END IF;

    RETURN v_payment_id;
END;
$$ LANGUAGE plpgsql;

-- Cancel a contribution and reverse balance
CREATE OR REPLACE FUNCTION cancel_contribution(
    p_contribution_id UUID
) RETURNS VOID AS $$
DECLARE
    v_account_id UUID;
    v_amount NUMERIC;
    v_status TEXT;
BEGIN
    SELECT account_id, amount, status INTO v_account_id, v_amount, v_status
    FROM contributions WHERE id = p_contribution_id;

    IF v_status != 'completed' THEN
        RAISE EXCEPTION 'Can only cancel completed contributions';
    END IF;

    UPDATE contributions
    SET status = 'cancelled', updated_at = NOW()
    WHERE id = p_contribution_id;

    UPDATE accounts
    SET balance = balance - v_amount, updated_at = NOW()
    WHERE id = v_account_id;
END;
$$ LANGUAGE plpgsql;
