from django.contrib import admin
from .models import MessageThread, Message, FarmReplyToken


class MessageInline(admin.TabularInline):
    model  = Message
    extra  = 0
    fields = ('sender_type', 'body', 'sent_at', 'read_at')
    readonly_fields = ('sent_at', 'read_at')


class FarmReplyTokenInline(admin.TabularInline):
    model  = FarmReplyToken
    extra  = 0
    fields = ('token', 'created_at', 'expires_at', 'used_at')
    readonly_fields = ('token', 'created_at', 'expires_at', 'used_at')


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'farm', 'customer', 'order', 'created_at')
    list_filter     = ('farm',)
    search_fields   = ('customer__phone', 'farm__name')
    readonly_fields = ('created_at',)
    inlines         = [MessageInline, FarmReplyTokenInline]


@admin.register(FarmReplyToken)
class FarmReplyTokenAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'thread', 'created_at', 'expires_at', 'used_at')
    list_filter     = ('used_at',)
    readonly_fields = ('token', 'created_at', 'expires_at', 'used_at')
