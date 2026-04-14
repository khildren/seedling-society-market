import secrets
from django.db import models
from django.utils import timezone
from customers.models import Customer
from farms.models import Farm
from reservations.models import Order


class MessageThread(models.Model):
    order      = models.ForeignKey(Order, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='threads')
    farm       = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='threads')
    customer   = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='threads')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Thread #{self.pk} — {self.farm.name} / {self.customer}"


class Message(models.Model):
    SENDER_FARM     = 'farm'
    SENDER_CUSTOMER = 'customer'
    SENDER_CHOICES  = [
        (SENDER_FARM,     'Farm'),
        (SENDER_CUSTOMER, 'Customer'),
    ]
    thread      = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    body        = models.TextField()
    sent_at     = models.DateTimeField(auto_now_add=True)
    read_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender_type} @ {self.sent_at:%Y-%m-%d %H:%M}"

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=['read_at'])


class FarmReplyToken(models.Model):
    """Single-use tokenized reply link sent to farmers via SMS."""
    thread     = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='reply_tokens')
    token      = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=72)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return not self.used_at and timezone.now() < self.expires_at

    def __str__(self):
        return f"ReplyToken for Thread #{self.thread_id} ({'used' if self.used_at else 'active'})"
