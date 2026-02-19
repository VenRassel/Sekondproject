from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('product/', views.product, name='product'),
    path('add_product/', views.add_product, name='add-product'),
    path('category/', views.category, name='category'),
    path('edit_product/<int:product_id>/', views.edit_product, name='edit-product'),
    path('delete_product/<int:product_id>/', views.delete_product, name='delete-product'),
    path('pc_builder/', views.pc_builder, name='pc-builder'),

    # auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),

    # PROFILE SETTINGS
    path('profile/settings/', views.profile_settings, name='profile-settings'),

    path('pc-builder/checkout/', views.checkout_pc_build, name='checkout_pc_build'),
    path('pc-builder/history/', views.checkout_history, name='checkout-history'),
    path('pc-builder/history/<int:build_id>/', views.checkout_history_detail, name='checkout-history-detail'),

]
