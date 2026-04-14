"""
python manage.py sync_farms

Pulls market dates + inventory from all active farm APIs and
updates CachedProduct and MarketListing records locally.
"""
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from farms.models import Farm, CachedProduct, MarketListing


class Command(BaseCommand):
    help = 'Sync inventory from all active farm APIs'

    def add_arguments(self, parser):
        parser.add_argument('--farm', type=str, help='Sync a single farm by slug')

    def handle(self, *args, **options):
        farms = Farm.objects.filter(is_active=True)
        if options['farm']:
            farms = farms.filter(slug=options['farm'])

        for farm in farms:
            self.stdout.write(f'Syncing {farm.name}...')
            try:
                self._sync_farm(farm)
                farm.last_synced = timezone.now()
                farm.save(update_fields=['last_synced'])
                self.stdout.write(self.style.SUCCESS(f'  ✓ {farm.name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {farm.name}: {e}'))

    def _sync_farm(self, farm):
        # Pull upcoming market dates
        resp = requests.get(farm.api('market-dates/'), timeout=10)
        resp.raise_for_status()
        dates = resp.json()

        for date_data in dates:
            date_id = date_data['id']
            # Pull full menu for each date
            menu_resp = requests.get(farm.api(f'menu/{date_id}/'), timeout=10)
            menu_resp.raise_for_status()
            menu = menu_resp.json()

            for item in menu.get('items', []):
                # Upsert CachedProduct
                product, _ = CachedProduct.objects.update_or_create(
                    farm=farm,
                    external_id=item['id'],
                    defaults={
                        'name':        item['product_name'],
                        'category':    item.get('category', 'other'),
                        'description': item.get('description', ''),
                        'image_url':   item.get('image_url') or '',
                    },
                )

                # Upsert MarketListing
                MarketListing.objects.update_or_create(
                    farm=farm,
                    menu_entry_id=item['id'],
                    defaults={
                        'product':            product,
                        'market_date':        date_data['date'],
                        'quantity_available': item['quantity_available'],
                        'price':              item['price'],
                        'unit_label':         item.get('unit_label', 'each'),
                        'location_note':      menu.get('location_note', ''),
                        'market_address':     menu.get('market_address', ''),
                    },
                )
