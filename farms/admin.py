from django.contrib import admin
from .models import Farm, CachedProduct, MarketListing


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'location', 'is_active', 'last_synced')
    list_filter   = ('is_active',)
    search_fields = ('name', 'slug', 'location')
    readonly_fields = ('joined', 'last_synced')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CachedProduct)
class CachedProductAdmin(admin.ModelAdmin):
    list_display  = ('name', 'farm', 'category', 'external_id')
    list_filter   = ('farm', 'category')
    search_fields = ('name', 'farm__name')
    readonly_fields = ('last_synced',)


@admin.register(MarketListing)
class MarketListingAdmin(admin.ModelAdmin):
    list_display  = ('product', 'farm', 'market_date', 'quantity_available', 'price', 'unit_label')
    list_filter   = ('farm', 'market_date')
    search_fields = ('product__name', 'farm__name')
    readonly_fields = ('last_synced',)
    date_hierarchy = 'market_date'
