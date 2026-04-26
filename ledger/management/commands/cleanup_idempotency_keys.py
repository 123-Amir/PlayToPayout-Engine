from django.core.management.base import BaseCommand
from ledger.models import IdempotencyKey
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired idempotency keys'

    def handle(self, *args, **options):
        deleted_count, _ = IdempotencyKey.cleanup_expired()
        
        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Cleaned up {deleted_count} expired idempotency keys')
            )
        else:
            self.stdout.write('No expired idempotency keys to clean up')