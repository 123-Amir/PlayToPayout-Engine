# Playto Payout Engine

This is a minimal payout engine for Playto-style merchants. It keeps a ledger-backed balance for each merchant, lets them request payouts, and processes payouts asynchronously through a background worker.

## Tech stack

- Backend: Django + Django REST Framework
- Database: PostgreSQL (amounts stored as integers in paise)
- Background jobs: Celery + Redis
- Frontend: React + Tailwind (dashboard folder)

## Core ideas

- All money amounts are stored as `BigIntegerField` in paise, no floats.
- Merchant balance is always derived from the ledger using database aggregation (credits − debits), never manually cached in Python.
- Payout requests are idempotent using an `Idempotency-Key` header scoped per merchant.
- Concurrency is handled with database transactions and row-level locking, so two simultaneous payouts cannot overspend the same balance.
- A background worker drives the payout state machine: `pending → processing → completed/failed`, with retries and automatic refunds on failure.

For more detail about the design, see `EXPLAINER.md`.
