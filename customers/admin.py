from django.contrib import admin
from .models import Customer, FulfillmentPreference


class FulfillmentPreferenceInline(admin.TabularInline):
    model  = FulfillmentPreference
    extra  = 0
    fields = ('priority', 'farm')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display   = ('phone', 'first_name', 'email', 'joined')
    search_fields  = ('phone', 'first_name', 'email')
    readonly_fields = ('token', 'joined')
    inlines        = [FulfillmentPreferenceInline]
