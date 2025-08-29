from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0002_contractoruser'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contractor',
            name='logo',
            field=models.ImageField(upload_to='contractor_logos/', blank=True, null=True),
        ),
    ]
