from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Base", "0008_pcbuild_is_archived"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[MinValueValidator(Decimal("0.01"))],
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="quantity",
            field=models.IntegerField(default=0, validators=[MinValueValidator(0)]),
        ),
    ]
