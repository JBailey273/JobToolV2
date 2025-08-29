from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class GlobalSettings(models.Model):
    logo = models.ImageField(upload_to='global_logos/', blank=True, null=True)

    def __str__(self) -> str:
        return "Global Settings"


class Contractor(models.Model):
    email = models.EmailField(unique=True)
    logo = models.ImageField(upload_to='contractor_logos/', blank=True, null=True)
    material_markup = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self) -> str:
        return self.email


class ContractorUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class ContractorUser(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    contractor = models.ForeignKey(Contractor, related_name='users', on_delete=models.CASCADE, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = ContractorUserManager()

    def __str__(self) -> str:
        return self.email


class Asset(models.Model):
    contractor = models.ForeignKey(Contractor, related_name='assets', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    cost_rate = models.DecimalField(max_digits=10, decimal_places=2)
    billable_rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    contractor = models.ForeignKey(Contractor, related_name='employees', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    cost_rate = models.DecimalField(max_digits=10, decimal_places=2)
    billable_rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return self.name


class Material(models.Model):
    contractor = models.ForeignKey(Contractor, related_name='materials', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return self.description


class Project(models.Model):
    contractor = models.ForeignKey(Contractor, related_name='projects', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class JobEntry(models.Model):
    project = models.ForeignKey(Project, related_name='job_entries', on_delete=models.CASCADE)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    asset = models.ForeignKey(Asset, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    employee = models.ForeignKey(Employee, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    material = models.ForeignKey(Material, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    cost_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.project.name} - {self.date}"


class Payment(models.Model):
    project = models.ForeignKey(Project, related_name='payments', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.project.name} - {self.amount}"
