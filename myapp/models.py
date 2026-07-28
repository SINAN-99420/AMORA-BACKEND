from django.db import models
from django.contrib.auth.models import ( AbstractUser, BaseUserManager)


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)

        user = self.model( email=email, **extra_fields )

        user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            email,
            password,
            **extra_fields
        )

class User(AbstractUser):

    username = None
    email = models.EmailField( unique=True )

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Category(models.Model):

    name = models.CharField(max_length=100,unique=True)
    image = models.ImageField( upload_to="categories/")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class SubCategory(models.Model):

    category = models.ForeignKey( Category, on_delete=models.CASCADE,related_name="subcategories")
    name = models.CharField( max_length=100)
    image = models.ImageField( upload_to="subcategories/", blank=True, null=True )
    is_active = models.BooleanField( default=True )
    created_at = models.DateTimeField( auto_now_add=True )

    def __str__(self):
        return self.name

class Offer(models.Model):

    title = models.CharField(max_length=200 )
    description = models.TextField()
    image = models.ImageField( upload_to="offers/")
    discount_percentage = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField( default=True)
    created_at = models.DateTimeField( auto_now_add=True)

    def __str__(self):
        return self.title
    
class Color(models.Model):

    name = models.CharField(max_length=50,unique=True)
    code = models.CharField(max_length=7)

    def __str__(self):
        return self.name
    
class Size(models.Model):

    name = models.CharField( max_length=20, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        
    def __str__(self):
        return self.name

class Product(models.Model):

    category = models.ForeignKey(Category,on_delete=models.CASCADE)
    subcategory = models.ForeignKey( SubCategory,on_delete=models.CASCADE)
    offer = models.ForeignKey( Offer, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField( max_length=200 )
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField( auto_now_add=True )
    updated_at = models.DateTimeField( auto_now=True )

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey( Product, on_delete=models.CASCADE, related_name="variants" )
    color = models.ForeignKey(Color,on_delete=models.CASCADE, null=True, blank=True )

    class Meta:
        unique_together = (
            "product",
            "color"
        )
    def __str__(self):
        if self.color:
            return (
                f"{self.product.name} - "
                f"{self.color.name}"
            )
        return self.product.name

class ProductVariantSize(models.Model):

    variant = models.ForeignKey(ProductVariant,on_delete=models.CASCADE, related_name="sizes" )
    size = models.ForeignKey( Size,  on_delete=models.CASCADE, null=True, blank=True )
    price = models.DecimalField( max_digits=10,decimal_places=2)
    stock = models.PositiveIntegerField( default=0)

    class Meta:
        unique_together = (
            "variant",
            "size"
        )
    def __str__(self):
        if self.size:
            return (
                f"{self.variant} - "
                f"{self.size.name}"
            )

        return str(self.variant)
    
class ProductImage(models.Model):

    variant = models.ForeignKey( ProductVariant, on_delete=models.CASCADE,related_name="images", null=True, blank=True)
    image = models.ImageField( upload_to="products/")
    is_primary = models.BooleanField( default=False)

    def __str__(self):
        return (
            f"{self.variant.product.name} - "
      
        )

class Wishlist(models.Model):

    user = models.ForeignKey( User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product,on_delete=models.CASCADE, related_name="wishlist")
    created_at = models.DateTimeField( auto_now_add=True )

    class Meta:
        unique_together = (
            "user",
            "product"
        )

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.product.name}"
        )

class Cart(models.Model):

    user = models.ForeignKey( User, on_delete=models.CASCADE )
    variant = models.ForeignKey( ProductVariant, on_delete=models.CASCADE )
    variant_size = models.ForeignKey( ProductVariantSize,on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField( default=1)
    created_at = models.DateTimeField( auto_now_add=True )

    class Meta:
        unique_together = (
            "user",
            "variant_size"
        )

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.variant.product.name} - "
            f"{self.variant.color.name} - "
            f"{self.variant_size.size.name}"
        )

class Address(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses"
        ,null=True
    )

    full_name = models.CharField(max_length=100, blank=True,null=True)
    phone = models.CharField(max_length=15, blank=True,null=True)
    address_line = models.TextField(blank=True,null=True)
    city = models.CharField(max_length=100, blank=True,null=True)
    postal_code = models.CharField(max_length=20, blank=True,null=True)
    country = models.CharField(max_length=100, default="New Zealand")
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True,null=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"
    
class UserProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
        , related_name="profile"
        ,null=True
    )

    phone = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)

class Order(models.Model):

    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Shipped", "Shipped"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
        ("Refunded", "Refunded"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    shipping_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="Pending"
    )

    stripe_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"ORD-{self.id:06d}"

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        null=True
    )
    

    size = models.ForeignKey(
        Size,
        on_delete=models.SET_NULL,
        null=True
    )

    quantity = models.PositiveIntegerField()

    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    variant_size = models.ForeignKey(
        ProductVariantSize,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    ) 


    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return self.product.name
    
class HeroBanner(models.Model):

    subtitle = models.CharField(max_length=100)

    title = models.CharField(max_length=200)

    description = models.TextField()

    image = models.ImageField(upload_to="hero_banners/")

    button_text = models.CharField(
        max_length=50,
        default="Explore Collection"
    )

    display_order = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.title