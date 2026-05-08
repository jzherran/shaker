-- Migration 002: Loan payments approval workflow
-- Run this in the Supabase SQL Editor on existing databases.
--
-- Changes:
-- 1) Default new loan_payments rows to status 'pending' (was 'completed').
-- 2) Track who/when approved a payment via approved_by/approved_at columns.
-- 3) Update record_loan_payment() to insert payments as 'pending' so they
--    do NOT count toward loan completion until an admin approves them.
-- 4) Add approve_loan_payment() and reject_loan_payment() helpers used by
--    the admin approval flow.
--
-- This script is idempotent — safe to re-run.

-- ------------------------------------------------------------
-- 1) Schema changes
-- ------------------------------------------------------------
ALTER TABLE public.loan_payments
    ALTER COLUMN status SET DEFAULT 'pending';

ALTER TABLE public.loan_payments
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id);

ALTER TABLE public.loan_payments
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

ALTER TABLE public.loan_payments
    ADD COLUMN IF NOT EXISTS submitted_by UUID REFERENCES public.users(id);

ALTER TABLE public.loan_payments
    ADD COLUMN IF NOT EXISTS notes TEXT;

CREATE INDEX IF NOT EXISTS idx_loan_payments_status ON public.loan_payments(status);

-- ------------------------------------------------------------
-- 2) Update record_loan_payment to insert as 'pending'
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION record_loan_payment(
    p_loan_id UUID,
    p_amount NUMERIC,
    p_principal NUMERIC,
    p_interest NUMERIC,
    p_payment_number INT,
    p_receipt_reference TEXT,
    p_submitted_by UUID DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_payment_id UUID;
BEGIN
    INSERT INTO loan_payments (
        loan_id, amount, principal_amount, interest_amount,
        payment_number, receipt_reference, status, submitted_by, notes
    ) VALUES (
        p_loan_id, p_amount, p_principal, p_interest,
        p_payment_number, p_receipt_reference, 'pending', p_submitted_by, p_notes
    ) RETURNING id INTO v_payment_id;

    RETURN v_payment_id;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- 3) Approve a loan payment atomically and mark loan as paid if covered
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION approve_loan_payment(
    p_payment_id UUID,
    p_approved_by UUID
) RETURNS VOID AS $$
DECLARE
    v_loan_id UUID;
    v_status TEXT;
    v_total_paid NUMERIC;
    v_amount_approved NUMERIC;
BEGIN
    SELECT loan_id, status INTO v_loan_id, v_status
    FROM loan_payments WHERE id = p_payment_id;

    IF v_loan_id IS NULL THEN
        RAISE EXCEPTION 'Payment not found';
    END IF;
    IF v_status != 'pending' THEN
        RAISE EXCEPTION 'Only pending payments can be approved';
    END IF;

    UPDATE loan_payments
    SET status = 'completed',
        approved_by = p_approved_by,
        approved_at = NOW()
    WHERE id = p_payment_id;

    SELECT COALESCE(SUM(principal_amount), 0) INTO v_total_paid
    FROM loan_payments
    WHERE loan_id = v_loan_id AND status = 'completed';

    SELECT amount_approved INTO v_amount_approved
    FROM loans WHERE id = v_loan_id;

    IF v_amount_approved IS NOT NULL AND v_total_paid >= v_amount_approved THEN
        UPDATE loans SET status = 'paid', updated_at = NOW()
        WHERE id = v_loan_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- 4) Reject a loan payment
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION reject_loan_payment(
    p_payment_id UUID,
    p_rejected_by UUID
) RETURNS VOID AS $$
DECLARE
    v_status TEXT;
BEGIN
    SELECT status INTO v_status FROM loan_payments WHERE id = p_payment_id;

    IF v_status IS NULL THEN
        RAISE EXCEPTION 'Payment not found';
    END IF;
    IF v_status != 'pending' THEN
        RAISE EXCEPTION 'Only pending payments can be rejected';
    END IF;

    UPDATE loan_payments
    SET status = 'cancelled',
        approved_by = p_rejected_by,
        approved_at = NOW()
    WHERE id = p_payment_id;
END;
$$ LANGUAGE plpgsql;
