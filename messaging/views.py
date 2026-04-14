"""
Messaging views.

Two actors:
  Customer — browses threads at /my/messages/, replies via web form.
  Farm     — receives SMS notification; replies via single-use token URL
             (no farm login required for MVP).
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone

from customers.views import _require_customer
from .models import MessageThread, Message, FarmReplyToken

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Customer: thread list
# ---------------------------------------------------------------------------

def thread_list(request):
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    threads = (
        MessageThread.objects
        .filter(customer=customer)
        .select_related('farm', 'order')
        .prefetch_related('messages')
        .order_by('-created_at')
    )
    return render(request, 'messaging/thread_list.html', {
        'customer': customer,
        'threads':  threads,
    })


# ---------------------------------------------------------------------------
# Customer: thread detail + send
# ---------------------------------------------------------------------------

def thread_detail(request, thread_id):
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    thread = get_object_or_404(MessageThread, pk=thread_id, customer=customer)
    msgs   = thread.messages.order_by('sent_at')

    # Mark unread messages (from farm) as read
    msgs.filter(sender_type=Message.SENDER_FARM, read_at__isnull=True).update(read_at=timezone.now())

    return render(request, 'messaging/thread_detail.html', {
        'customer': customer,
        'thread':   thread,
        'messages': msgs,
    })


@require_POST
def customer_send(request, thread_id):
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    thread = get_object_or_404(MessageThread, pk=thread_id, customer=customer)
    body   = request.POST.get('body', '').strip()

    if not body:
        messages.error(request, 'Message cannot be empty.')
        return redirect('thread_detail', thread_id=thread_id)

    Message.objects.create(
        thread=thread,
        sender_type=Message.SENDER_CUSTOMER,
        body=body,
    )

    # TODO: send SMS notification to farm (Phase 2 — Twilio)
    logger.info('Customer %s sent message on thread %s', customer.pk, thread.pk)

    return redirect('thread_detail', thread_id=thread_id)


# ---------------------------------------------------------------------------
# Farm reply via token URL (SMS magic link)
# ---------------------------------------------------------------------------

def farm_reply(request, token):
    """
    Tokenized URL sent to farm via SMS.
    GET  → show the thread + reply form
    POST → save message, mark token used, render confirmation
    """
    reply_token = get_object_or_404(FarmReplyToken, token=token)

    if not reply_token.is_valid:
        return render(request, 'messaging/token_expired.html', {'token': reply_token})

    thread = reply_token.thread
    msgs   = thread.messages.order_by('sent_at')

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if not body:
            messages.error(request, 'Message cannot be empty.')
            return render(request, 'messaging/farm_reply.html', {
                'thread':       thread,
                'messages':     msgs,
                'reply_token':  reply_token,
            })

        Message.objects.create(
            thread=thread,
            sender_type=Message.SENDER_FARM,
            body=body,
        )

        reply_token.used_at = timezone.now()
        reply_token.save(update_fields=['used_at'])

        # TODO: send SMS to customer notifying of farm reply (Phase 2 — Twilio)
        logger.info('Farm replied on thread %s via token', thread.pk)

        return render(request, 'messaging/farm_reply_sent.html', {'thread': thread})

    return render(request, 'messaging/farm_reply.html', {
        'thread':      thread,
        'messages':    msgs,
        'reply_token': reply_token,
    })
