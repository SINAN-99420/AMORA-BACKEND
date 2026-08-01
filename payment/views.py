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
    OrderItem
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

    cart_items = (
        Cart.objects.filter(
            user=request.user
        )
        .select_related(
            "variant",
            "variant__product",
            "variant__product__offer",
            "variant_size",
        )
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

        discount_amount = calculate_discount_amount(
            original_price,
            item.variant.product.offer
        )

        subtotal += (
            offer_price *
            item.quantity
        )

        discount += (
            discount_amount *
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

    session = StripeService.create_checkout_session(

        line_items=line_items,

        success_url=(
            "http://localhost:5173/payment-success"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),

        cancel_url=(
            "http://localhost:5173/payment-cancel"
        ),

        metadata={

            "user_id": str(request.user.id),

            "address_id": str(address.id),

        }

    )

    return Response(

        {

            "checkout_url": session.url

        }

    )
    
from django.db import transaction


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@transaction.atomic
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

    if session.payment_status != "paid":

        return Response(
            {
                "message": "Payment not completed"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Prevent duplicate order creation

    existing_order = Order.objects.filter(
        stripe_session_id=session.id
    ).first()

    if existing_order:

        return Response(
            {
                "message": "Payment already verified"
            }
        )

    user_id = session.metadata["user_id"]

    address_id = session.metadata["address_id"]

    if not user_id or not address_id:

        return Response(
            {
                "message": "Session metadata missing"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        address = Address.objects.get(

            id=address_id,

            user_id=user_id

        )

    except Address.DoesNotExist:

        return Response(
            {
                "message": "Address not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    cart_items = (
        Cart.objects
        .filter(
            user_id=user_id
        )
        .select_related(
            "variant",
            "variant__product",
            "variant__product__offer",
            "variant__color",
            "variant_size",
            "variant_size__size",
        )
    )

    if not cart_items.exists():

        return Response(
            {
                "message": "Cart is empty"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    original_subtotal = Decimal("0.00")

    discount_total = Decimal("0.00")

    discounted_subtotal = Decimal("0.00")

    for item in cart_items:

        if item.quantity > item.variant_size.stock:

            return Response(
                {
                    "message":
                    f"Only {item.variant_size.stock} item(s) left for {item.variant.product.name}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        original_price = Decimal(
            str(item.variant_size.price)
        )

        discounted_price = calculate_offer_price(
            original_price,
            item.variant.product.offer
        )

        discount_amount = calculate_discount_amount(
            original_price,
            item.variant.product.offer
        )

        original_subtotal += (
            original_price *
            item.quantity
        )

        discount_total += (
            discount_amount *
            item.quantity
        )

        discounted_subtotal += (
            discounted_price *
            item.quantity
        )

    totals = calculate_order_total(
        discounted_subtotal
    )

    order = Order.objects.create(

        user_id=user_id,

        address=address,

        subtotal=original_subtotal,

        discount_amount=discount_total,

        shipping_charge=totals["shipping"],

        total_amount=totals["total"],

        payment_status="Paid",

        status="Confirmed",

        stripe_session_id=session.id,

    )

    for item in cart_items:

        original_price = Decimal(
            str(item.variant_size.price)
        )

        discounted_price = calculate_offer_price(
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

            price=discounted_price,

            total_price=(
                discounted_price *
                item.quantity
            )

        )

        item.variant_size.stock -= item.quantity

        item.variant_size.save()

    cart_items.delete()

    return Response(

        {

            "message":
            "Payment successful"

        }

    )