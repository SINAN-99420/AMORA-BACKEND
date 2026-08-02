import stripe
from django.conf import settings


stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:

    @staticmethod
    def create_checkout_session(
        line_items,
        success_url,
        cancel_url,
        metadata=None,
    ):

        session = stripe.checkout.Session.create(

            payment_method_types=[
                "card"
            ],

            mode="payment",

            line_items=line_items,

            success_url=success_url,

            cancel_url=cancel_url,

            metadata=metadata or {},

        )

        return session