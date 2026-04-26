import time
import random
import logging
from django.db import transaction
from django.utils import timezone
from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Payout, LedgerEntry, Merchant

logger = get_task_logger(__name__)

# Constants
MAX_PAYOUT_ATTEMPTS = 3
PAYOUT_PROCESSING_TIMEOUT = 30  # seconds
SUCCESS_PROBABILITY = 0.70  # 70%
FAIL_PROBABILITY = 0.20    # 20%
PROCESSING_PROBABILITY = 0.10  # 10%


@shared_task(bind=True, max_retries=5)
def process_payout_task(self, payout_id):
    """
    Process a single payout with exponential backoff retry logic.
    
    Outcomes:
    - 70% success: status='completed', debit merchant ledger
    - 20% failure: status='failed', credit merchant ledger (refund)
    - 10% processing: keep status='processing', retry later
    
    Retry logic: if attempt_count > MAX_PAYOUT_ATTEMPTS, force fail with refund
    """
    try:
        # Fetch and lock the payout using select_for_update
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            
            # Check if already processed
            if payout.status in ['completed', 'failed']:
                logger.info(f"Payout {payout_id} already {payout.status}. Skipping.")
                return f"Payout {payout_id} already {payout.status}"
            
            # Update attempt count
            payout.attempt_count += 1
            
            # Check if max attempts exceeded
            if payout.attempt_count > MAX_PAYOUT_ATTEMPTS:
                logger.warning(f"Payout {payout_id} exceeded max attempts. Failing with refund.")
                payout.status = 'failed'
                payout.failure_reason = f'Max attempts exceeded ({MAX_PAYOUT_ATTEMPTS})'
                payout.save()
                
                # Refund: create credit ledger entry
                _create_refund_ledger(payout)
                return f"Payout {payout_id} failed after {payout.attempt_count} attempts. Refunded."
            
            # Set status to processing
            payout.status = 'processing'
            payout.save()
        
        # Simulate payout processing (30 seconds)
        logger.info(f"Starting payout processing for payout {payout_id}. Simulating 30 seconds...")
        time.sleep(PAYOUT_PROCESSING_TIMEOUT)
        
        # Generate random outcome
        outcome = random.random()
        
        with transaction.atomic():
            # Refresh payout from DB to ensure we have latest state
            payout = Payout.objects.select_for_update().get(id=payout_id)
            
            if outcome < SUCCESS_PROBABILITY:
                # 70% success case
                logger.info(f"Payout {payout_id} succeeded.")
                payout.status = 'completed'
                payout.reference_id = f"REF-{payout_id}-{int(time.time())}"
                payout.save()
                
                # Debit merchant ledger
                _create_debit_ledger(payout)
                
                return f"Payout {payout_id} completed successfully."
            
            elif outcome < (SUCCESS_PROBABILITY + FAIL_PROBABILITY):
                # 20% failure case
                logger.warning(f"Payout {payout_id} failed.")
                payout.status = 'failed'
                payout.failure_reason = 'Bank declined the transaction'
                payout.save()
                
                # Refund: create credit ledger entry
                _create_refund_ledger(payout)
                
                # Retry if under max attempts
                if payout.attempt_count < MAX_PAYOUT_ATTEMPTS:
                    logger.info(f"Scheduling retry for payout {payout_id}.")
                    # Calculate exponential backoff: 2^attempt_count seconds
                    countdown = (2 ** payout.attempt_count)
                    raise self.retry(countdown=countdown, exc=Exception("Payout failed, retrying..."))
                
                return f"Payout {payout_id} failed. Max retries reached. Refunded."
            
            else:
                # 10% processing case - stay in processing state, retry later
                logger.info(f"Payout {payout_id} still processing. Will retry later.")
                payout.save()
                
                # Exponential backoff retry
                countdown = (2 ** payout.attempt_count)
                raise self.retry(countdown=countdown, exc=Exception("Payout still processing"))
    
    except Payout.DoesNotExist:
        logger.error(f"Payout {payout_id} not found.")
        return f"Payout {payout_id} not found"
    except Exception as exc:
        logger.error(f"Error processing payout {payout_id}: {exc}")
        raise


@shared_task
def process_pending_payouts():
    """
    Periodic scheduled task to find and process all pending payouts.
    Runs every 10 seconds via Celery Beat.
    """
    try:
        pending_payouts = Payout.objects.filter(
            status='pending'
        ).values_list('id', flat=True)[:100]  # Process max 100 at a time
        
        if pending_payouts:
            logger.info(f"Found {len(pending_payouts)} pending payouts. Processing...")
            for payout_id in pending_payouts:
                process_payout_task.delay(payout_id)
        else:
            logger.debug("No pending payouts to process.")
        
        return f"Processed {len(pending_payouts)} pending payouts"
    
    except Exception as exc:
        logger.error(f"Error in process_pending_payouts: {exc}")
        return f"Error: {str(exc)}"


def _create_debit_ledger(payout):
    """
    Create a debit ledger entry when payout is successfully completed.
    Debit = money going out
    """
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        type='debit',
        amount_paise=payout.amount_paise,
        description=f'Payout completed - Ref: {payout.reference_id}'
    )
    logger.info(f"Created debit ledger entry for payout {payout.id}")


def _create_refund_ledger(payout):
    """
    Create a credit ledger entry when payout fails or is cancelled.
    Credit = money coming in (refund)
    """
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        type='credit',
        amount_paise=payout.amount_paise,
        description=f'Payout refund - Reason: {payout.failure_reason}'
    )
    logger.info(f"Created refund ledger entry for payout {payout.id}")
