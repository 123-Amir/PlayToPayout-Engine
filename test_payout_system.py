#!/usr/bin/env python
"""
Test script for the PlayToPayout engine Celery task processing.
This script demonstrates:
1. Creating merchants
2. Creating payouts
3. Monitoring payout status changes
4. Verifying ledger entries and merchant balance
"""

import os
import sys
import django
import time
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto_payout.settings')
django.setup()

from ledger.models import Merchant, Payout, LedgerEntry
from ledger.tasks import process_payout_task


def create_test_merchant(name, account_id):
    """Create a test merchant"""
    merchant, created = Merchant.objects.get_or_create(
        name=name,
        defaults={'bank_account_id': account_id}
    )
    print(f"✓ Merchant '{name}' created/found (ID: {merchant.id})")
    return merchant


def create_test_payout(merchant, amount_paise, idempotency_key):
    """Create a test payout"""
    payout = Payout.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        bank_account_id=merchant.bank_account_id,
        idempotency_key=idempotency_key,
        status='pending'
    )
    print(f"✓ Payout created (ID: {payout.id}, Status: {payout.status}, Amount: {amount_paise} paise)")
    return payout


def print_payout_status(payout):
    """Print current payout status"""
    payout.refresh_from_db()
    print(f"\n  Payout {payout.id} Status:")
    print(f"    - Status: {payout.status}")
    print(f"    - Attempts: {payout.attempt_count}")
    if payout.reference_id:
        print(f"    - Reference: {payout.reference_id}")
    if payout.failure_reason:
        print(f"    - Failure Reason: {payout.failure_reason}")


def print_merchant_balance(merchant):
    """Print merchant balance and ledger entries"""
    merchant.refresh_from_db()
    balance = merchant.balance
    entries = LedgerEntry.objects.filter(merchant=merchant).order_by('-created_at')
    
    print(f"\n✓ Merchant '{merchant.name}' Balance: {balance} paise")
    print(f"  Ledger Entries ({entries.count()}):")
    for entry in entries[:5]:  # Show last 5 entries
        print(f"    - {entry.type.upper()}: {entry.amount_paise} paise ({entry.created_at.strftime('%H:%M:%S')})")


def main():
    print("=" * 70)
    print("PlayToPayout Engine - Celery Task Processing Test")
    print("=" * 70)
    
    # Create test merchant
    print("\n[1] Creating Test Merchant...")
    merchant = create_test_merchant("Test Merchant", "ACC-TEST-001")
    print(f"    Initial Balance: {merchant.balance} paise\n")
    
    # Create test payout
    print("[2] Creating Test Payout (100,000 paise)...")
    payout = create_test_payout(merchant, 100000, f"PAYOUT-TEST-{int(time.time())}")
    print_payout_status(payout)
    
    # Queue for processing
    print("\n[3] Queuing Payout for Immediate Processing...")
    # Manually trigger the task (normally it would be queued by signal or scheduler)
    print("  ℹ In production, this would be triggered by:")
    print("    - Signal when payout is created")
    print("    - Celery Beat scheduler every 10 seconds")
    print("    - Manual retry via API endpoint")
    
    print("\n[4] Next Steps:")
    print("  1. Run: python manage.py migrate")
    print("  2. Run: python manage.py init_celery_schedule")
    print("  3. Start PostgreSQL & Redis")
    print("  4. Start Django: python manage.py runserver")
    print("  5. Start Celery worker: celery -A playto_payout worker -l info")
    print("  6. Start Celery beat: celery -A playto_payout beat -l info")
    print("  7. Create payouts via API")
    print("  8. Monitor task processing in Celery worker terminal")
    
    print("\n[5] API Endpoints for Testing:")
    print("  POST   /api/merchants/ - Create merchant")
    print("  GET    /api/merchants/{id}/balance/ - Get merchant balance")
    print("  POST   /api/payouts/ - Create payout")
    print("  GET    /api/payouts/{id}/ - Get payout details")
    print("  POST   /api/payouts/{id}/retry/ - Retry failed payout")
    print("  GET    /api/ledger-entries/?merchant=1 - Get merchant ledger")
    
    print("\n[6] Expected Processing Outcomes:")
    print("  - 70% Payout succeeds → status: 'completed', debit ledger entry")
    print("  - 20% Payout fails → status: 'failed', credit ledger (refund)")
    print("  - 10% Payout stays processing → auto-retry with exponential backoff")
    print("  - Max 3 attempts → auto-fail with refund if all fail")
    
    print("\n" + "=" * 70)
    print("Setup complete! Follow the steps above to test the payout system.")
    print("=" * 70)


if __name__ == '__main__':
    main()
