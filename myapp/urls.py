from django.urls import path
from .import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/",views.register),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("google-login/", views.google_login),
    path("login/",views.login),
    path("forgot-password/",views.forgot_password),
    path("reset-password/<uidb64>/<token>/",views.reset_password),
    
    # path("categories/",views.get_categories), 
    path("category-products/<int:category_id>/", views.category_products ),
    path("products/",views.get_products),
    path("related-products/<int:pk>/",views.related_products),
    path("new-arrivals/",views.new_arrivals),
    
    path("subcategories/",views.get_subcategories),
    path("products/",views.get_products),
    path("product/<int:pk>/",views.product_details),
    path("wishlist/add/",views.add_to_wishlist),
    path("wishlist/",views.get_wishlist),
    path("wishlist/remove/<int:id>/",views.remove_wishlist),
    path("cart/add/", views.add_to_cart),
    path("cart/",views.get_cart),
    path("cart/update/<int:id>/", views.update_cart_quantity),
    path("cart/remove/<int:id>/", views.remove_cart_item),
    path("offer-status/", views.offer_status),
    path("offers/",views.get_offers),
    path( "offer-products/",views.offer_products),
    path("search-products/", views.search_products),
    path("place-order/",views.place_order),
    path("my-orders/",views.my_orders),
    path("cancel-order/<int:id>/",views.cancel_order),
    path( "order-details/<int:id>/",views.order_details),
    path(
    "admin-dashboard-cards/", views. admin_dashboard_cards
),

path(
    "admin-orders/",views.admin_orders
),
path(
    "admin-order-details/<int:id>/",
   views.admin_order_details
),

path(
    "update-order-status/<int:id>/",
    views.update_order_status
),
path(
    "low-stock-products/",
    views.low_stock_products
),
path(
    "export-orders-csv/",
    views.export_orders_csv
),
 path("profile/", views.profile),

    path("addresses/", views.address_list),

    path("addresses/<int:pk>/", views.address_detail),
    
    
    path(
        "home/categories/",views.home_categories,name="home-categories"
    ),
    path(
    "admin-order-details/<int:id>/",
    views.admin_order_details
),

path(
    "update-order-status/<int:id>/",
    views.update_order_status
),
path(
    "wishlist-products/",
    views.wishlist_products
),
path(
        "hero-banners/",
        views.get_hero_banners
    )
]   