import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventory.settings')
django.setup()

from Base.models import PCBuild

builds = PCBuild.objects.all()
print(f'Total builds: {builds.count()}')
print(f'Checked out: {builds.filter(status="checked_out").count()}')

for b in builds:
    print(f'Build #{b.id}: status={b.status}, total={b.total_price}, items={b.items.count()}')
