#!/usr/bin/env python
"""
Test script for Payout API with Idempotency and Concurrency.
This script demonstrates:
1. Idempotency-Key header requirement
2. Same key same merchant -> same response
3. 24hr key expiration
4. Atomic balance checking with SELECT FOR UPDATE
5. Concurrency: 100rs balance pe 2x60rs -> sirf 1 success
6. Transactional: balance debit + payout pending atomic
"""

import os
import sys
import django
import time
import json
import uuid
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto_payout.settings')
django.setup()

from ledger.models import Merchant, Payout, LedgerEntry, IdempotencyKey
from django.utils import timezone
from datetime import timedelta


def create_test_merchant(name, account_id, initial_balance=10000):  # 100 rupees
    """Create a test merchant with initial balance"""
    merchant, created = Merchant.objects.get_or_create(
        name=name,
        defaults={'bank_account_id': account_id}
    )
    
    if created:
        # Add initial credit to merchant
        LedgerEntry.objects.create(
            merchant=merchant,
            type='credit',
            amount_paise=initial_balance,
            description='Initial balance for testing'
        )
        print(f"✓ Created merchant '{name}' with initial balance: {initial_balance} paise")
    else:
        print(f"✓ Merchant '{name}' already exists")
    
    merchant.refresh_from_db()
    print(f"  Current balance: {merchant.balance} paise")
    return merchant


def test_idempotency_key_validation():
    """Test Idempotency-Key header validation"""
    print("\n" + "="*60)
    print("TEST 1: Idempotency-Key Header Validation")
    print("="*60)
    
    merchant = create_test_merchant("Test Merchant 1", "ACC-TEST-001")
    
    # Test 1.1: Missing Idempotency-Key header
    print("\n1.1 Missing Idempotency-Key header:")
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test 1.2: Invalid UUID format
    print("\n1.2 Invalid UUID format:")
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': 'invalid-uuid'},
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")


def test_idempotency_behavior():
    """Test idempotency behavior - same key same response"""
    print("\n" + "="*60)
    print("TEST 2: Idempotency Behavior")
    print("="*60)
    
    merchant = create_test_merchant("Test Merchant 2", "ACC-TEST-002")
    idempotency_key = str(uuid.uuid4())
    
    print(f"\nUsing Idempotency-Key: {idempotency_key}")
    
    # First request
    print("\n2.1 First request:")
    try:
        response1 = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 2000,  # 20 rupees
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response1.status_code}")
        print(f"  Response: {response1.json()}")
        response1_data = response1.json()
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Second request with same key
    print("\n2.2 Second request (same key):")
    try:
        response2 = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 3000,  # Different amount (should be ignored)
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response2.status_code}")
        print(f"  Response: {response2.json()}")
        response2_data = response2.json()
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Verify responses are identical
    if response1_data == response2_data:
        print("✓ SUCCESS: Both responses are identical (idempotent)")
    else:
        print("✗ FAILED: Responses differ (not idempotent)")
        print(f"  Response 1: {response1_data}")
        print(f"  Response 2: {response2_data}")


def test_insufficient_balance():
    """Test insufficient balance handling"""
    print("\n" + "="*60)
    print("TEST 3: Insufficient Balance")
    print("="*60)
    
    merchant = create_test_merchant("Test Merchant 3", "ACC-TEST-003", 500)  # Only 5 rupees
    idempotency_key = str(uuid.uuid4())
    
    print(f"\nMerchant balance: {merchant.balance} paise")
    print(f"Requesting: 1000 paise")
    
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,  # More than balance
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Test idempotency for error responses too
        print("\n3.1 Testing idempotency for error response:")
        response2 = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"Status: {response2.status_code}")
        print(f"Response: {response2.json()}")
        
        if response.json() == response2.json():
            print("✓ SUCCESS: Error responses are also idempotent")
        else:
            print("✗ FAILED: Error responses differ")
            
    except Exception as e:
        print(f"Error: {e}")


def concurrent_payout_request(merchant_id, amount_paise, idempotency_key, request_id):
    """Single concurrent payout request"""
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant_id,
                'amount_paise': amount_paise,
                'bank_account_id': 'ACC123456'
            },
            timeout=10
        )
        return {
            'request_id': request_id,
            'status_code': response.status_code,
            'response': response.json() if response.status_code < 500 else {'error': 'server_error'},
            'success': response.status_code == 201
        }
    except Exception as e:
        return {
            'request_id': request_id,
            'status_code': None,
            'response': {'error': str(e)},
            'success': False
        }


