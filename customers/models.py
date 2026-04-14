import secrets
from django.db import models
from farms.models import Farm


class Customer(models.Model):
    phone      = models.CharField(max_length=20, unique=True)
    email      = models.EmailField(blank=True)
    first_name = models.CharField(max_length=60, blank=True)
    token      = models.CharField(max_length=64, unique=True, blank=True,
                                  help_text='UUID — lets customer access orders without login')
    joined     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-joined']

    def __str__(self):
        return self.first_name or self.phone

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class FulfillmentPreference(models.Model):
    """Ordered farm preferences for a customer (primary=1, secondary=2, tertiary=3)."""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='preferences')
    farm     = models.ForeignKey(Farm, on_delete=models.CASCADE)
    priority = models.PositiveSmallIntegerField(choices=[(1,'Primary'),(2,'Secondary'),(3,'Tertiary')])

    class Meta:
        unique_together = ('customer', 'farm')
        ordering        = ['customer', 'priority']

    def __str__(self):
        return f"{self.customer} → {self.farm.name} (#{self.priority})"
