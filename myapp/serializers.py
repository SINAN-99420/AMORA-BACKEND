from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import *
from .utils import *    

class RegisterSerializer(serializers.ModelSerializer):

    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "email",
            "password",
            "confirm_password"
        ]

        extra_kwargs = {
            "password": {
                "write_only": True
            }
        }

    def validate(self, data):

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                "Passwords do not match"
            )

        if len(data["password"]) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters"
            )

        if User.objects.filter(
            email=data["email"]
        ).exists():
            raise serializers.ValidationError(
                "Email already exists"
            )

        return data

    def create(self, validated_data):

        validated_data.pop("confirm_password")

        user = User(
            first_name=validated_data["first_name"],
            email=validated_data["email"],
            is_active=True
        )

        user.set_password(validated_data["password"])
        user.save()

        UserProfile.objects.create(user=user)

        return user
    
class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        user = authenticate(
            username=data["email"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError(
                "Invalid Email or Password"
            )

        data["user"] = user

        return data
    
class ForgotPasswordSerializer(serializers.Serializer):

    email = serializers.EmailField()
    def validate(self, data):
        try:
            user = User.objects.get( email=data["email"])

        except User.DoesNotExist:
            raise serializers.ValidationError({
                 "error": "No account found with this email address."
                })
        data["user"] = user
        return data

class ResetPasswordSerializer( serializers.Serializer):

    password = serializers.CharField()
    confirm_password = serializers.CharField()
    def validate(self, data):

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match")

        if len(data["password"]) < 8:
            raise serializers.ValidationError( "Password must be at least 8 characters" )

        return data
    
class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category

        fields = [
            "id",
            "name",
            "image",
            "is_active"
        ]

class SubCategorySerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )


    class Meta:
        model = SubCategory

        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "image",
            "is_active"
        ]

class ProductImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "is_primary"
        ]

class ColorSerializer(serializers.ModelSerializer):

    class Meta:
        model = Color

        fields = [
            "id",
            "name",
            "code"
        ]




class SizeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Size

        fields = [
            "id",
            "name"
        ]
        
class ProductVariantSizeSerializer(
    serializers.ModelSerializer
):

    size = SizeSerializer(
        read_only=True
    )

    discounted_price = serializers.SerializerMethodField()

    discount_amount = serializers.SerializerMethodField()

    has_offer = serializers.SerializerMethodField()

    discount_percentage = serializers.SerializerMethodField()

    class Meta:

        model = ProductVariantSize

        fields = [
            "id",
            "size",
            "price",
            "discounted_price",
            "discount_amount",
            "has_offer",
            "discount_percentage",
            "stock",
        ]

    def get_discounted_price(
        self,
        obj
    ):

        return calculate_offer_price(
            obj.price,
            obj.variant.product.offer
        )

    def get_discount_amount(
        self,
        obj
    ):

        return calculate_discount_amount(
            obj.price,
            obj.variant.product.offer
        )

    def get_has_offer(
        self,
        obj
    ):

        return is_offer_valid(
            obj.variant.product.offer
        )

    def get_discount_percentage(
        self,
        obj
    ):

        if is_offer_valid(
            obj.variant.product.offer
        ):

            return obj.variant.product.offer.discount_percentage

        return 0     

class ProductVariantSerializer(serializers.ModelSerializer):

    color = ColorSerializer(
        read_only=True
    )

    sizes = ProductVariantSizeSerializer(
        many=True,
        read_only=True
    )

    images = ProductImageSerializer(
        many=True,
        read_only=True
    )


    class Meta:
        model = ProductVariant

        fields = [
            "id",
            "color",
            "sizes",
            "images"
        ]


