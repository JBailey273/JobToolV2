from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import tracker.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [

        # Only require the initial auth migration so history remains consistent across deployments
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contractor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('logo', models.ImageField(upload_to='contractor_logos/', blank=True, null=True)),
                ('material_markup', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
            ],
        ),
        migrations.CreateModel(
            name='GlobalSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logo', models.ImageField(upload_to='global_logos/', blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ContractorUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('contractor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='users', to='tracker.contractor')),
                ('groups', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
            },
            managers=[
                ('objects', tracker.models.ContractorUserManager()),
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
