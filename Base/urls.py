from django.urls import path
from .views import (
    landing,
    product,
    add_product,
    category,
    edit_product,
    delete_product,
    pc_builder,
    login_view,
    logout_view,
    signup_view,
)

urlpatterns = [
    path('', landing, name='landing'),
    path('product/', product, name='product'),
    path('add-product/', add_product, name='add_product'),
    path('category/', category, name='category'),
    path('edit/<int:product_id>/', edit_product, name='edit_product'),
    path('delete/<int:product_id>/', delete_product, name='delete_product'),
    path('pc_builder/', pc_builder, name='pc_builder'),
    path('logout/', logout_view, name='logout'),


     # 🔐 AUTH ROUTES
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),
]
