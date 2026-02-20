from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Base", "0007_stockmovement"),
    ]

    operations = [
        migrations.AddField(
            model_name="pcbuild",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
    ]
