from django.contrib import admin

from .models import BalanceAccount, BalanceMovement, DailyBalance


@admin.register(BalanceAccount)
class BalanceAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'broker', 'broker_moneyorder', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('order', 'name')


@admin.register(DailyBalance)
class DailyBalanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'account', 'initial_balance', 'company_balance')
    list_filter = ('date', 'account', 'user')
    date_hierarchy = 'date'
    autocomplete_fields = ('account',)


@admin.register(BalanceMovement)
class BalanceMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'movement_type', 'amount', 'from_user', 'to_user', 'account')
    list_filter = ('date', 'movement_type', 'account')
    date_hierarchy = 'date'
    search_fields = ('description',)
    autocomplete_fields = ('account',)
