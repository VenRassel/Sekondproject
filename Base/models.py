# Base/models.py
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

CATEGORY_CHOICES = [
    ('ram', 'RAM'),
    ('motherboard', 'Motherboard'),
    ('cpu', 'CPU'),
    ('gpu', 'GPU'),
    ('storage', 'Storage'),
    ('psu', 'Power Supply'),
    ('case', 'Case'),
]

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='ram')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        normalized_name = " ".join((self.name or '').split())
        normalized_description = " ".join((self.description or '').split())
        if not normalized_name:
            raise ValidationError({'name': 'Product name is required.'})
        self.name = normalized_name
        self.description = (self.description or '').strip()

        if self.price is None:
            raise ValidationError({'price': 'Price is required.'})
        if self.price <= 0:
            raise ValidationError({'price': 'Price must be greater than 0.'})

        if self.quantity is None:
            raise ValidationError({'quantity': 'Quantity is required.'})
        if self.quantity < 0:
            raise ValidationError({'quantity': 'Quantity cannot be negative.'})

        duplicate_qs = Product.objects.filter(category=self.category)
        if self.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.pk)
        normalized_name_key = normalized_name.casefold()
        normalized_description_key = normalized_description.casefold()
        for existing in duplicate_qs.only('name', 'description'):
            existing_name = " ".join((existing.name or '').split()).casefold()
            existing_description = " ".join((existing.description or '').split()).casefold()
            if existing_name == normalized_name_key and existing_description == normalized_description_key:
                raise ValidationError(
                    {
                        'name': 'A product with this name, description, and category already exists.',
                        'description': 'A product with this name, description, and category already exists.',
                    }
                )

    def __str__(self):
        return self.name

# --- Profile model for user profile settings ---
ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('staff', 'Staff'),
)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.user.username} Profile"

class PCBuild(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('checked_out', 'Checked Out'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Build #{self.id} - {self.user.username}"

class PCBuildItem(models.Model):
    build = models.ForeignKey(
        PCBuild,
        related_name='items',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1)
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantity * self.price_at_time

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class StockMovement(models.Model):
    REASON_CHOICES = (
        ('checkout', 'Checkout'),
        ('adjustment', 'Manual Adjustment'),
        ('restock', 'Restock'),
    )

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    build = models.ForeignKey(
        PCBuild,
        on_delete=models.SET_NULL,
        related_name='stock_movements',
        blank=True,
        null=True,
    )
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='checkout')
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.quantity_change >= 0 else ''
        return f"{self.product.name} {sign}{self.quantity_change} ({self.reason})"


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('forgot_password', 'Forgot Password'),
        ('delete_build', 'Delete Build'),
    )
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rate_limited', 'Rate Limited'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    identifier = models.CharField(max_length=255, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        who = self.user.username if self.user else (self.identifier or 'anonymous')
        return f"{self.action} ({self.status}) - {who}"
