from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid
import logging

from .models import Merchant, LedgerEntry, Payout, IdempotencyKey
from .serializers import MerchantSerializer, LedgerEntrySerializer, PayoutSerializer, PayoutCreateSerializer

logger = logging.getLogger(__name__)


class MerchantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing merchants.
    """
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer
    permission_classes = [AllowAny]  # Allow for testing
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'bank_account_id']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get merchant balance details"""
        merchant = self.get_object()
        return Response({
            'id': merchant.id,
            'name': merchant.name,
            'available_balance': merchant.available_balance,
            'held_balance': merchant.held_balance,
            'total_balance': merchant.balance
        })


class LedgerEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ledger entries.
    """
    queryset = LedgerEntry.objects.all()
    serializer_class = LedgerEntrySerializer
    permission_classes = [AllowAny]  # Allow for testing
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['type', 'merchant']
    search_fields = ['merchant__name', 'description']
    ordering_fields = ['created_at', 'amount_paise']
    ordering = ['-created_at']


class PayoutViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payouts with idempotency and concurrency handling.
    """
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer
    permission_classes = [AllowAny]  # Allow for testing
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'merchant', 'created_at']
    search_fields = ['merchant__name', 'idempotency_key']
    ordering_fields = ['created_at', 'amount_paise', 'status']
    ordering = ['-created_at']

    def create(self, request, *args, **kwargs):
        """
        Create payout with idempotency and atomic balance checking.
        
        Requirements:
        - Idempotency-Key header (UUID)
        - 24hr key expiration
        - Atomic balance check + hold (SELECT FOR UPDATE)
        - Transactional: balance debit + payout pending
        - Response: {"payout_id": "", "status": "pending", "balance_after": xxx}
        """
        # Validate Idempotency-Key header
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response(
                {'detail': 'Idempotency-Key header is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate UUID format
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            return Response(
                {'detail': 'Idempotency-Key must be a valid UUID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use PayoutCreateSerializer for input validation
        serializer = PayoutCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        merchant = serializer.validated_data['merchant']
        amount_paise = serializer.validated_data['amount_paise']
        bank_account_id = serializer.validated_data['bank_account_id']
        
        # Check for existing idempotency key
        existing_key = IdempotencyKey.objects.filter(
            key=idempotency_key,
            merchant=merchant
        ).first()
        
        if existing_key:
            if existing_key.is_expired:
                # Clean up expired key and allow new request
                existing_key.delete()
            else:
                # Return cached response
                return Response(existing_key.response_data, status=status.HTTP_200_OK)
        
        # Atomic transaction: balance check + debit + payout creation
        try:
            with transaction.atomic():
                # Lock merchant for balance check and update
                merchant_locked = Merchant.objects.select_for_update().get(id=merchant.id)
                
                # Calculate current balance
                current_balance = merchant_locked.balance
                
                # Check if sufficient balance
                if current_balance < amount_paise:
                    response_data = {
                        'detail': 'Insufficient balance',
                        'current_balance': current_balance,
                        'requested_amount': amount_paise
                    }
                    
                    # Store idempotency key with error response
                    IdempotencyKey.objects.create(
                        key=idempotency_key,
                        merchant=merchant,
                        request_path=request.path,
                        request_method=request.method,
                        response_data=response_data,
                        expires_at=timezone.now() + timedelta(hours=24)
                    )
                    
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
                # Create debit ledger entry (holds the balance)
                debit_entry = LedgerEntry.objects.create(
                    merchant=merchant,
                    type='debit',
                    amount_paise=amount_paise,
                    description=f'Payout debit - Idempotency: {idempotency_key}'
                )
                
                # Create payout with pending status
                payout = Payout.objects.create(
                    merchant=merchant,
                    idempotency_key=idempotency_key,
                    amount_paise=amount_paise,
                    bank_account_id=bank_account_id,
                    status='pending'
                )
                
                # Calculate balance after transaction
                balance_after = current_balance - amount_paise
                
                # Prepare response
                response_data = {
                    'payout_id': payout.id,
                    'status': 'pending',
                    'balance_after': balance_after
                }
                
                # Store idempotency key with success response
                IdempotencyKey.objects.create(
                    key=idempotency_key,
                    merchant=merchant,
                    request_path=request.path,
                    request_method=request.method,
                    response_data=response_data,
                    expires_at=timezone.now() + timedelta(hours=24)
                )
                
                logger.info(f"Payout created: {payout.id}, Merchant: {merchant.name}, Amount: {amount_paise} paise")
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error creating payout: {e}")
            return Response(
                {'detail': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry a failed or pending payout.
        Resets attempt_count to allow immediate retry with exponential backoff.
        """
        payout = self.get_object()
        
        if payout.status not in ['failed', 'pending', 'processing']:
            return Response(
                {'detail': 'Only failed, pending, or processing payouts can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset to pending and trigger processing
        payout.status = 'pending'
        payout.attempt_count = 0
        payout.failure_reason = None
        payout.reference_id = None
        payout.save()
        
        # Import here to avoid circular imports
        from .tasks import process_payout_task
        process_payout_task.delay(payout.id)
        
        return Response(
            {
                'detail': 'Payout queued for retry',
                'payout': self.get_serializer(payout).data
            },
            status=status.HTTP_200_OK
        )
