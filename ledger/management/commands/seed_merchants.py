from django.core.management.base import BaseCommand
from django.db import transaction
from ledger.models import Merchant, LedgerEntry
import random
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seed the database with 3 merchants, each with 50000 paise credit history (10 entries)'

    def handle(self, *args, **options):
        # Merchant data
        merchants_data = [
            {
                'name': 'TechCorp Solutions',
                'bank_account_id': 'ACC0012345678901'
            },
            {
                'name': 'DigitalMart E-commerce',
                'bank_account_id': 'ACC0012345678902'
            },
            {
                'name': 'ServiceHub Providers',
                'bank_account_id': 'ACC0012345678903'
            }
        ]

        # Credit amount per entry: 50000 paise total / 10 entries = 5000 paise each
        CREDIT_AMOUNT_PER_ENTRY = 5000  # 50 INR in paise
        ENTRIES_PER_MERCHANT = 10

        # Sample credit descriptions
        credit_descriptions = [
            'Payment received for order #{}',
            'Refund processed for transaction #{}',
            'Commission earned from sale #{}',
            'Bonus credit for loyalty program',
            'Cashback reward for purchase #{}',
            'Settlement from partner #{}',
            'Revenue share payment #{}',
            'Subscription fee collected #{}',
            'Service charge reimbursement #{}',
            'Account top-up credit #{}'
        ]

        with transaction.atomic():
            for merchant_data in merchants_data:
                # Create merchant
                merchant, created = Merchant.objects.get_or_create(
                    name=merchant_data['name'],
                    defaults={'bank_account_id': merchant_data['bank_account_id']}
                )

                if created:
                    self.stdout.write(f'Created merchant: {merchant.name}')
                else:
                    self.stdout.write(f'Merchant already exists: {merchant.name}')
                    continue

                # Create 10 credit entries for each merchant
                base_time = timezone.now() - timedelta(days=30)  # Spread over last 30 days

                for i in range(ENTRIES_PER_MERCHANT):
                    # Random time within the 30-day window
                    random_days = random.randint(0, 29)
                    random_hours = random.randint(0, 23)
                    entry_time = base_time + timedelta(days=random_days, hours=random_hours)

                    # Random description
                    description = random.choice(credit_descriptions).format(
                        f"{random.randint(10000, 99999)}"
                    )

                    # Create credit entry
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        type='credit',
                        amount_paise=CREDIT_AMOUNT_PER_ENTRY,
                        description=description,
                        created_at=entry_time
                    )

                total_credited = ENTRIES_PER_MERCHANT * CREDIT_AMOUNT_PER_ENTRY
                self.stdout.write(
                    f'  → Added {ENTRIES_PER_MERCHANT} credit entries '
                    f'(₹{total_credited/100:.2f} total)'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded {len(merchants_data)} merchants '
                f'with credit history'
            )
        )