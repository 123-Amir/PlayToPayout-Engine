from django.db import models
from django.db.models import Sum, Q, DecimalField, F
from django.utils import timezone
from datetime import timedelta


class Merchant(models.Model):
    """
    Represents a merchant in the payout system.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    bank_account_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'merchants'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['bank_account_id']),
        ]

    def __str__(self):
        return self.name

    @property
    def balance(self):
        """
        Calculate merchant balance using database aggregation.
        balance = sum(credits) - sum(debits) in paise
        """
        aggregation = LedgerEntry.objects.filter(
            merchant=self
        ).aggregate(
            credits=Sum(
                'amount_paise',
                filter=Q(type='credit'),
                output_field=models.BigIntegerField()
            ),
            debits=Sum(
                'amount_paise',
                filter=Q(type='debit'),
                output_field=models.BigIntegerField()
            )
        )
        
        credits = aggregation['credits'] or 0
        debits = aggregation['debits'] or 0
        return credits - debits

    @property
    def held_balance(self):
        """
        Calculate held balance from pending payouts.
        held_balance = sum of pending payout amounts in paise
        """
        aggregation = Payout.objects.filter(
            merchant=self,
            status='pending'
        ).aggregate(
            held=Sum('amount_paise', output_field=models.BigIntegerField())
        )
        return aggregation['held'] or 0

    @property
    def available_balance(self):
        """
        Calculate available balance (total balance minus held amounts).
        available_balance = credits - debits - held_balance in paise
        """
        return self.balance - self.held_balance


class IdempotencyKey(models.Model):
    """
    Tracks idempotency keys for API requests to prevent duplicate operations.
    Keys expire after 24 hours.
    """
    key = models.CharField(max_length=255, unique=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='idempotency_keys')
    request_path = models.CharField(max_length=500)
    request_method = models.CharField(max_length=10)
    response_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'idempotency_keys'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['merchant', 'key']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = ['merchant', 'key']

    def __str__(self):
        return f"{self.merchant.name} - {self.key}"

    @property
    def is_expired(self):
        """Check if the idempotency key has expired"""
        return timezone.now() > self.expires_at

    @classmethod
    def cleanup_expired(cls):
        """Remove expired idempotency keys"""
        return cls.objects.filter(expires_at__lt=timezone.now()).delete()


class LedgerEntry(models.Model):
    """
    Represents a ledger entry for a merchant (credit or debit).
    Amount is stored in paise (smallest currency unit).
    """
    ENTRY_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    id = models.BigAutoField(primary_key=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='ledger_entries')
    type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    amount_paise = models.BigIntegerField()  # Amount in paise (1 rupee = 100 paise)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ledger_entries'
        indexes = [
            models.Index(fields=['merchant', 'created_at']),
            models.Index(fields=['type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.merchant.name} - {self.type} - {self.amount_paise} paise"


class Payout(models.Model):
    """
    Represents a payout from merchant account to their bank account.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.BigAutoField(primary_key=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='payouts')
    idempotency_key = models.CharField(max_length=255, unique=True)
    amount_paise = models.BigIntegerField()  # Amount in paise
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempt_count = models.IntegerField(default=0)
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payouts'
        indexes = [
            models.Index(fields=['merchant', 'status']),
            models.Index(fields=['idempotency_key']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout {self.id} - {self.merchant.name} - {self.status}"
