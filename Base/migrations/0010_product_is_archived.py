from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Base', '0009_alter_product_validation'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
    ]
