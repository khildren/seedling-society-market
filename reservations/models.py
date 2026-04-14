import secrets
from django.db import models
from customers.models import Customer
from farms.models import Farm, MarketListing


class Order(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PARTIAL   = 'partial'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES   = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PARTIAL,   'Partial — some items unavailable'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    customer    = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    market_date = models.DateField()
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    order_token = models.CharField(max_length=64, unique=True, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} — {self.customer} — {self.market_date}"

    def save(self, *args, **kwargs):
        if not self.order_token:
            self.order_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum(i.subtotal for i in self.items.all())


class OrderItem(models.Model):
    STATUS_PENDING     = 'pending'
    STATUS_HELD        = 'held'
    STATUS_CONFIRMED   = 'confirmed'
    STATUS_UNAVAILABLE = 'unavailable'
    STATUS_CHOICES     = [
        (STATUS_PENDING,     'Pending'),
        (STATUS_HELD,        'Held at farm'),
        (STATUS_CONFIRMED,   'Confirmed'),
        (STATUS_UNAVAILABLE, 'Unavailable'),
    ]
    order              = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    listing            = models.ForeignKey(MarketListing, on_delete=models.PROTECT)
    fulfillment_farm   = models.ForeignKey(Farm, on_delete=models.PROTECT)
    quantity_requested = models.PositiveIntegerField()
    quantity_fulfilled = models.PositiveIntegerField(default=0)
    status             = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"{self.quantity_requested}x {self.listing.product.name} from {self.fulfillment_farm.name}"

    @property
    def subtotal(self):
        return self.quantity_fulfilled * self.listing.price
