from decimal import Decimal

import stripe

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

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
    ProductVariantSize,
)

from myapp.utils import (
    calculate_offer_price,
    calculate_discount_amount,
    calculate_order_total,
)

from .services import StripeService


stripe.api_key = settings.STRIPE_SECRET_KEY


# =========================================================
# CREATE STRIPE CHECKOUT SESSION
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
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


    cart_items = list(
        Cart.objects
        .filter(
            user=request.user
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


    if not cart_items:

        return Response(
            {
                "message": "Cart is empty"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


    original_subtotal = Decimal("0.00")

    discount_total = Decimal("0.00")

    discounted_subtotal = Decimal("0.00")

    line_items = []


    # =====================================================
    # VALIDATE CART + CALCULATE PRICES
    # =====================================================

    for item in cart_items:

        if item.quantity > item.variant_size.stock:

            return Response(
                {
                    "message":
                    f"{item.variant.product.name} has only "
                    f"{item.variant_size.stock} item(s) left."
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


        line_items.append(
            {
                "price_data": {

                    "currency": "nzd",

                    "product_data": {

                        "name":
                            item.variant.product.name,

                    },

                    "unit_amount": int(
                        discounted_price * 100
                    ),

                },

                "quantity": item.quantity,
            }
        )


    totals = calculate_order_total(
        discounted_subtotal
    )


    # =====================================================
    # SHIPPING
    # =====================================================

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


    # =====================================================
    # CREATE PENDING ORDER BEFORE STRIPE PAYMENT
    # =====================================================

    order = Order.objects.create(

        user=request.user,

        address=address,

        subtotal=original_subtotal,

        discount_amount=discount_total,

        shipping_charge=totals["shipping"],

        total_amount=totals["total"],

        payment_status="Pending",

        status="Pending",

    )


    # =====================================================
    # SNAPSHOT CART INTO ORDER ITEMS
    # =====================================================

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
            ),

        )


    # =====================================================
    # CREATE STRIPE SESSION
    # =====================================================

    try:

        session = StripeService.create_checkout_session(

            line_items=line_items,

            success_url=(
                "https://www.amora.nz/payment-success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),

            cancel_url=(
                "https://www.amora.nz/checkout"
            ),

            metadata={

                "user_id":
                    str(request.user.id),

                "order_id":
                    str(order.id),

            }

        )

    except Exception as e:
        print("STRIPE ERROR =", e)
        import traceback
        traceback.print_exc()

        order.delete()

        return Response(
            {
                "message": str(e)
            },
            status=500
        )


    # =====================================================
    # SAVE STRIPE SESSION ID
    # =====================================================

    order.stripe_session_id = session.id

    order.save(
        update_fields=[
            "stripe_session_id"
        ]
    )


    return Response(
        {
            "checkout_url": session.url
        }
    )


# =========================================================
# FULFILL PAID ORDER
# =========================================================

@transaction.atomic
def fulfill_paid_order(session):

    # Stripe metadata contains our Order ID

    order_id = session.metadata.get(
        "order_id"
    )


    if not order_id:

        raise ValueError(
            "Order ID missing from Stripe metadata"
        )


    # Lock the order so webhook retries / success page
    # cannot process it simultaneously.

    order = (
        Order.objects
        .select_for_update()
        .get(
            id=order_id
        )
    )


    # =====================================================
    # SECURITY CHECK
    # Stripe session must belong to this exact order.
    # =====================================================

    if (
        order.stripe_session_id
        and
        order.stripe_session_id != session.id
    ):

        raise ValueError(
            "Stripe session does not match order"
        )


    # =====================================================
    # IDEMPOTENCY
    # Already fulfilled -> do nothing.
    # =====================================================

    if order.payment_status == "Paid":

        return order


    # =====================================================
    # VERIFY STRIPE PAYMENT
    # =====================================================

    if session.payment_status != "paid":

        raise ValueError(
            "Payment is not paid"
        )


    # =====================================================
    # VERIFY STRIPE AMOUNT
    # =====================================================

    expected_amount = int(
        order.total_amount * 100
    )


    if session.amount_total != expected_amount:

        raise ValueError(
            "Stripe payment amount does not match order total"
        )


    # =====================================================
    # VERIFY CURRENCY
    # =====================================================

    if session.currency.lower() != "nzd":

        raise ValueError(
            "Invalid payment currency"
        )


    order_items = list(
        order.items.select_related(
            "variant_size"
        )
    )


    if not order_items:

        raise ValueError(
            "Order has no items"
        )


    # =====================================================
    # LOCK STOCK ROWS
    # =====================================================

    variant_size_ids = [

        item.variant_size_id

        for item in order_items

        if item.variant_size_id

    ]


    locked_sizes = {

        variant_size.id: variant_size

        for variant_size in (
            ProductVariantSize.objects
            .select_for_update()
            .filter(
                id__in=variant_size_ids
            )
        )

    }


    # =====================================================
    # CHECK STOCK AGAIN
    # =====================================================

    for item in order_items:

        if not item.variant_size_id:

            raise ValueError(
                "Variant size missing from order item"
            )


        variant_size = locked_sizes.get(
            item.variant_size_id
        )


        if not variant_size:

            raise ValueError(
                "Product variant not found"
            )


        if variant_size.stock < item.quantity:

            raise ValueError(
                f"Insufficient stock for "
                f"{item.product.name}"
            )


    # =====================================================
    # REDUCE STOCK
    # =====================================================

    for item in order_items:

        variant_size = locked_sizes[
            item.variant_size_id
        ]


        variant_size.stock -= (
            item.quantity
        )


        variant_size.save(
            update_fields=[
                "stock"
            ]
        )


    # =====================================================
    # MARK ORDER PAID
    # =====================================================

    order.payment_status = "Paid"

    order.status = "Processing"

    order.save(
        update_fields=[
            "payment_status",
            "status",
        ]
    )


    # =====================================================
    # REMOVE PURCHASED ITEMS FROM CART
    #
    # Do NOT delete the user's whole cart.
    # If they added something after opening Stripe,
    # that new cart item should remain.
    # =====================================================

    for item in order_items:

        Cart.objects.filter(

            user=order.user,

            variant_size_id=
                item.variant_size_id,

        ).delete()


    return order


# =========================================================
# PAYMENT SUCCESS PAGE API
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_success(request):

    session_id = request.GET.get(
        "session_id"
    )


    if not session_id:

        return Response(
            {
                "message":
                    "Session ID is required"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


    try:

        session = (
            stripe.checkout.Session.retrieve(
                session_id
            )
        )

    except Exception:

        return Response(
            {
                "message":
                    "Invalid payment session"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


    # =====================================================
    # IMPORTANT:
    # Logged-in user must own this Stripe session.
    # =====================================================

    session_user_id = (
        session.metadata.get(
            "user_id"
        )
    )


    if (
        not session_user_id
        or
        str(request.user.id)
        != str(session_user_id)
    ):

        return Response(
            {
                "message":
                    "Unauthorized payment session"
            },
            status=status.HTTP_403_FORBIDDEN
        )


    if session.payment_status != "paid":

        return Response(
            {
                "message":
                    "Payment has not been completed"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


    try:

        order = fulfill_paid_order(
            session
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message":
                    "Order not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    except ValueError as error:

        return Response(
            {
                "message":
                    str(error)
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception:

        return Response(
            {
                "message":
                    "Payment was received but order processing failed. "
                    "Please contact support."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


    return Response(
        {
            "message":
                "Payment successful",

            "order_id":
                order.id,
        }
    )


# =========================================================
# STRIPE WEBHOOK
# =========================================================

@csrf_exempt
def stripe_webhook(request):

    if request.method != "POST":

        return HttpResponse(
            status=405
        )


    payload = request.body

    signature = request.META.get(
        "HTTP_STRIPE_SIGNATURE"
    )


    if not signature:

        return HttpResponse(
            status=400
        )


    try:

        event = (
            stripe.Webhook.construct_event(

                payload,

                signature,

                settings.STRIPE_WEBHOOK_SECRET,

            )
        )


    except ValueError:

        return HttpResponse(
            status=400
        )


    except stripe.error.SignatureVerificationError:

        return HttpResponse(
            status=400
        )


    # =====================================================
    # PAYMENT COMPLETED
    # =====================================================

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]


        # Only fulfill when Stripe says it is actually paid.

        if session.get(
            "payment_status"
        ) == "paid":

            try:

                fulfill_paid_order(
                    session
                )

            except Exception:

                # Returning 500 tells Stripe delivery failed,
                # so Stripe can retry the webhook.

                return HttpResponse(
                    status=500
                )


    # =====================================================
    # ASYNC PAYMENT SUCCESS
    # Useful if additional delayed payment methods
    # are enabled later.
    # =====================================================

    elif (
        event["type"]
        ==
        "checkout.session.async_payment_succeeded"
    ):

        session = event["data"]["object"]


        try:

            fulfill_paid_order(
                session
            )

        except Exception:

            return HttpResponse(
                status=500
            )


    return HttpResponse(
        status=200
    )