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
            original_price * item.quantity
        )


        discount_total += (
            discount_amount * item.quantity
        )


        discounted_subtotal += (
            discounted_price * item.quantity
        )


        line_items.append(
            {
                "price_data": {
                    "currency": "nzd",

                    "product_data": {
                        "name": item.variant.product.name,

                        # Save the product snapshot inside Stripe.
                        # This lets the webhook create the Order only
                        # after payment, without creating a Pending Order.
                        "metadata": {
                            "type": "product",
                            "variant_size_id": str(item.variant_size_id),
                            "original_price": str(original_price),
                            "discount_amount": str(discount_amount),
                            "discounted_price": str(discounted_price),
                        },
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

                        "metadata": {
                            "type": "shipping",
                        },
                    },

                    "unit_amount": int(
                        totals["shipping"] * 100
                    ),
                },

                "quantity": 1,
            }
        )


    # =====================================================
    # CREATE STRIPE SESSION
    #
    # IMPORTANT:
    # No Order / OrderItem is created here.
    # The Order will be created only after Stripe confirms
    # that the payment is successful.
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
                "user_id": str(request.user.id),
                "address_id": str(address.id),
            }

        )

    except Exception as e:
        print("STRIPE ERROR =", e)
        import traceback
        traceback.print_exc()

        return Response(
            {
                "message": str(e)
            },
            status=500
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

    # =====================================================
    # VERIFY PAYMENT FIRST
    # =====================================================

    if session.payment_status != "paid":

        raise ValueError(
            "Payment is not paid"
        )


    user_id = session.metadata.get("user_id")
    address_id = session.metadata.get("address_id")


    if not user_id:

        raise ValueError(
            "User ID missing from Stripe metadata"
        )


    if not address_id:

        raise ValueError(
            "Address ID missing from Stripe metadata"
        )


    try:

        user_id = int(user_id)
        address_id = int(address_id)

    except (TypeError, ValueError):

        raise ValueError(
            "Invalid user or address ID"
        )


    # =====================================================
    # IDEMPOTENCY
    #
    # Webhook and payment-success API can both reach this
    # function. If this Stripe session already created an
    # order, return it instead of creating a duplicate.
    # =====================================================

    existing_order = (
        Order.objects
        .filter(stripe_session_id=session.id)
        .first()
    )

    if existing_order:

        return existing_order


    # =====================================================
    # VERIFY CURRENCY
    # =====================================================

    if not session.currency:

        raise ValueError(
            "Payment currency missing"
        )


    if session.currency.lower() != "nzd":

        raise ValueError(
            "Invalid payment currency"
        )


    # =====================================================
    # GET STRIPE LINE ITEMS
    #
    # We use the Stripe Checkout line items as the payment
    # snapshot. This avoids depending on the user's cart after
    # payment.
    # =====================================================

    stripe_line_items = stripe.checkout.Session.list_line_items(
        session.id,
        limit=100,
        expand=["data.price.product"],
    )


    product_snapshots = []
    shipping_charge = Decimal("0.00")


    for line_item in stripe_line_items.data:

        product = line_item.price.product

        if not product:

            raise ValueError(
                "Stripe product information is missing"
            )

        metadata = product.metadata or {}
        item_type = metadata.get("type")


        if item_type == "shipping":

            shipping_charge += (
                Decimal(line_item.amount_total or 0) /
                Decimal("100")
            )

            continue


        if item_type != "product":

            raise ValueError(
                "Invalid Stripe line item"
            )


        variant_size_id = metadata.get(
            "variant_size_id"
        )

        if not variant_size_id:

            raise ValueError(
                "Variant size missing from Stripe line item"
            )


        quantity = int(line_item.quantity or 0)

        if quantity <= 0:

            raise ValueError(
                "Invalid product quantity"
            )


        product_snapshots.append(
            {
                "variant_size_id": int(variant_size_id),
                "quantity": quantity,
                "original_price": Decimal(
                    metadata.get("original_price", "0")
                ),
                "discount_amount": Decimal(
                    metadata.get("discount_amount", "0")
                ),
                "price": Decimal(
                    metadata.get("discounted_price", "0")
                ),
            }
        )


    if not product_snapshots:

        raise ValueError(
            "No products found in Stripe session"
        )


    # =====================================================
    # VERIFY TOTAL AMOUNT
    # =====================================================

    expected_total = Decimal("0.00")
    original_subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    discounted_subtotal = Decimal("0.00")


    for snapshot in product_snapshots:

        quantity = snapshot["quantity"]
        original_price = snapshot["original_price"]
        discount_amount = snapshot["discount_amount"]
        price = snapshot["price"]

        original_subtotal += (
            original_price * quantity
        )

        discount_total += (
            discount_amount * quantity
        )

        discounted_subtotal += (
            price * quantity
        )


    expected_total = (
        discounted_subtotal + shipping_charge
    )

    expected_amount = int(
        expected_total * 100
    )


    if session.amount_total != expected_amount:

        raise ValueError(
            "Stripe payment amount does not match order total"
        )


    # =====================================================
    # GET ADDRESS
    # =====================================================

    try:

        address = Address.objects.get(
            id=address_id,
            user_id=user_id
        )

    except Address.DoesNotExist:

        raise ValueError(
            "Address not found"
        )


    # =====================================================
    # LOCK STOCK ROWS
    # =====================================================

    variant_size_ids = [
        snapshot["variant_size_id"]
        for snapshot in product_snapshots
    ]


    locked_sizes = {
        variant_size.id: variant_size
        for variant_size in (
            ProductVariantSize.objects
            .select_for_update()
            .select_related(
                "variant",
                "variant__product",
                "variant__color",
                "size",
            )
            .filter(
                id__in=variant_size_ids
            )
        )
    }


    # =====================================================
    # CHECK STOCK AGAIN
    # =====================================================

    for snapshot in product_snapshots:

        variant_size = locked_sizes.get(
            snapshot["variant_size_id"]
        )

        if not variant_size:

            raise ValueError(
                "Product variant not found"
            )


        if variant_size.stock < snapshot["quantity"]:

            raise ValueError(
                f"Insufficient stock for "
                f"{variant_size.variant.product.name}"
            )


    # =====================================================
    # CREATE PAID ORDER
    #
    # This is the first time Order is created.
    # =====================================================

    order = Order.objects.create(

        user_id=user_id,

        address=address,

        subtotal=original_subtotal,

        discount_amount=discount_total,

        shipping_charge=shipping_charge,

        total_amount=expected_total,

        payment_status="Paid",

        status="Processing",

        stripe_session_id=session.id,

    )


    # =====================================================
    # CREATE ORDER ITEMS
    # =====================================================

    for snapshot in product_snapshots:

        variant_size = locked_sizes[
            snapshot["variant_size_id"]
        ]

        OrderItem.objects.create(

            order=order,

            product=variant_size.variant.product,

            color=variant_size.variant.color,

            size=variant_size.size,

            variant_size=variant_size,

            quantity=snapshot["quantity"],

            original_price=snapshot["original_price"],

            discount_amount=snapshot["discount_amount"],

            price=snapshot["price"],

            total_price=(
                snapshot["price"] *
                snapshot["quantity"]
            ),

        )


    # =====================================================
    # REDUCE STOCK
    # =====================================================

    for snapshot in product_snapshots:

        variant_size = locked_sizes[
            snapshot["variant_size_id"]
        ]

        variant_size.stock -= snapshot["quantity"]

        variant_size.save(
            update_fields=[
                "stock"
            ]
        )


    # =====================================================
    # REMOVE ONLY PURCHASED ITEMS FROM CART
    # =====================================================

    for snapshot in product_snapshots:

        Cart.objects.filter(
            user_id=user_id,
            variant_size_id=snapshot["variant_size_id"],
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
    # LOGGED-IN USER MUST OWN THIS STRIPE SESSION
    # =====================================================

    session_user_id = session.metadata.get(
        "user_id"
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

        # The webhook may already have created the order.
        # If not, this safely creates it after verifying payment.
        order = fulfill_paid_order(
            session
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

