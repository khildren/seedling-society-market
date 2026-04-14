"""
Customer-facing views.

Auth model: no passwords. Customer enters phone → gets session cookie containing
their customer_id. A magic link (token) can also be passed in the URL for SMS flows.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from farms.models import Farm
from .models import Customer, FulfillmentPreference

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _get_customer(request):
    """Return authenticated Customer or None."""
    cid = request.session.get('customer_id')
    if cid:
        try:
            return Customer.objects.get(pk=cid)
        except Customer.DoesNotExist:
            request.session.pop('customer_id', None)
    # Also accept ?t=<token> in URL (for SMS magic links)
    token = request.GET.get('t')
    if token:
        try:
            c = Customer.objects.get(token=token)
            request.session['customer_id'] = c.pk
            return c
        except Customer.DoesNotExist:
            pass
    return None


def _require_customer(request):
    """Return customer or None if not authed (caller should redirect)."""
    return _get_customer(request)


# ---------------------------------------------------------------------------
# Lookup / entry point
# ---------------------------------------------------------------------------

def lookup(request):
    """
    GET  → show phone entry form
    POST → find-or-create customer, set session, redirect to dashboard
    """
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        if not phone:
            messages.error(request, 'Please enter your phone number.')
            return render(request, 'customers/lookup.html')

        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={'first_name': request.POST.get('first_name', '').strip()},
        )
        request.session['customer_id'] = customer.pk
        logger.info('Customer %s %s via lookup', customer.pk, 'created' if created else 'logged in')

        # Send magic link SMS so customer can return without re-entering phone
        from messaging.sms import send_magic_link
        send_magic_link(request, customer)

        return redirect('dashboard')

    # If already authed, go straight to dashboard
    if _get_customer(request):
        return redirect('dashboard')

    return render(request, 'customers/lookup.html')


def dashboard(request):
    """
    Customer home: upcoming orders + farm preferences.
    """
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    orders = customer.orders.select_related().prefetch_related('items__listing__product').order_by('-created_at')[:10]
    prefs  = list(
        FulfillmentPreference.objects
        .filter(customer=customer)
        .order_by('priority')
        .select_related('farm')
    )

    return render(request, 'customers/dashboard.html', {
        'customer': customer,
        'orders':   orders,
        'prefs':    prefs,
    })


# ---------------------------------------------------------------------------
# Farm preferences
# ---------------------------------------------------------------------------

@require_http_methods(['GET', 'POST'])
def preferences(request):
    """
    Let customer pick up to 3 farms in order of preference.
    GET  → show form with current prefs
    POST → save updated prefs
    """
    customer = _require_customer(request)
    if not customer:
        return redirect('lookup')

    farms = Farm.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        # Expect farm_1, farm_2, farm_3 in POST — 0 means "none"
        FulfillmentPreference.objects.filter(customer=customer).delete()
        for priority in (1, 2, 3):
            farm_id = request.POST.get(f'farm_{priority}', '0')
            try:
                farm_id = int(farm_id)
            except ValueError:
                continue
            if farm_id:
                try:
                    farm = Farm.objects.get(pk=farm_id, is_active=True)
                    FulfillmentPreference.objects.create(
                        customer=customer,
                        farm=farm,
                        priority=priority,
                    )
                except Farm.DoesNotExist:
                    pass
        messages.success(request, 'Farm preferences saved.')
        return redirect('dashboard')

    # Build current selections as {1: farm_id, 2: farm_id, 3: farm_id}
    prefs_qs = FulfillmentPreference.objects.filter(customer=customer)
    selected = {p.priority: p.farm_id for p in prefs_qs}

    return render(request, 'customers/preferences.html', {
        'customer': customer,
        'farms':    farms,
        'sel_1':    selected.get(1, 0),
        'sel_2':    selected.get(2, 0),
        'sel_3':    selected.get(3, 0),
    })


def logout_view(request):
    request.session.flush()
    return redirect('lookup')
