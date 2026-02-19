import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventory.settings')
django.setup()

from Base.models import PCBuild, PCBuildItem
from decimal import Decimal

# Simulate the view logic
analytics_builds = PCBuild.objects.filter(status='checked_out')
builds = list(analytics_builds.order_by('-created_at'))

for build in builds:
    build.item_count = build.items.count()

total_builds = analytics_builds.count()

# Calculate total revenue using Python instead of Django ORM
total_revenue = Decimal('0.00')
for build in analytics_builds:
    total_revenue += build.total_price

avg_order_value = total_revenue / total_builds if total_builds > 0 else Decimal('0.00')

# Most popular item
from django.db.models import Count
most_popular_item = None
most_popular_count = 0
if total_builds > 0:
    popular = PCBuildItem.objects.values('product__name').annotate(
        count=Count('id')
    ).order_by('-count').first()
    if popular:
        most_popular_item = popular['product__name']
        most_popular_count = popular['count']

# Convert to float as in the view
context = {
    'builds': builds,
    'total_builds': total_builds,
    'total_revenue': float(total_revenue),
    'avg_order_value': float(avg_order_value),
    'most_popular_item': most_popular_item,
    'most_popular_count': most_popular_count,
}

print("Context variables that will be passed to template:")
print(f"total_builds: {context['total_builds']}")
print(f"total_revenue: {context['total_revenue']}")
print(f"avg_order_value: {context['avg_order_value']}")
print(f"most_popular_item: {context['most_popular_item']}")
print(f"most_popular_count: {context['most_popular_count']}")
print(f"\nNumber of builds in list: {len(context['builds'])}")
