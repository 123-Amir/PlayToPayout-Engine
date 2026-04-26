from rest_framework import serializers
from .models import Merchant, LedgerEntry, Payout, IdempotencyKey


class MerchantSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = ('id', 'name', 'bank_account_id', 'balance', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at', 'balance')

    def get_balance(self, obj):
        """Get the balance property"""
        return obj.balance


class IdempotencyKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = IdempotencyKey
        fields = ('key', 'merchant', 'request_path', 'request_method', 'response_data', 'created_at', 'expires_at')
        read_only_fields = ('created_at', 'expires_at')


class LedgerEntrySerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source='merchant.name', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = ('id', 'merchant', 'merchant_name', 'type', 'amount_paise', 'description', 'created_at')
        read_only_fields = ('id', 'created_at')


class PayoutSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source='merchant.name', read_only=True)

    class Meta:
        model = Payout
        fields = (
            'id', 'merchant', 'merchant_name', 'idempotency_key', 'amount_paise',
            'bank_account_id', 'status', 'attempt_count', 'reference_id',
            'failure_reason', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'attempt_count', 'created_at', 'updated_at', 'reference_id', 'failure_reason')

    def validate_idempotency_key(self, value):
        """Ensure idempotency key is unique"""
        if Payout.objects.filter(idempotency_key=value).exists():
            raise serializers.ValidationError(
                "A payout with this idempotency key already exists."
            )
        return value

    def validate_amount_paise(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class PayoutCreateSerializer(serializers.Serializer):
    """
    Serializer for creating payouts with idempotency and balance checking.
    """
    merchant = serializers.IntegerField()
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)

    def validate_merchant(self, value):
        """Validate merchant exists"""
        try:
            merchant = Merchant.objects.get(id=value)
            return merchant
        except Merchant.DoesNotExist:
            raise serializers.ValidationError("Merchant not found")

    def validate_amount_paise(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
