from django.contrib import admin
from django.urls import path

from customers import views as customer_views
from reservations import views as reservation_views
from messaging import views as messaging_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Auth / customer entry ───────────────────────────────────────────────
    path('',               customer_views.lookup,       name='lookup'),
    path('logout/',        customer_views.logout_view,  name='logout'),

    # ── Customer dashboard & preferences ───────────────────────────────────
    path('my/',            customer_views.dashboard,    name='dashboard'),
    path('my/preferences/', customer_views.preferences, name='preferences'),

    # ── Browse & cart ───────────────────────────────────────────────────────
    path('market/',                            reservation_views.browse,      name='browse'),
    path('market/<str:market_date>/',          reservation_views.market_day,  name='market_day'),
    path('market/<str:market_date>/add/',      reservation_views.cart_add,    name='cart_add'),
    path('cart/',                              reservation_views.cart_view,   name='cart'),
    path('cart/remove/',                       reservation_views.cart_remove, name='cart_remove'),
    path('cart/place/',                        reservation_views.place_order, name='place_order'),

    # ── Order detail ────────────────────────────────────────────────────────
    path('orders/<str:order_token>/',          reservation_views.order_detail, name='order_detail'),

    # ── Messaging ───────────────────────────────────────────────────────────
    path('my/messages/',                       messaging_views.thread_list,   name='thread_list'),
    path('my/messages/<int:thread_id>/',       messaging_views.thread_detail, name='thread_detail'),
    path('my/messages/<int:thread_id>/send/',  messaging_views.customer_send, name='customer_send'),
    path('reply/<str:token>/',                 messaging_views.farm_reply,    name='farm_reply'),
]
