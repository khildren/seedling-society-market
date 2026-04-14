from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model   = OrderItem
    extra   = 0
    fields  = ('listing', 'fulfillment_farm', 'quantity_requested', 'quantity_fulfilled', 'status')
    readonly_fields = ('quantity_fulfilled', 'status')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'customer', 'market_date', 'status', 'created_at')
    list_filter     = ('status', 'market_date')
    search_fields   = ('customer__phone', 'customer__first_name', 'order_token')
    readonly_fields = ('order_token', 'created_at', 'updated_at')
    inlines         = [OrderItemInline]
    date_hierarchy  = 'market_date'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display  = ('pk', 'order', 'listing', 'fulfillment_farm', 'quantity_requested', 'quantity_fulfilled', 'status')
    list_filter   = ('status', 'fulfillment_farm')
    search_fields = ('order__order_token', 'listing__product__name')
