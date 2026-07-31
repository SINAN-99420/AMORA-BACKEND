import nested_admin
from django.contrib import admin
from .models import *

admin.site.site_header = "Amora Admin"
admin.site.site_title = "Amora"
admin.site.index_title = "Welcome To Amora Dashboard"

@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        "email",
        "is_staff",
        "is_active"
    )

    search_fields = ( "email",)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "is_active",
        "created_at"
    )

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "category",
        "is_active"
    )

    list_filter = ( "category", )

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "discount_percentage",
        "is_active"
    )
    
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):

    list_display = ("name","code")

@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):

    list_display = ("name","order")

class ProductImageInline( nested_admin.NestedTabularInline ):

    model = ProductImage
    extra = 1

class ProductVariantSizeInline( nested_admin.NestedTabularInline):

    model = ProductVariantSize
    extra = 1

class ProductVariantInline( nested_admin.NestedStackedInline ):

    model = ProductVariant
    extra = 1
    inlines = [
        ProductImageInline,
        ProductVariantSizeInline
    ]

@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):

    list_display = (
        "name",
        "category",
        "subcategory",
        "is_active"
    )

    list_filter = (
        "category",
        "subcategory",
        "is_active"
    )

    search_fields = ("name",)

    fieldsets = (
        ("Product Information",
            {    "fields": ("name", "description")}
        ),

        ( "Category Details",
            { "fields": ( "category","subcategory")}
        ),

        ("Offer Details",
            {"fields": ( "offer", ) }
        ),

        ("Status",
            {"fields": ("is_active",)}
        ),
        )

    inlines = [ProductVariantInline]

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "get_product",
        "variant",
        "variant_size",
        "created_at"
    )

    def get_product(self, obj):
        return obj.variant.product.name

    get_product.short_description = "Product"

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "variant_size",
        "quantity"
    )

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):

    list_display = (
        "full_name",
        "city",
        "postal_code",
        "country",
        "phone"
    )

admin.site.register(UserProfile)
admin.site.register(Order)
admin.site.register(OrderItem)


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "display_order",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    ordering = (
        "display_order",
    )

    search_fields = (
        "title",
        "subtitle",
    )