from django.urls import path
from .views import *

urlpatterns = [
    path(
        "create-checkout-session/",
        create_checkout_session,
        name="create_checkout_session",
    ),
    path(
    "payment-success/",
        payment_success,
        name="payment-success",
    ),
      path(
        "stripe-webhook/",
        stripe_webhook,
        name="stripe_webhook"
    ),
]