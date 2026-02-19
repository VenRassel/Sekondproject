import os
import django
from decimal import Decimal
from django.db.models import Sum, Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventory.settings')
django.setup()

from Base.models import PCBuild, PCBuildItem

# Test the checkout_history view logic
builds = PCBuild.objects.filter(status='checked_out').order_by('-created_at')

print("Builds query:", builds)
print("Count:", builds.count())

# Add item_count to each build
for build in builds:
    build.item_count = build.items.count()

total_builds = builds.count()
total_revenue = builds.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0.00')
avg_order_value = total_revenue / total_builds if total_builds > 0 else Decimal('0.00')

print(f"\nTotal Builds: {total_builds}")
print(f"Total Revenue: {total_revenue}")
print(f"Avg Order Value: {avg_order_value}")

# Most popular item
most_popular_item = None
most_popular_count = 0
if total_builds > 0:
    popular = PCBuildItem.objects.values('product__name').annotate(
        count=Count('id')
    ).order_by('-count').first()
    if popular:
        most_popular_item = popular['product__name']
        most_popular_count = popular['count']

print(f"Most Popular Item: {most_popular_item} ({most_popular_count} times)")
