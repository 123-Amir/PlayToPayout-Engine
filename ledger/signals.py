from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models import Payout
from .tasks import process_payout_task

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payout)
def queue_payout_processing(sender, instance, created, **kwargs):
    """
    When a new payout is created, automatically queue it for processing.
    """
    if created:
        logger.info(f"New payout created: {instance.id}. Queuing for processing...")
        # Queue the payout for processing with a 2-second delay
        # process_payout_task.apply_async(args=[instance.id], countdown=2)
        logger.info(f"Payout processing queued (disabled for testing): {instance.id}")
