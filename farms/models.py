from django.db import models


class Farm(models.Model):
    name          = models.CharField(max_length=120)
    slug          = models.SlugField(unique=True)
    bio           = models.TextField(blank=True)
    location      = models.CharField(max_length=200, blank=True)
    image_url     = models.URLField(blank=True)
    api_url       = models.URLField(help_text='Base URL of farm Django instance e.g. https://raggedgloryfarm.com')
    api_key       = models.CharField(max_length=128, blank=True, help_text='Future auth — leave blank for now')
    is_active     = models.BooleanField(default=True)
    contact_name  = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    joined        = models.DateTimeField(auto_now_add=True)
    last_synced   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def api(self, path):
        return f"{self.api_url.rstrip('/')}/api/v1/{path.lstrip('/')}"


class CachedProduct(models.Model):
    CATEGORY_CHOICES = [
        ('eggs',     'Eggs'),
        ('veg',      'Vegetables'),
        ('fruit',    'Fruit'),
        ('bread',    'Bread & Baked'),
        ('preserve', 'Preserves'),
        ('other',    'Other'),
    ]
    farm        = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='products')
    external_id = models.PositiveIntegerField()
    name        = models.CharField(max_length=120)
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    image_url   = models.URLField(blank=True)
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'external_id')
        ordering        = ['category', 'name']

    def __str__(self):
        return f"{self.farm.name} — {self.name}"


class MarketListing(models.Model):
    farm               = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='listings')
    product            = models.ForeignKey(CachedProduct, on_delete=models.CASCADE, related_name='listings')
    market_date        = models.DateField()
    quantity_available = models.PositiveIntegerField(default=0)
    price              = models.DecimalField(max_digits=8, decimal_places=2)
    unit_label         = models.CharField(max_length=40, default='each')
    menu_entry_id      = models.PositiveIntegerField()
    location_note      = models.CharField(max_length=200, blank=True)
    market_address     = models.CharField(max_length=300, blank=True)
    last_synced        = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'menu_entry_id')
        ordering        = ['market_date', 'product__category', 'product__name']

    def __str__(self):
        return f"{self.farm.name} — {self.product.name} ({self.market_date})"
