from decimal import Decimal

import stripe
from django.conf import settings

from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from myapp.models import (
    Cart,
    Address,
    Order,
    OrderItem,
)

from myapp.utils import (
    calculate_offer_price,
    calculate_discount_amount,
    calculate_order_total,
)

from .services import StripeService


stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):

    address_id = request.data.get("address")

    if not address_id:

        return Response(
            {
                "message": "Address is required"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        address = Address.objects.get(
            id=address_id,
            user=request.user
        )

    except Address.DoesNotExist:

        return Response(
            {
                "message": "Invalid address"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    cart_items = Cart.objects.filter(
        user=request.user
    ).select_related(
        "variant",
        "variant__product",
        "variant__product__offer",
        "variant_size",
    )

    if not cart_items.exists():

        return Response(
            {
                "message": "Cart is empty"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    subtotal = Decimal("0.00")

    discount = Decimal("0.00")

    line_items = []

    for item in cart_items:

        # Stock Check Before Payment
        if item.variant_size.stock < item.quantity:

            return Response(
                {
                    "message": f"{item.variant.product.name} has only {item.variant_size.stock} item(s) left."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        original_price = Decimal(
            str(item.variant_size.price)
        )

        offer_price = calculate_offer_price(
            original_price,
            item.variant.product.offer
        )

        discount += (
            calculate_discount_amount(
                original_price,
                item.variant.product.offer
            ) * item.quantity
        )

        subtotal += (
            offer_price *
            item.quantity
        )

        line_items.append(
            {
                "price_data": {

                    "currency": "nzd",

                    "product_data": {
                        "name": item.variant.product.name,
                    },

                    "unit_amount": int(
                        offer_price * 100
                    ),
                },

                "quantity": item.quantity,
            }
        )

    totals = calculate_order_total(
        subtotal
    )

    if totals["shipping"] > 0:

        line_items.append(
            {
                "price_data": {

                    "currency": "nzd",

                    "product_data": {
                        "name": "Shipping",
                    },

                    "unit_amount": int(
                        totals["shipping"] * 100
                    ),
                },

                "quantity": 1,
            }
        )

    order = Order.objects.create(

        user=request.user,

        address=address,

        subtotal=totals["subtotal"],

        shipping_charge=totals["shipping"],

        discount_amount=discount,

        total_amount=totals["total"],

        payment_status="Pending",

        status="Pending",
    )

    session = StripeService.create_checkout_session(

        line_items=line_items,

        success_url=(
            "http://www.amora.nz/payment-success"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),

        cancel_url=(
            "http://www.amora.nz/payment-cancel"
        ),
    )

    order.stripe_session_id = session.id

    order.save()

    return Response(
        {
            "checkout_url": session.url,
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_success(request):

    session_id = request.GET.get("session_id")

    if not session_id:

        return Response(
            {
                "message": "Session ID is required"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        session = stripe.checkout.Session.retrieve(
            session_id
        )

    except Exception:

        return Response(
            {
                "message": "Invalid session"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        order = Order.objects.get(
            stripe_session_id=session.id,
            user=request.user
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message": "Order not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if session.payment_status != "paid":

        return Response(
            {
                "message": "Payment not completed"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Prevent duplicate processing
    if order.payment_status == "Paid":

        return Response(
            {
                "message": "Payment already verified"
            }
        )

    cart_items = Cart.objects.filter(
        user=request.user
    ).select_related(
        "variant",
        "variant__product",
        "variant__product__offer",
        "variant_size",
        "variant_size__size",
    )

    if not cart_items.exists():

        order.payment_status = "Paid"

        order.status = "Confirmed"

        order.save()

        return Response(
            {
                "message": "Payment successful"
            }
        )

    for item in cart_items:

        original_price = Decimal(
            str(item.variant_size.price)
        )

        offer_price = calculate_offer_price(
            original_price,
            item.variant.product.offer
        )

        discount_amount = calculate_discount_amount(
            original_price,
            item.variant.product.offer
        )

        OrderItem.objects.create(

            order=order,

            product=item.variant.product,

            color=item.variant.color,

            size=item.variant_size.size,

            variant_size=item.variant_size,

            quantity=item.quantity,

            original_price=original_price,

            discount_amount=discount_amount,

            price=offer_price,

            total_price=offer_price * item.quantity,
        )

        item.variant_size.stock -= item.quantity

        item.variant_size.save()

    order.payment_status = "Paid"

    order.status = "Confirmed"

    order.save()

    cart_items.delete()

    return Response(
        {
            "message": "Payment successful"
        }
    )