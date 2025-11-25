# Base/models.py
from django.db import models
from django.contrib.auth.models import User

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
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='ram')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

# --- Profile model for user profile settings ---
ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('staff', 'Staff'),
    ('encoder', 'Encoder'),
)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.user.username} Profile"
