from django.contrib import admin
from .models import Product

# Register your models here.

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'quantity', 'is_archived', 'created_at']
    list_filter = ['is_archived', 'created_at']
    search_fields = ['name', 'description']
