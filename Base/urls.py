from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('product/', views.product, name='product'),
    path('add_product/', views.add_product, name='add-product'),
    path('category/', views.category, name='category'),
    path('edit_product/<int:product_id>/', views.edit_product, name='edit-product'),
    path('delete_product/<int:product_id>/', views.delete_product, name='delete-product'),
    path('archive_product/<int:product_id>/', views.archive_product, name='archive-product'),
    path('restore_product/<int:product_id>/', views.restore_product, name='restore-product'),
    path('product/bulk-action/', views.bulk_manage_products, name='bulk-manage-products'),
    path('pc_builder/', views.pc_builder, name='pc-builder'),

    # auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path(
        'forgot-password/',
        views.ForgotPasswordView.as_view(),
        name='forgot_password',
    ),
    path(
        'forgot-password/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth/forgot_password_done.html',
        ),
        name='forgot_password_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='auth/forgot_password_confirm.html',
            success_url='/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth/forgot_password_complete.html',
        ),
        name='password_reset_complete',
    ),

    # PROFILE SETTINGS
    path('profile/settings/', views.profile_settings, name='profile-settings'),

    path('pc-builder/checkout/', views.checkout_pc_build, name='checkout_pc_build'),
    path('pc-builder/history/', views.checkout_history, name='checkout-history'),
    path('pc-builder/history/bulk-action/', views.bulk_manage_builds, name='bulk-manage-builds'),
    path('pc-builder/history/<int:build_id>/', views.checkout_history_detail, name='checkout-history-detail'),
    path('pc-builder/history/<int:build_id>/archive/', views.archive_build, name='archive-build'),
    path('pc-builder/history/<int:build_id>/restore/', views.restore_build, name='restore-build'),
    path('pc-builder/history/<int:build_id>/delete/', views.delete_build, name='delete-build'),
    path('pc-builder/reorder/<int:build_id>/', views.reorder_build, name='reorder-build'),
]
