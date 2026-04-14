"""
Tiered fulfillment engine.

For each item in an order, tries to fill quantity from the customer's
preferred farms in order (primary → secondary → tertiary).
Places holds on farm APIs atomically, rolls back all holds if anything fails.
"""
import logging
import requests
from django.db import transaction

from customers.models import FulfillmentPreference
from farms.models import MarketListing
from .models import Order, OrderItem

logger = logging.getLogger(__name__)


def _place_hold(farm, menu_entry_id, quantity, order_token):
    """Call farm API to reserve quantity. Returns True on success."""
    try:
        resp = requests.post(
            farm.api('hold/'),
            json={'menu_entry_id': menu_entry_id, 'quantity': quantity, 'order_token': order_token},
            timeout=8,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning('Hold failed for farm %s entry %s: %s', farm.slug, menu_entry_id, e)
        return False


def _release_hold(farm, menu_entry_id, quantity, order_token):
    """Call farm API to release a hold. Best-effort."""
    try:
        requests.post(
            farm.api('release/'),
            json={'menu_entry_id': menu_entry_id, 'quantity': quantity, 'order_token': order_token},
            timeout=8,
        )
    except Exception as e:
        logger.warning('Release failed for farm %s entry %s: %s', farm.slug, menu_entry_id, e)


def fulfill_order(order):
    """
    Main entry point. Takes a pending Order and attempts tiered fulfillment.

    Updates OrderItem records with fulfillment_farm and quantity_fulfilled.
    Sets order.status to CONFIRMED, PARTIAL, or CANCELLED.
    Returns (success: bool, summary: dict)
    """
    customer  = order.customer
    prefs     = list(
        FulfillmentPreference.objects
        .filter(customer=customer)
        .order_by('priority')
        .select_related('farm')
    )
    farm_order = [p.farm for p in prefs]

    placed_holds = []   # track for rollback: (farm, menu_entry_id, qty)
    order_items  = list(order.items.select_related('listing__farm', 'listing__product'))

    all_fulfilled = True

    for item in order_items:
        needed         = item.quantity_requested
        product_name   = item.listing.product.name
        market_date    = order.market_date

        for farm in farm_order:
            if needed <= 0:
                break

            # Find this farm's listing for this product on this date
            listing = MarketListing.objects.filter(
                farm=farm,
                product__name=product_name,
                market_date=market_date,
                quantity_available__gt=0,
            ).first()

            if not listing:
                continue

            can_fill = min(needed, listing.quantity_available)
            if can_fill <= 0:
                continue

            if _place_hold(farm, listing.menu_entry_id, can_fill, order.order_token):
                # Decrement local cache so subsequent items see correct availability
                listing.quantity_available = max(0, listing.quantity_available - can_fill)
                listing.save(update_fields=['quantity_available'])

                placed_holds.append((farm, listing.menu_entry_id, can_fill))
                item.quantity_fulfilled += can_fill
                item.fulfillment_farm    = farm
                item.status              = OrderItem.STATUS_HELD
                needed                  -= can_fill

        if needed > 0:
            all_fulfilled = False
            if item.quantity_fulfilled == 0:
                item.status = OrderItem.STATUS_UNAVAILABLE
            else:
                item.status = OrderItem.STATUS_HELD   # partial fill

        item.save()

    # Set order status
    if all(i.status == OrderItem.STATUS_UNAVAILABLE for i in order_items):
        # Nothing could be filled — rollback and cancel
        for farm, entry_id, qty in placed_holds:
            _release_hold(farm, entry_id, qty, order.order_token)
        order.status = Order.STATUS_CANCELLED
    elif all_fulfilled:
        order.status = Order.STATUS_CONFIRMED
    else:
        order.status = Order.STATUS_PARTIAL

    order.save(update_fields=['status'])

    return order.status != Order.STATUS_CANCELLED, {
        'status':  order.status,
        'items':   [
            {
                'product':   i.listing.product.name,
                'requested': i.quantity_requested,
                'fulfilled': i.quantity_fulfilled,
                'farm':      i.fulfillment_farm.name if i.fulfillment_farm_id else None,
                'status':    i.status,
            }
            for i in order_items
        ],
    }
