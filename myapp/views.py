from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode
)
from django.utils.encoding import force_bytes

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import *

from .models import User


from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import (
    api_view,
    permission_classes
)

from google.oauth2 import id_token
from google.auth.transport import requests

import csv

import traceback
from google.auth.exceptions import GoogleAuthError

@api_view(["POST"])
def google_login(request):

    token = request.data.get("token")

    if not token:
        return Response(
            {"error": "Google token is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=30
        )

        email = info.get("email")
        first_name = info.get("given_name", "")

        if not email:
            return Response(
                {"error": "Google account email not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user, created = User.objects.get_or_create(
            email=email.lower(),
            defaults={
                "first_name": first_name,
                "is_active": True,
            }
        )

        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "is_staff": user.is_staff,
                }
            }
        )

    except GoogleAuthError:
        return Response(
            {
                "error": "Google authentication failed. Please try again."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception:
        traceback.print_exc()   # Terminal-il full error print cheyyum

        return Response(
            {
                "error": "Something went wrong. Please try again later."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
def register(request):

    serializer = RegisterSerializer(data=request.data)

    serializer.is_valid(raise_exception=True)

    serializer.save()

    return Response(
        {
            "message": "Registration successful."
        },
        status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
def login(request):

    serializer = LoginSerializer(data=request.data)

    serializer.is_valid(raise_exception=True)

    user = serializer.validated_data["user"]

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "is_staff": user.is_staff,
            }
        },
        status=status.HTTP_200_OK
    )
    
@api_view(["POST"])
def forgot_password(request):

    serializer = ForgotPasswordSerializer(
        data=request.data
    )

    if serializer.is_valid():

        user = serializer.validated_data["user"]

        uidb64 = urlsafe_base64_encode(
            force_bytes(user.pk)
        )

        token = default_token_generator.make_token(
            user
        )

        reset_link = ( f"{settings.SITE_URL}/reset-password/{uidb64}/{token}")

        send_mail(
            subject="Reset Your Password",
            message=f"""
            Hello {user.first_name},

            Click the link below to reset your password:

            {reset_link}

            Thank You,
            Amora Team
            """,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False
        )

        return Response(
            {
                "message":
                "Password reset email sent"
            }
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )
@api_view(["POST"])
def reset_password( request,uidb64,token):

    serializer = ResetPasswordSerializer( data=request.data )

    if serializer.is_valid():

        try:

            uid = urlsafe_base64_decode( uidb64 ).decode()

            user = User.objects.get( pk=uid )

        except Exception:

            return Response( { "message": "Invalid Link"}, status=400 )

        if not default_token_generator.check_token( user, token ):
            
            return Response({ "message": "Invalid Token" },status=400)

        user.set_password( serializer.validated_data[ "password" ])

        user.save()

        return Response({ "message": "Password Reset Successful" } )

    return Response( serializer.errors, status=400 )
    
    
    
    
    
    
    
@api_view(["GET"])
def get_categories(request):  #NAVBAR IL ULLA CATOGARY DROPDOWN IL 

    categories = Category.objects.filter( is_active=True )

    serializer = CategorySerializer( categories, many=True )

    return Response( serializer.data )

@api_view(["GET"])    
def category_products( request, category_id ):  #CATOGRY YILE PRODUCTS PAGE IL

    products = Product.objects.filter( category_id=category_id, is_active=True )

    serializer = ProductSerializer( products, many=True )

    return Response( serializer.data )


@api_view(["GET"])
def get_products(request):

    products = Product.objects.filter(
        is_active=True
    )

    category = request.GET.get("category")
    subcategory = request.GET.get("subcategory")
    sort = request.GET.get("sort")

    if category:
        products = products.filter(
            category_id=category
        )

    if subcategory:
        products = products.filter(
            subcategory_id=subcategory
        )

    if sort == "price_low":
        products = products.order_by(
            "variants__sizes__price"
        )

    elif sort == "price_high":
        products = products.order_by(
            "-variants__sizes__price"
        )

    elif sort == "new":
        products = products.order_by(
            "-created_at"
        )

    serializer = ProductSerializer(
        products.distinct(),
        many=True
    )

    return Response(serializer.data)   
    
    
@api_view(["GET"])
def product_details( request,pk): #PRODUCT DETAIL PAGE IL SIZE UM COLOR SELET CHEYYAM 

    try:

        product = Product.objects.get(
            id=pk,
            is_active=True
        )

    except Product.DoesNotExist:

        return Response(
            {
                "message":
                "Product not found"
            },
            status=404
        )

    serializer = ProductSerializer(
        product
    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
def related_products(
    request,
    pk
):

    try:

        product = Product.objects.get(
            id=pk
        )

    except Product.DoesNotExist:

        return Response(
            {
                "message":
                "Product not found"
            },
            status=404
        )

    products = Product.objects.filter(

        category=product.category,

        is_active=True

    ).exclude(
        id=pk
    )

    serializer = ProductSerializer(
        products,
        many=True
    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
def new_arrivals(request):

    products = Product.objects.filter(
        is_active=True
    ).order_by(
        "-created_at"
    )[:8]

    serializer = ProductSerializer(
        products,
        many=True
    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
def get_subcategories(request):

    subcategories = SubCategory.objects.filter( is_active=True )

    serializer = SubCategorySerializer( subcategories, many=True )

    return Response( serializer.data )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_to_wishlist(request):

    user = request.user

    variant_id = request.data.get("variant")
    variant_size_id = request.data.get("variant_size")

    if not variant_id or not variant_size_id:

        return Response(
            {
                "error": "Variant and variant size are required"
            },
            status=400
        )

    try:

        variant = ProductVariant.objects.get(
            id=variant_id
        )

    except ProductVariant.DoesNotExist:

        return Response(
            {
                "error": "Variant not found"
            },
            status=404
        )

    try:

        variant_size = ProductVariantSize.objects.get(
            id=variant_size_id,
            variant=variant
        )

    except ProductVariantSize.DoesNotExist:

        return Response(
            {
                "error": "Variant size not found"
            },
            status=404
        )

    wishlist, created = Wishlist.objects.get_or_create(

        user=user,
        variant=variant,
        variant_size=variant_size

    )

    if created:

        return Response(
            {
                "message": "Added to wishlist"
            },
            status=201
        )

    return Response(
        {
            "message": "Already in wishlist"
        },
        status=200
    )
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_wishlist(request):

    wishlist = Wishlist.objects.filter(
        user=request.user
    ).select_related(
        "variant",
        "variant__product",
        "variant__color",
        "variant_size",
        "variant_size__size",
        "variant__product__category",
        "variant__product__offer"
    )

    serializer = WishlistSerializer(
        wishlist,
        many=True
    )

    return Response(
        serializer.data
    )
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_wishlist(request, id):

    wishlist = Wishlist.objects.get(
        id=id,
        user=request.user
    )

    wishlist.delete()

    return Response(
        {
            "message": "Removed from wishlist"
        }
    )
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_to_cart(request):

    print("USER =", request.user)
    print("AUTH =", request.auth)

    variant_id = request.data.get(
        "variant"
    )

    variant_size_id = request.data.get(
        "variant_size"
    )

    try:

        quantity = int(
            request.data.get(
                "quantity",
                1
            )
        )

    except (TypeError, ValueError):

        return Response(
            {
                "message":
                "Invalid quantity"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity < 1:

        return Response(
            {
                "message":
                "Quantity must be greater than 0"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        variant = ProductVariant.objects.select_related(
            "product"
        ).get(
            id=variant_id
        )

        variant_size = ProductVariantSize.objects.select_related(
            "variant"
        ).get(
            id=variant_size_id
        )

    except ProductVariant.DoesNotExist:

        return Response(
            {
                "message":
                "Variant not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    except ProductVariantSize.DoesNotExist:

        return Response(
            {
                "message":
                "Variant size not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if variant_size.variant != variant:

        return Response(
            {
                "message":
                "Invalid size selected"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity > variant_size.stock:

        return Response(
            {
                "message":
                f"Only {variant_size.stock} items available in stock"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    cart_item, created = Cart.objects.get_or_create(

        user=request.user,

        variant=variant,

        variant_size=variant_size,

        defaults={
            "quantity": quantity
        }

    )

    if not created:

        new_quantity = cart_item.quantity + quantity

        if new_quantity > variant_size.stock:

            return Response(
                {
                    "message":
                    f"Only {variant_size.stock} items available in stock"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity = new_quantity

        cart_item.save()

    return Response(
        {
            "message":
            "Product added to cart successfully"
        },
        status=status.HTTP_200_OK
    )
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cart(request):

    print("USER =", request.user)
    print("AUTH =", request.auth)

    cart = (
        Cart.objects
        .filter(user=request.user)
        .select_related(
            "variant",
            "variant__product",
            "variant__product__offer",
            "variant__color",
            "variant_size",
            "variant_size__size",
        )
        .prefetch_related(
            "variant__images"
        )
    )

    serializer = CartSerializer(
        cart,
        many=True
    )

    subtotal = Decimal("0.00")

    total_items = 0

    for item in cart:

        discounted_price = calculate_offer_price(
            item.variant_size.price,
            item.variant.product.offer
        )

        subtotal += (
            discounted_price *
            item.quantity
        )

        total_items += item.quantity

    totals = calculate_order_total(
        subtotal
    )

    return Response(
        {
            "items": serializer.data,
            "subtotal": totals["subtotal"],
            "shipping": totals["shipping"],
            "total": totals["total"],
            "total_items": total_items,
        },
        status=status.HTTP_200_OK
    )
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_cart_quantity(request, id):

    try:

        cart = Cart.objects.select_related(
            "variant_size"
        ).get(
            id=id,
            user=request.user
        )

    except Cart.DoesNotExist:

        return Response(
            {
                "message":
                "Cart item not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    try:

        quantity = int(
            request.data.get(
                "quantity"
            )
        )

    except (TypeError, ValueError):

        return Response(
            {
                "message":
                "Invalid quantity"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity < 1:

        return Response(
            {
                "message":
                "Quantity must be greater than 0"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity > cart.variant_size.stock:

        return Response(
            {
                "message":
                f"Only {cart.variant_size.stock} items available in stock"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    cart.quantity = quantity

    cart.save()

    discounted_price = calculate_offer_price(
        cart.variant_size.price,
        cart.variant.product.offer
    )

    line_total = (
        discounted_price *
        cart.quantity
    )

    cart_items = (
        Cart.objects
        .filter(user=request.user)
        .select_related(
            "variant__product__offer",
            "variant_size"
        )
    )

    subtotal = Decimal("0.00")

    total_items = 0

    for item in cart_items:

        subtotal += (
            calculate_offer_price(
                item.variant_size.price,
                item.variant.product.offer
            )
            *
            item.quantity
        )

        total_items += item.quantity

    totals = calculate_order_total(
        subtotal
    )

    return Response(
        {
            "message":
            "Quantity updated successfully",

            "quantity":
            cart.quantity,

            "item_total":
            line_total,

            "subtotal":
            totals["subtotal"],

            "shipping":
            totals["shipping"],

            "total":
            totals["total"],

            "total_items":
            total_items
        },
        status=status.HTTP_200_OK
    )

from django.db import transaction

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def place_order(request):

    address_id = request.data.get(
        "address"
    )

    try:

        address = Address.objects.get(
            id=address_id,
            user=request.user
        )

    except Address.DoesNotExist:

        return Response(
            {
                "message":
                "Address not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    cart_items = (
        Cart.objects
        .select_related(
            "variant__product__offer",
            "variant__color",
            "variant_size__size"
        )
        .filter(
            user=request.user
        )
    )

    if not cart_items.exists():

        return Response(
            {
                "message":
                "Cart is empty"
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
                    f"Only {item.variant_size.stock} items available for {item.variant.product.name}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        original_price = item.variant_size.price

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

        user=request.user,

        address=address,

        subtotal=original_subtotal,

        discount_amount=discount_total,

        shipping_charge=totals["shipping"],

        total_amount=totals["total"],

        payment_status="Pending",

        status="Pending"
    )
    
    for item in cart_items:

        original_price = item.variant_size.price

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
            "Order placed successfully",

            "order_id":
            order.id,

            "subtotal":
            order.subtotal,

            "discount":
            order.discount_amount,

            "shipping":
            order.shipping_charge,

            "grand_total":
            order.total_amount,

            "payment_status":
            order.payment_status,

            "status":
            order.status

        },

        status=status.HTTP_201_CREATED

    )
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_cart_item(
    request,
    id
):

    try:

        cart = Cart.objects.get(

            id=id,

            user=request.user

        )

    except Cart.DoesNotExist:

        return Response(

            {
                "message":
                "Cart item not found"
            },

            status=404

        )

    cart.delete()

    return Response(

        {
            "message":
            "Item removed"
        }

    )
    
 


    
from django.utils import timezone

@api_view(["GET"])
def get_offers(request):

    today = timezone.now().date()

    offers = Offer.objects.filter(

        is_active=True,

        start_date__lte=today,

        end_date__gte=today

    )

    serializer = OfferSerializer(
        offers,
        many=True
    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
def offer_products(request):

    today = timezone.now().date()

    offer = Offer.objects.filter(

        is_active=True,

        start_date__lte=today,

        end_date__gte=today

    ).first()

    if not offer:

        return Response([])

    products = Product.objects.filter(
        offer=offer
    )

    serializer = ProductSerializer(
        products,
        many=True
    )

    return Response({

        "offer": {

            "title":
            offer.title,

            "description":
            offer.description,

            "image":
            offer.image.url
            if offer.image
            else None,

            "discount":
            offer.discount_percentage

        },

        "products":
        serializer.data

    })

@api_view(["GET"])
def offer_status(request):

    today = timezone.now().date()

    has_offer = Offer.objects.filter(

        is_active=True,

        start_date__lte=today,

        end_date__gte=today

    ).exists()

    return Response({

        "has_offer": has_offer

    })

@api_view(["GET"])
def search_products(request):

        search = request.GET.get(
            "search",
            ""
        ).strip()

        category = request.GET.get(
            "category"
        )

        subcategory = request.GET.get(
            "subcategory"
        )

        offer = request.GET.get(
            "offer"
        )

        new_arrival = request.GET.get(
            "new_arrival"
        )

        sort = request.GET.get(
            "sort"
        )

        products = Product.objects.filter(
            is_active=True
        )

        if search:

            products = products.filter(

                Q(
                    name__icontains=search
                )

                |

                Q(
                    description__icontains=search
                )

                |

                Q(
                    category__name__icontains=search
                )

                |

                Q(
                    subcategory__name__icontains=search
                )

            )

        if category:

            products = products.filter(
                category_id=category
            )

        if subcategory:

            products = products.filter(
                subcategory_id=subcategory
            )

        if offer == "true":

            products = products.filter(
                offer__isnull=False
            )

        if new_arrival == "true":

            latest_ids = Product.objects.filter(
                is_active=True
            ).order_by(
                "-created_at"
            ).values_list(
                "id",
                flat=True
            )[:8]

            products = products.filter(
                id__in=latest_ids
            )

        if sort == "price_low":

            products = products.order_by(
                "variants__sizes__price"
            )

        elif sort == "price_high":

            products = products.order_by(
                "-variants__sizes__price"
            )

        elif sort == "new":

            products = products.order_by(
                "-created_at"
            )

        else:

            products = products.order_by(
                "-created_at"
            )

        serializer = ProductSerializer(

            products.distinct(),

            many=True

        )

        return Response(
            serializer.data
        )
    
from decimal import Decimal

from django.db import transaction

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def place_order(request):

    address_id = request.data.get(
        "address"
    )

    try:

        address = Address.objects.get(
            id=address_id,
            user=request.user
        )

    except Address.DoesNotExist:

        return Response(
            {
                "message": "Address not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    cart_items = Cart.objects.select_related(
        "variant__product__offer",
        "variant__color",
        "variant_size__size",
    ).filter(
        user=request.user
    )

    if not cart_items.exists():

        return Response(
            {
                "message": "Cart is empty"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    subtotal = Decimal("0.00")

    for item in cart_items:

        if item.quantity > item.variant_size.stock:

            return Response(
                {
                    "message": (
                        f"Only "
                        f"{item.variant_size.stock} "
                        f"items available for "
                        f"{item.variant.product.name}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        discounted_price = calculate_offer_price(
            item.variant_size.price,
            item.variant.product.offer
        )

        subtotal += (
            discounted_price *
            item.quantity
        )

    totals = calculate_order_total(
        subtotal
    )

    order = Order.objects.create(

        user=request.user,

        address=address,

        subtotal=totals["subtotal"],

        discount_amount=totals["discount"],

        shipping_charge=totals["shipping"],

        total_amount=totals["total"],

        payment_status="Pending",

        status="Pending"

    )

    for item in cart_items:

        prices = get_product_prices(

            item.variant_size.price,

            item.variant.product.offer,

            item.quantity

        )

        OrderItem.objects.create(

            order=order,

            product=item.variant.product,

            color=item.variant.color,

            size=item.variant_size.size,

            variant_size=item.variant_size,

            quantity=item.quantity,

            original_price=prices["original_price"],

            discount_amount=prices["discount_amount"],

            price=prices["discounted_price"],

            total_price=prices["item_total"]

        )

        item.variant_size.stock -= item.quantity

        item.variant_size.save()

    cart_items.delete()

    return Response(

        {

            "message": "Order placed successfully",

            "order_id": order.id,

            "subtotal": order.subtotal,

            "discount": order.discount_amount,

            "shipping": order.shipping_charge,

            "total_amount": order.total_amount

        },

        status=status.HTTP_201_CREATED

    )
    
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orders(request):

    orders = Order.objects.filter(
        user=request.user
    ).order_by(
        "-created_at"
    )

    serializer = MyOrderSerializer(
        orders,
        many=True
    )

    return Response(
        serializer.data
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cancel_order(request, id):

    try:

        order = Order.objects.get(
            id=id,
            user=request.user
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message": "Order not found"
            },
            status=404
        )

    if order.status not in [
        "Pending",
        "Processing"
    ]:

        return Response(
            {
                "message": "This order cannot be cancelled."
            },
            status=400
        )

    if order.payment_status == "Paid":

        return Response(
            {
                "message": "Paid orders cannot be cancelled."
            },
            status=400
        )

    for item in order.items.all():

        item.variant_size.stock += item.quantity

        item.variant_size.save()

    order.status = "Cancelled"

    order.save()

    return Response(
        {
            "message": "Order cancelled successfully."
        }
    )
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_details(request, id):

    try:

        order = Order.objects.get(
            id=id,
            user=request.user
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message":
                "Order not found"
            },
            status=404
        )

    serializer = OrderSerializer(
        order
    )

    return Response(
        serializer.data
    )
    
from django.db.models import Q, Sum

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_dashboard_cards(request):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    total_revenue = (
        Order.objects.filter(
            payment_status="Paid"
        ).exclude(
            status="Cancelled"
        ).aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    data = {

        "total_orders": Order.objects.count(),

        "revenue": total_revenue,

        "pending_orders": Order.objects.filter(
            status="Pending"
        ).count(),

        "processing_orders": Order.objects.filter(
            status="Processing"
        ).count(),

        "shipped_orders": Order.objects.filter(
            status="Shipped"
        ).count(),

        "delivered_orders": Order.objects.filter(
            status="Delivered"
        ).count(),

        "cancelled_orders": Order.objects.filter(
            status="Cancelled"
        ).count()

    }

    return Response(data)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_orders(request):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    orders = Order.objects.select_related(
        "user"
    )

    search = request.GET.get(
        "search",
        ""
    ).strip()

    status_filter = request.GET.get(
        "status"
    )

    sort = request.GET.get(
        "sort"
    )

    if search:

        if search.upper().startswith("ORD-"):

            order_id = search[4:].lstrip("0")

            if order_id == "":

                order_id = "0"

            if order_id.isdigit():

                orders = orders.filter(
                    id=int(order_id)
                )

            else:

                orders = orders.none()

        elif search.isdigit():

            orders = orders.filter(
                id=int(search)
            )

        else:

            orders = orders.filter(

                Q(
                    user__first_name__icontains=search
                )

                |

                Q(
                    user__email__icontains=search
                )

            )

    if status_filter:

        orders = orders.filter(
            status=status_filter
        )

    if sort == "newest":

        orders = orders.order_by(
            "-created_at"
        )

    elif sort == "oldest":

        orders = orders.order_by(
            "created_at"
        )

    elif sort == "high_amount":

        orders = orders.order_by(
            "-total_amount"
        )

    elif sort == "low_amount":

        orders = orders.order_by(
            "total_amount"
        )

    else:

        orders = orders.order_by(
            "-created_at"
        )

    serializer = AdminOrderSerializer(
        orders,
        many=True
    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_order_details(request, id):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    try:

        order = Order.objects.select_related(
            "user",
            "address"
        ).prefetch_related(
            "items"
        ).get(
            id=id
        )

    except Order.DoesNotExist:

        return Response(
            {
                "error": "Order Not Found"
            },
            status=404
        )

    serializer = OrderSerializer(
        order
    )

    return Response(
        serializer.data
    )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_order_status(request, id):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    try:

        order = Order.objects.get(
            id=id
        )

    except Order.DoesNotExist:

        return Response(
            {
                "error": "Order Not Found"
            },
            status=404
        )

    status_value = request.data.get(
        "status"
    )

    allowed_status = [

        choice[0]

        for choice in Order.STATUS_CHOICES

    ]

    if status_value not in allowed_status:

        return Response(
            {
                "error": "Invalid Status"
            },
            status=400
        )

    order.status = status_value

    order.save()

    return Response(
        {
            "message": "Order Status Updated Successfully",
            "status": order.status
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def low_stock_products(request):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    products = ProductVariantSize.objects.select_related(
        "variant__product",
        "variant__color",
        "variant__product__category",
        "size"
    ).filter(
        stock__lte=5
    ).order_by(
        "stock"
    )

    data = []

    for item in products:

        data.append({

            "id": item.id,

            "product_name": item.variant.product.name,

            "category": (
                item.variant.product.category.name
                if item.variant.product.category
                else None
            ),

            "color": (
                item.variant.color.name
                if item.variant.color
                else None
            ),

            "size": (
                item.size.name
                if item.size
                else None
            ),

            "stock": item.stock

        })

    return Response(data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_orders_csv(request):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    response = HttpResponse(
        content_type="text/csv"
    )

    response[
        "Content-Disposition"
    ] = 'attachment; filename="orders.csv"'

    writer = csv.writer(
        response
    )

    writer.writerow([

        "Order ID",

        "Customer",

        "Email",

        "Amount",

        "Payment Method",

        "Payment Status",

        "Order Status",

        "Date"

    ])

    orders = Order.objects.select_related(
        "user"
    ).order_by(
        "-created_at"
    )

    for order in orders:

        writer.writerow([

            order.id,

            order.user.first_name,

            order.user.email,

            order.total_amount,


            order.payment_status,

            order.status,

            order.created_at.strftime(
                "%d-%m-%Y %H:%M"
            )

        ])

    return response

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile
from .serializers import ProfileSerializer


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def profile(request):

    user = request.user

    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == "GET":

        serializer = ProfileSerializer(user)
        print(serializer.data)

        return Response(serializer.data)

    serializer = ProfileSerializer(
        user,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():

        serializer.save()

        return Response(
            {
                "message": "Profile updated successfully",
                "data": serializer.data
            }
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def address_list(request):

    if request.method == "GET":

        addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-id")
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    serializer = AddressSerializer(
        data=request.data,
        context={"request": request}
    )

    if serializer.is_valid():

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):

    try:
        address = Address.objects.get(id=pk, user=request.user)
    except Address.DoesNotExist:
        return Response(
            {"message": "Address not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "PUT":

        serializer = AddressSerializer(
            address,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():

            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    address.delete()

    return Response(
        {"message": "Address deleted successfully"},
        status=status.HTTP_200_OK
    )
    
    
    
# New catogary view  
from django.db.models import Prefetch

@api_view(["GET"])
def home_categories(request):

    categories = Category.objects.filter(
        is_active=True
    ).prefetch_related(
        Prefetch(
            "subcategories",
            queryset=SubCategory.objects.filter(is_active=True)
        )
    )

    serializer = HomeCategorySerializer(
        categories,
        many=True
    )

    return Response(serializer.data)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_order_details(request, id):

    if not request.user.is_staff:

        return Response(
            {
                "message": "Permission Denied"
            },
            status=403
        )

    try:

        order = Order.objects.select_related(
            "user",
            "address"
        ).prefetch_related(
            "items__product",
            "items__color",
            "items__size"
        ).get(
            id=id
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message": "Order not found"
            },
            status=404
        )

    serializer = OrderSerializer(order)

    return Response(serializer.data)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_order_status(request, id):

    if not request.user.is_staff:

        return Response(
            {
                "message": "Permission Denied"
            },
            status=403
        )

    try:

        order = Order.objects.get(
            id=id
        )

    except Order.DoesNotExist:

        return Response(
            {
                "message": "Order not found"
            },
            status=404
        )

    status_value = request.data.get("status")

    if not status_value:

        return Response(
            {
                "message": "Status is required"
            },
            status=400
        )

    allowed_status = [

        "Pending",
        "Processing",
        "Shipped",
        "Delivered",
        "Cancelled"

    ]

    if status_value not in allowed_status:

        return Response(
            {
                "message": "Invalid Status"
            },
            status=400
        )

    order.status = status_value

    order.save()

    return Response(
        {
            "message": "Order status updated successfully",
            "status": order.status
        }
    )
    
from django.db.models import Count

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wishlist_products(request):

    if not request.user.is_staff:

        return Response(
            {
                "error": "Unauthorized"
            },
            status=403
        )

    variants = ProductVariant.objects.annotate(

        wishlist_count=Count(
            "wishlist",
            distinct=True
        )

    ).filter(

        wishlist_count__gt=0

    ).select_related(

        "product",
        "product__category",
        "color"

    ).order_by(

        "-wishlist_count"

    )

    data = []

    for variant in variants:

        image = None

        product_image = variant.images.filter(
            is_primary=True
        ).first()

        if not product_image:

            product_image = variant.images.first()

        if product_image:

            image = request.build_absolute_uri(
                product_image.image.url
            )

        data.append({

            "variant_id": variant.id,

            "product_id": variant.product.id,

            "product_name": variant.product.name,

            "color": (
                variant.color.name
                if variant.color
                else None
            ),

            "image": image,

            "category": (
                variant.product.category.name
                if variant.product.category
                else None
            ),

            "wishlist_count": variant.wishlist_count

        })

    return Response(data)


@api_view(["GET"])
def get_hero_banners(request):

    banners = HeroBanner.objects.filter(
        is_active=True
    ).order_by(
        "display_order"
    )

    serializer = HeroBannerSerializer(
        banners,
        many=True
    )

    return Response(
        serializer.data
    )