class CartSerializer(serializers.ModelSerializer):

    product = serializers.IntegerField(
        source="variant.product.id",
        read_only=True
    )

    variant = serializers.IntegerField(
        source="variant.id",
        read_only=True
    )

    variant_size = serializers.IntegerField(
        source="variant_size.id",
        read_only=True
    )

    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()

    color = serializers.CharField(
        source="variant.color.name",
        read_only=True
    )

    size = serializers.CharField(
        source="variant_size.size.name",
        read_only=True
    )

    original_price = serializers.DecimalField(
        source="variant_size.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    stock = serializers.IntegerField(
        source="variant_size.stock",
        read_only=True
    )

    discounted_price = serializers.SerializerMethodField()

    discount_amount = serializers.SerializerMethodField()

    has_offer = serializers.SerializerMethodField()

    discount_percentage = serializers.SerializerMethodField()

    quantity = serializers.IntegerField(
        read_only=True
    )

    total_price = serializers.SerializerMethodField()

    class Meta:

        model = Cart

        fields = [
            "id",
            "product",
            "variant",
            "variant_size",
            "product_name",
            "product_image",
            "color",
            "size",
            "original_price",
            "discounted_price",
            "discount_amount",
            "has_offer",
            "discount_percentage",
            "quantity",
            "stock",
            "total_price",
            "created_at",
        ]

    def get_product_image(
        self,
        obj
    ):

        image = obj.variant.images.filter(
            is_primary=True
        ).first()

        if not image:

            image = obj.variant.images.first()

        if image:

            return image.image.url

        return None

    def get_discounted_price(
        self,
        obj
    ):

        return calculate_offer_price(
            obj.variant_size.price,
            obj.variant.product.offer
        )

    def get_discount_amount(
        self,
        obj
    ):

        return calculate_discount_amount(
            obj.variant_size.price,
            obj.variant.product.offer
        )

    def get_has_offer(
        self,
        obj
    ):

        return is_offer_valid(
            obj.variant.product.offer
        )

    def get_discount_percentage(
        self,
        obj
    ):

        if is_offer_valid(
            obj.variant.product.offer
        ):

            return obj.variant.product.offer.discount_percentage

        return 0

    def get_total_price(
        self,
        obj
    ):

        discounted_price = calculate_offer_price(
            obj.variant_size.price,
            obj.variant.product.offer
        )

        return discounted_price * obj.quantity
    
    
class ProfileSerializer(serializers.ModelSerializer):

    phone = serializers.CharField(source="profile.phone", required=False)
    gender = serializers.CharField(source="profile.gender", required=False)
    date_of_birth = serializers.DateField(source="profile.date_of_birth", required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
        ]
        read_only_fields = ["email"]

    def update(self, instance, validated_data):

        profile_data = validated_data.pop("profile", {})

        instance.first_name = validated_data.get(
            "first_name",
            instance.first_name
        )

        instance.save()

        profile = UserProfile.objects.get(user=instance)

        profile.phone = profile_data.get(
            "phone",
            profile.phone
        )

        profile.gender = profile_data.get(
            "gender",
            profile.gender
        )

        profile.date_of_birth = profile_data.get(
            "date_of_birth",
            profile.date_of_birth
        )
        print(profile.phone, profile.gender, profile.date_of_birth)
        profile.save()
        

        return instance


class AddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ["id", "user", "created_at"]

    def create(self, validated_data):

        user = self.context["request"].user

        if validated_data.get("is_default"):
            Address.objects.filter(user=user).update(is_default=False)

        return Address.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):

        if validated_data.get("is_default"):
            Address.objects.filter(user=instance.user).exclude(id=instance.id).update(is_default=False)

        return super().update(instance, validated_data)
        
class OfferSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = Offer

        fields = "__all__"
        
class OrderItemSerializer(
    serializers.ModelSerializer
):

    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    color = serializers.CharField(
        source="color.name",
        read_only=True
    )

    size = serializers.CharField(
        source="size.name",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()

    class Meta:

        model = OrderItem

        fields = [

            "id",

            "product_name",

            "product_image",

            "color",

            "size",

            "quantity",

            "price"

        ]

    def get_product_image( self, obj):

        if not obj.product:
            return None

        variant = None

        if obj.color:

            variant = obj.product.variants.filter(
                color=obj.color
            ).first()

        if not variant:

            variant = obj.product.variants.first()

        if not variant:
            return None

        image = variant.images.filter(
            is_primary=True
        ).first()

        if not image:

            image = variant.images.first()

        if image:

            return image.image.url

        return None
class OrderSerializer(
    serializers.ModelSerializer
):

    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    customer_name = serializers.CharField(
        source="user.first_name",
        read_only=True
    )

    customer_email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    payment_method = serializers.CharField(
        read_only=True
    )

    address_name = serializers.CharField(
        source="address.full_name",
        read_only=True
    )

    address_phone = serializers.CharField(
        source="address.phone",
        read_only=True
    )

    address_line = serializers.CharField(
        source="address.address_line",
        read_only=True
    )

    city = serializers.CharField(
        source="address.city",
        read_only=True
    )

    postcode = serializers.CharField(
        source="address.postal_code",
        read_only=True
    )

    country = serializers.CharField(
        source="address.country",
        read_only=True
    )

    class Meta:

        model = Order

        fields = [

            "id",

            "customer_name",

            "customer_email",

            "subtotal",

            "discount_amount",

            "shipping_charge",

            "total_amount",

            "payment_method",

            "payment_status",

            "status",

            "created_at",

            "address_name",

            "address_phone",

            "address_line",

            "city",

            "postcode",

            "country",

            "items"

        ]
class AdminOrderSerializer(
    serializers.ModelSerializer
):

    customer_name = serializers.CharField(
        source="user.first_name",
        read_only=True
    )

    class Meta:

        model = Order

        fields = [

            "id",

            "customer_name",

            "total_amount",


            "payment_status",

            "status",

            "created_at"

        ]
        


class HomeSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = [
            "id",
            "name",
            "image",
        ]

# new added catoegory serializers
class HomeCategorySerializer(serializers.ModelSerializer):
    subcategories = HomeSubCategorySerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "image",
            "subcategories",
        ]
        
        
