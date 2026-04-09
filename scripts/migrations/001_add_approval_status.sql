-- Migration 001: Add approval_status to users table
-- Run this in the Supabase SQL Editor on existing databases.
-- Existing users default to 'approved'; new users created via OAuth get 'pending'.

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'approved'
    CHECK (approval_status IN ('pending', 'approved', 'rejected'));

CREATE INDEX IF NOT EXISTS idx_users_approval_status ON public.users(approval_status);
