from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize Celery Beat periodic tasks'

    def handle(self, *args, **options):
        # Create or get the 10-second interval schedule
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=10,
            period=IntervalSchedule.SECONDS,
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created 10-second interval schedule')
            )
        else:
            self.stdout.write('10-second interval schedule already exists')
        
        # Create or update the periodic task
        task, created = PeriodicTask.objects.get_or_create(
            name='Process pending payouts',
            defaults={
                'task': 'ledger.tasks.process_pending_payouts',
                'interval': schedule,
                'enabled': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created periodic task: Process pending payouts')
            )
        else:
            self.stdout.write('Periodic task already exists')
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Celery Beat schedule initialized successfully!')
        )
        self.stdout.write(
            'The following periodic task is now active:\n'
            '  - Process pending payouts (every 10 seconds)\n'
        )
