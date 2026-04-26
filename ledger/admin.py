from django.contrib import admin
from .models import Merchant, LedgerEntry, Payout


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'bank_account_id', 'created_at')
    search_fields = ('name', 'bank_account_id')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'bank_account_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'type', 'amount_paise', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('merchant__name', 'description')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Entry Information', {
            'fields': ('merchant', 'type', 'amount_paise')
        }),
        ('Details', {
            'fields': ('description', 'created_at')
        }),
    )


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'amount_paise', 'status', 'attempt_count', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('merchant__name', 'idempotency_key', 'bank_account_id')
    readonly_fields = ('created_at', 'updated_at', 'attempt_count')
    fieldsets = (
        ('Payout Information', {
            'fields': ('merchant', 'amount_paise', 'bank_account_id', 'idempotency_key')
        }),
        ('Status & Attempts', {
            'fields': ('status', 'attempt_count', 'reference_id', 'failure_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