class WishlistSerializer(serializers.ModelSerializer):

    product = serializers.IntegerField(
        source="variant.product.id",
        read_only=True
    )

    variant = serializers.IntegerField(
        source="variant.id",
        read_only=True
    )

    variant_size = serializers.IntegerField(
        source="variant_size.id",
        read_only=True
    )

    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True
    )

    category = serializers.CharField(
        source="variant.product.category.name",
        read_only=True
    )

    color = serializers.CharField(
        source="variant.color.name",
        read_only=True
    )

    size = serializers.CharField(
        source="variant_size.size.name",
        read_only=True
    )

    stock = serializers.IntegerField(
        source="variant_size.stock",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()

    original_price = serializers.DecimalField(
        source="variant_size.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    discounted_price = serializers.SerializerMethodField()

    discount_amount = serializers.SerializerMethodField()

    has_offer = serializers.SerializerMethodField()

    discount_percentage = serializers.SerializerMethodField()

    class Meta:

        model = Wishlist

        fields = [
            "id",
            "product",
            "variant",
            "variant_size",
            "product_name",
            "category",
            "color",
            "size",
            "stock",
            "product_image",
            "original_price",
            "discounted_price",
            "discount_amount",
            "has_offer",
            "discount_percentage",
            "created_at",
        ]

    def get_product_image(self, obj):

        if not obj.variant:
            return None

        image = obj.variant.images.filter(
            is_primary=True
        ).first()

        if not image:
            image = obj.variant.images.first()

        return image.image.url if image else None

    def get_discounted_price(self, obj):

        if not obj.variant or not obj.variant_size:
            return None

        return calculate_offer_price(
            obj.variant_size.price,
            obj.variant.product.offer
        )

    def get_discount_amount(self, obj):

        if not obj.variant or not obj.variant_size:
            return 0

        return calculate_discount_amount(
            obj.variant_size.price,
            obj.variant.product.offer
        )

    def get_has_offer(self, obj):

        if not obj.variant:
            return False

        return is_offer_valid(
            obj.variant.product.offer
        )

    def get_discount_percentage(self, obj):

        if not obj.variant:
            return 0

        if is_offer_valid(
            obj.variant.product.offer
        ):
            return obj.variant.product.offer.discount_percentage

        return 0
        
class ProductSerializer(serializers.ModelSerializer):

    category = CategorySerializer(
        read_only=True
    )

    subcategory = SubCategorySerializer(
        read_only=True
    )

    offer = OfferSerializer(
        read_only=True
    )

    variants = ProductVariantSerializer(
        many=True,
        read_only=True
    )

    starting_price = serializers.SerializerMethodField()

    discounted_price = serializers.SerializerMethodField()

    discount_amount = serializers.SerializerMethodField()

    has_offer = serializers.SerializerMethodField()

    discount_percentage = serializers.SerializerMethodField()

    class Meta:

        model = Product

        fields = [
            "id",
            "name",
            "description",
            "category",
            "subcategory",
            "offer",
            "variants",
            "starting_price",
            "discounted_price",
            "discount_amount",
            "has_offer",
            "discount_percentage",
            "is_active",
            "created_at",
        ]

    def get_starting_price(
        self,
        obj
    ):

        return get_product_prices(
            obj
        )["starting_price"]

    def get_discounted_price(
        self,
        obj
    ):

        return get_product_prices(
            obj
        )["discounted_price"]

    def get_discount_amount(
        self,
        obj
    ):

        return get_product_prices(
            obj
        )["discount_amount"]

    def get_has_offer(
        self,
        obj
    ):

        return get_product_prices(
            obj
        )["has_offer"]

    def get_discount_percentage(
        self,
        obj
    ):

        return get_product_prices(
            obj
        )["discount_percentage"]


class WishlistProductSerializer(
    serializers.Serializer
):

    product_id = serializers.IntegerField()

    product_name = serializers.CharField()

    image = serializers.ImageField(
        allow_null=True
    )

    category = serializers.CharField()

    wishlist_count = serializers.IntegerField()
    
class MyOrderSerializer(
    serializers.ModelSerializer
):

    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    total_items = serializers.SerializerMethodField()

    class Meta:

        model = Order

        fields = [

            "id",

            "created_at",

            "status",

            "payment_status",

            "total_amount",

            "total_items",

            "items",

        ]

    def get_total_items(
        self,
        obj
    ):

        return obj.items.count()
    

class HeroBannerSerializer( serializers.ModelSerializer):
    class Meta:

        model = HeroBanner
        fields = "__all__"