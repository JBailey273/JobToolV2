from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Contractor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('password', models.CharField(max_length=128)),
                ('logo', models.CharField(blank=True, max_length=255)),
                ('material_markup', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
            ],
        ),
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('cost_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('billable_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('contractor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assets', to='tracker.contractor')),
            ],
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('cost_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('billable_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('contractor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employees', to='tracker.contractor')),
            ],
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('actual_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('contractor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='tracker.contractor')),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('contractor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='tracker.contractor')),
            ],
        ),
        migrations.CreateModel(
            name='JobEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('hours', models.DecimalField(decimal_places=2, max_digits=5)),
                ('cost_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('billable_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('description', models.TextField(blank=True)),
                ('asset', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_entries', to='tracker.asset')),
                ('employee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_entries', to='tracker.employee')),
                ('material', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_entries', to='tracker.material')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_entries', to='tracker.project')),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('date', models.DateField()),
                ('notes', models.TextField(blank=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='tracker.project')),
            ],
        ),
    ]
