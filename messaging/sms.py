"""
Twilio SMS helpers.

All functions are no-ops (log only) if Twilio credentials are not configured
in settings. This lets the app run in dev/demo without credentials.

Required .env vars:
    TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_FROM_NUMBER=+18005551234
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _client():
    """Return a Twilio client or None if not configured."""
    sid   = getattr(settings, 'TWILIO_ACCOUNT_SID',  None)
    token = getattr(settings, 'TWILIO_AUTH_TOKEN',   None)
    if not sid or not token or 'placeholder' in (sid + token):
        return None
    try:
        from twilio.rest import Client
        return Client(sid, token)
    except Exception as e:
        logger.warning('Twilio client init failed: %s', e)
        return None


def send_sms(to_number, body):
    """
    Send a single SMS. Returns True on success, False otherwise.
    Logs the message body even when Twilio is not configured.

    TWILIO_FROM_NUMBER can be either:
      - A phone number (+15005550006) — uses from_=
      - A Messaging Service SID (MG...) — uses messaging_service_sid=
    """
    from_value = getattr(settings, 'TWILIO_FROM_NUMBER', None)
    client     = _client()

    if not client or not from_value:
        logger.info('[SMS stub] to=%s | %s', to_number, body)
        return False

    try:
        # Messaging Service SID starts with MG
        if from_value.startswith('MG'):
            msg = client.messages.create(
                body=body,
                messaging_service_sid=from_value,
                to=to_number,
            )
        else:
            msg = client.messages.create(body=body, from_=from_value, to=to_number)
        logger.info('SMS sent sid=%s to=%s', msg.sid, to_number)
        return True
    except Exception as e:
        logger.warning('SMS failed to=%s: %s', to_number, e)
        return False


# ---------------------------------------------------------------------------
# Named send helpers — one per event type
# ---------------------------------------------------------------------------

def send_magic_link(request, customer):
    """
    Send the customer a magic login link after they enter their phone number.
    """
    url  = request.build_absolute_uri(f'/?t={customer.token}')
    body = f'Seedling Society: tap to access your account — {url}'
    send_sms(customer.phone, body)


def send_order_confirmation(request, order):
    """
    Notify the customer of their order status after fulfillment runs.
    """
    url = request.build_absolute_uri(f'/orders/{order.order_token}/')
    status_phrase = {
        'confirmed': 'confirmed',
        'partial':   'partially filled (some items unavailable)',
        'cancelled': 'could not be filled — nothing available',
    }.get(order.status, order.status)

    body = (
        f'Seedling Society: your order for {order.market_date} '
        f'has been {status_phrase}. '
        f'Details: {url}'
    )
    send_sms(order.customer.phone, body)


def send_farm_reply_request(request, thread, reply_token):
    """
    Send the farm a one-time reply URL via SMS when a customer messages them.
    Only fires if the farm has a contact_phone set.
    """
    if not thread.farm.contact_phone:
        logger.info('Farm %s has no contact_phone — skipping SMS', thread.farm.slug)
        return

    url          = request.build_absolute_uri(f'/reply/{reply_token.token}/')
    last_msg     = thread.messages.filter(sender_type='customer').last()
    preview      = (last_msg.body[:60] + '…') if last_msg and len(last_msg.body) > 60 else (last_msg.body if last_msg else '')
    customer_name = thread.customer.first_name or 'A customer'

    body = (
        f'Seedling Society message from {customer_name}: '
        f'"{preview}" — Reply here (72h link): {url}'
    )
    send_sms(thread.farm.contact_phone, body)


def send_customer_reply_notification(request, thread):
    """
    Notify the customer when a farm replies to their message.
    """
    url  = request.build_absolute_uri(f'/my/messages/{thread.pk}/')
    body = f'Seedling Society: {thread.farm.name} replied to your message — {url}'
    send_sms(thread.customer.phone, body)
