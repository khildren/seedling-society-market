"""
Reservation views — browse listings, manage cart, place orders.

Cart is stored in the session as:
  session['cart'] = {
      '<listing_id>': {'quantity': int, 'market_date': 'YYYY-MM-DD'},
      ...
  }
"""
import logging
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST

from farms.models import MarketListing
from customers.views import _require_customer
from .models import Order, OrderItem
from .fulfillment import fulfill_order

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------

def browse(request):
    """Show upcoming market dates that have available inventory."""
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    today = date.today()
    dates = (
        MarketListing.objects
        .filter(market_date__gte=today, quantity_available__gt=0)
        .values_list('market_date', flat=True)
        .distinct()
        .order_by('market_date')
    )
    return render(request, 'reservations/browse.html', {
        'customer':     customer,
        'market_dates': dates,
    })


def market_day(request, market_date):
    """List all available products for a given market date, grouped by category."""
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    listings = (
        MarketListing.objects
        .filter(market_date=market_date, quantity_available__gt=0)
        .select_related('farm', 'product')
        .order_by('product__category', 'product__name', 'farm__name')
    )

    grouped = {}
    for listing in listings:
        cat = listing.product.get_category_display()
        grouped.setdefault(cat, []).append(listing)

    cart = request.session.get('cart', {})

    return render(request, 'reservations/market_day.html', {
        'customer':    customer,
        'market_date': market_date,
        'grouped':     grouped,
        'cart':        cart,
    })


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

@require_POST
def cart_add(request, market_date):
    """Add or update an item in the session cart."""
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    listing_id = request.POST.get('listing_id', '')
    try:
        qty = max(0, int(request.POST.get('quantity', 1)))
    except ValueError:
        qty = 1

    if not listing_id:
        return redirect('market_day', market_date=market_date)

    try:
        listing = MarketListing.objects.get(pk=listing_id, market_date=market_date)
    except MarketListing.DoesNotExist:
        messages.error(request, 'That item is no longer available.')
        return redirect('market_day', market_date=market_date)

    cart = request.session.get('cart', {})
    if qty == 0:
        cart.pop(str(listing_id), None)
    else:
        qty = min(qty, listing.quantity_available)
        cart[str(listing_id)] = {'quantity': qty, 'market_date': str(market_date)}

    request.session['cart'] = cart
    request.session.modified = True
    return redirect('market_day', market_date=market_date)


def cart_view(request):
    """Review cart contents before placing order."""
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    cart = request.session.get('cart', {})
    items = []
    total = 0
    market_date = None

    for listing_id, entry in list(cart.items()):
        try:
            listing = MarketListing.objects.select_related('farm', 'product').get(pk=listing_id)
        except MarketListing.DoesNotExist:
            cart.pop(listing_id)
            continue
        qty      = entry['quantity']
        subtotal = listing.price * qty
        total   += subtotal
        market_date = listing.market_date
        items.append({'listing': listing, 'quantity': qty, 'subtotal': subtotal})

    request.session['cart'] = cart
    request.session.modified = True

    return render(request, 'reservations/cart.html', {
        'customer':    customer,
        'items':       items,
        'total':       total,
        'market_date': market_date,
    })


@require_POST
def cart_remove(request):
    """Remove a single item from the cart."""
    listing_id = request.POST.get('listing_id', '')
    cart = request.session.get('cart', {})
    cart.pop(str(listing_id), None)
    request.session['cart'] = cart
    request.session.modified = True
    return redirect('cart')


# ---------------------------------------------------------------------------
# Place order
# ---------------------------------------------------------------------------

@require_POST
def place_order(request):
    """Convert session cart into Order + OrderItems, then run fulfillment."""
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'Your cart is empty.')
        return redirect('browse')

    first_entry = next(iter(cart.values()))
    market_date = first_entry['market_date']
    notes = request.POST.get('notes', '').strip()

    order = Order.objects.create(
        customer=customer,
        market_date=market_date,
        notes=notes,
        status=Order.STATUS_PENDING,
    )

    for listing_id, entry in cart.items():
        try:
            listing = MarketListing.objects.select_related('farm').get(pk=listing_id)
        except MarketListing.DoesNotExist:
            continue
        OrderItem.objects.create(
            order=order,
            listing=listing,
            fulfillment_farm=listing.farm,   # default; fulfillment engine may override
            quantity_requested=entry['quantity'],
        )

    if not order.items.exists():
        order.delete()
        messages.error(request, 'None of the items in your cart were available.')
        return redirect('browse')

    fulfill_order(order)

    # Notify customer of outcome via SMS
    from messaging.sms import send_order_confirmation
    send_order_confirmation(request, order)

    request.session.pop('cart', None)
    request.session.modified = True

    return redirect('order_detail', order_token=order.order_token)


# ---------------------------------------------------------------------------
# Order detail
# ---------------------------------------------------------------------------

def order_detail(request, order_token):
    """Public order status page — accessible by anyone with the token URL."""
    order = get_object_or_404(Order, order_token=order_token)
    items = order.items.select_related('listing__product', 'listing__farm', 'fulfillment_farm')

    # Distinct farms that actually fulfilled items (for message forms)
    farms_fulfilled = list({
        item.fulfillment_farm
        for item in items
        if item.fulfillment_farm_id and item.quantity_fulfilled > 0
    })

    return render(request, 'reservations/order_detail.html', {
        'order':           order,
        'items':           items,
        'farms_fulfilled': farms_fulfilled,
    })
