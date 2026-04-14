import logging
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.utils import timezone

from .models import Farm, CachedProduct, MarketListing

logger = logging.getLogger(__name__)


def _run_sync(farm):
    """Run sync for a single farm. Returns (success, message)."""
    from farms.management.commands.sync_farms import Command
    try:
        cmd = Command()
        cmd._sync_farm(farm)
        farm.last_synced = timezone.now()
        farm.save(update_fields=['last_synced'])
        return True, f'{farm.name} synced successfully.'
    except Exception as e:
        logger.exception('Admin sync failed for %s', farm.slug)
        return False, f'{farm.name} sync failed: {e}'


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display    = ('name', 'slug', 'location', 'is_active', 'last_synced', 'sync_button')
    list_filter     = ('is_active',)
    search_fields   = ('name', 'slug', 'location')
    readonly_fields = ('joined', 'last_synced')
    prepopulated_fields = {'slug': ('name',)}
    actions         = ['sync_selected']

    # ── Custom list column: per-row sync button ────────────────────────────

    def sync_button(self, obj):
        from django.utils.html import format_html
        url = f'../farm/{obj.pk}/sync/'
        return format_html(
            '<a class="button" href="{}">Sync now</a>', url
        )
    sync_button.short_description = 'Sync'
    sync_button.allow_tags = True

    # ── Admin action: sync selected ────────────────────────────────────────

    @admin.action(description='Sync selected farms from their APIs')
    def sync_selected(self, request, queryset):
        ok = fail = 0
        for farm in queryset.filter(is_active=True):
            success, msg = _run_sync(farm)
            if success:
                ok += 1
                self.message_user(request, msg, messages.SUCCESS)
            else:
                fail += 1
                self.message_user(request, msg, messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} farm(s) synced.', messages.SUCCESS)

    # ── Extra URL: /admin/farms/farm/<pk>/sync/ ────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:farm_id>/sync/', self.admin_site.admin_view(self.sync_one_view), name='farm_sync_one'),
            path('sync-all/',           self.admin_site.admin_view(self.sync_all_view),  name='farm_sync_all'),
        ]
        return custom + urls

    def sync_one_view(self, request, farm_id):
        try:
            farm = Farm.objects.get(pk=farm_id)
        except Farm.DoesNotExist:
            self.message_user(request, 'Farm not found.', messages.ERROR)
            return redirect('..')
        success, msg = _run_sync(farm)
        level = messages.SUCCESS if success else messages.ERROR
        self.message_user(request, msg, level)
        return redirect('../../')

    def sync_all_view(self, request):
        ok = fail = 0
        for farm in Farm.objects.filter(is_active=True):
            success, msg = _run_sync(farm)
            if success:
                ok += 1
            else:
                fail += 1
                self.message_user(request, msg, messages.ERROR)
        self.message_user(request, f'Sync complete — {ok} succeeded, {fail} failed.', messages.SUCCESS)
        return redirect('../')

    # ── Inject "Sync All" button into the changelist header ───────────────

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['sync_all_url'] = 'sync-all/'
        return super().changelist_view(request, extra_context=extra_context)


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
