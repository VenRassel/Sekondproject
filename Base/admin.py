from django.contrib import admin
from .models import AuditLog, Product

# Register your models here.

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'quantity', 'is_archived', 'created_at']
    list_filter = ['is_archived', 'created_at']
    search_fields = ['name', 'description']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'status', 'user', 'identifier', 'ip_address']
    list_filter = ['action', 'status', 'created_at']
    search_fields = ['identifier', 'user__username', 'user__email', 'ip_address']
    readonly_fields = ['created_at', 'action', 'status', 'user', 'identifier', 'ip_address', 'metadata']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