def test_concurrency():
    """Test concurrency: 100rs balance pe 2x60rs -> sirf 1 success"""
    print("\n" + "="*60)
    print("TEST 4: Concurrency Test")
    print("="*60)
    
    merchant = create_test_merchant("Test Merchant 4", "ACC-TEST-004", 10000)  # 100 rupees
    print(f"\nMerchant initial balance: {merchant.balance} paise")
    
    # Launch 2 concurrent requests for 60 rupees each (total 120 > 100)
    print("\nLaunching 2 concurrent requests for 6000 paise each (total 12000 > 10000)...")
    
    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for i in range(2):
            idempotency_key = str(uuid.uuid4())
            future = executor.submit(
                concurrent_payout_request,
                merchant.id, 6000, idempotency_key, f"req_{i+1}"
            )
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"Request {result['request_id']}: Status {result['status_code']}, Success: {result['success']}")
    
    # Analyze results
    successful_requests = [r for r in results if r['success']]
    failed_requests = [r for r in results if not r['success']]
    
    print(f"\nResults:")
    print(f"  Successful: {len(successful_requests)}")
    print(f"  Failed: {len(failed_requests)}")
    
    if len(successful_requests) == 1 and len(failed_requests) == 1:
        print("✓ SUCCESS: Exactly 1 request succeeded (concurrency protection working)")
        
        # Check final balance
        merchant.refresh_from_db()
        print(f"Final balance: {merchant.balance} paise")
        expected_balance = 10000 - 6000  # 10000 - 6000 = 4000
        if merchant.balance == expected_balance:
            print("✓ SUCCESS: Balance correctly debited")
        else:
            print(f"✗ FAILED: Expected balance {expected_balance}, got {merchant.balance}")
            
    else:
        print("✗ FAILED: Expected exactly 1 success and 1 failure")
        
        # Show details
        for result in results:
            print(f"  {result['request_id']}: {result['response']}")


def test_key_expiration():
    """Test 24hr key expiration"""
    print("\n" + "="*60)
    print("TEST 5: Key Expiration (24 hours)")
    print("="*60)
    
    merchant = create_test_merchant("Test Merchant 5", "ACC-TEST-005")
    idempotency_key = str(uuid.uuid4())
    
    print(f"\nUsing Idempotency-Key: {idempotency_key}")
    
    # Create a payout
    print("\n5.1 Creating initial payout:")
    try:
        response1 = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response1.status_code}")
        print(f"  Response: {response1.json()}")
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Manually expire the key (set expires_at to past)
    print("\n5.2 Manually expiring the idempotency key:")
    key_obj = IdempotencyKey.objects.get(key=idempotency_key, merchant=merchant)
    key_obj.expires_at = timezone.now() - timedelta(hours=1)  # 1 hour ago
    key_obj.save()
    print("  Key expired manually")
    
    # Try same request again (should work since key expired)
    print("\n5.3 Retrying with expired key:")
    try:
        response2 = requests.post(
            'http://localhost:8000/api/v1/payouts/',
            headers={'Idempotency-Key': idempotency_key},
            json={
                'merchant': merchant.id,
                'amount_paise': 1000,
                'bank_account_id': 'ACC123456'
            }
        )
        print(f"  Status: {response2.status_code}")
        print(f"  Response: {response2.json()}")
        
        if response2.status_code == 201:
            print("✓ SUCCESS: Expired key allowed new request")
        else:
            print("✗ FAILED: Expired key blocked new request")
            
    except Exception as e:
        print(f"  Error: {e}")


def main():
    print("=" * 80)
    print("PlayToPayout Engine - Payout API Idempotency & Concurrency Tests")
    print("=" * 80)
    
    print("\n⚠️  IMPORTANT: Make sure Django server is running on http://localhost:8000")
    print("   Run: python manage.py runserver")
    print("\n⚠️  Also ensure PostgreSQL and Redis are running")
    
    try:
        # Run all tests
        test_idempotency_key_validation()
        test_idempotency_behavior()
        test_insufficient_balance()
        test_concurrency()
        test_key_expiration()
        
        print("\n" + "=" * 80)
        print("All tests completed!")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")


if __name__ == '__main__':
    main()