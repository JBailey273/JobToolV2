from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from decimal import Decimal
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image
import os


class GlobalSettings(models.Model):
    logo = models.ImageField(upload_to='global_logos/', blank=True, null=True)

    def __str__(self) -> str:
        return "Global Settings"


class Contractor(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    logo = models.ImageField(upload_to='contractor_logos/', blank=True, null=True)
    logo_thumbnail = models.ImageField(
        upload_to='contractor_logos/thumbnails/', blank=True, null=True
    )
    material_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.logo:
            self._generate_thumbnail()

    def _generate_thumbnail(self):
        try:
            img = Image.open(self.logo)
        except Exception:
            return
        if img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        ):
            img = img.convert("RGBA")
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(background, img).convert("RGB")
        else:
            img = img.convert("RGB")
        max_width = 300
        if img.width > max_width:
            ratio = max_width / float(img.width)
            height = int(float(img.height) * ratio)
            img = img.resize((max_width, height), Image.LANCZOS)
        thumb_io = BytesIO()
        img.save(thumb_io, format="JPEG")
        thumb_name = os.path.splitext(os.path.basename(self.logo.name))[0]
        self.logo_thumbnail.save(
            f"thumb_{thumb_name}.jpg", ContentFile(thumb_io.getvalue()), save=False
        )
        thumb_io.close()
        super(Contractor, self).save(update_fields=["logo_thumbnail"])


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
    is_estimate = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name


class JobEntry(models.Model):
    project = models.ForeignKey(Project, related_name='job_entries', on_delete=models.CASCADE)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    asset = models.ForeignKey(Asset, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    employee = models.ForeignKey(Employee, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    material_description = models.CharField(max_length=255, blank=True)
    material_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cost_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.project.name} - {self.date}"

    def save(self, *args, **kwargs):
        contractor = self.project.contractor
        self.cost_amount = Decimal("0")
        self.billable_amount = Decimal("0")
        if self.asset:
            self.cost_amount += self.asset.cost_rate * self.hours
            self.billable_amount += self.asset.billable_rate * self.hours
        if self.employee:
            self.cost_amount += self.employee.cost_rate * self.hours
            self.billable_amount += self.employee.billable_rate * self.hours
        if self.material_cost:
            material_total = self.material_cost * self.hours
            self.cost_amount += material_total
            margin = contractor.material_margin / Decimal("100")
            self.billable_amount += material_total / (Decimal("1") - margin)
        self.cost_amount = self.cost_amount.quantize(Decimal("0.01"))
        self.billable_amount = self.billable_amount.quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class EstimateEntry(models.Model):
    project = models.ForeignKey(
        Project, related_name="estimate_entries", on_delete=models.CASCADE
    )
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    asset = models.ForeignKey(
        Asset,
        related_name="estimate_entries",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    employee = models.ForeignKey(
        Employee,
        related_name="estimate_entries",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    material_description = models.CharField(max_length=255, blank=True)
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    cost_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"Estimate: {self.project.name} - {self.date}"

    def save(self, *args, **kwargs):
        contractor = self.project.contractor
        self.cost_amount = Decimal("0")
        self.billable_amount = Decimal("0")
        if self.asset:
            self.cost_amount += self.asset.cost_rate * self.hours
            self.billable_amount += self.asset.billable_rate * self.hours
        if self.employee:
            self.cost_amount += self.employee.cost_rate * self.hours
            self.billable_amount += self.employee.billable_rate * self.hours
        if self.material_cost:
            material_total = self.material_cost * self.hours
            self.cost_amount += material_total
            margin = contractor.material_margin / Decimal("100")
            self.billable_amount += material_total / (Decimal("1") - margin)
        self.cost_amount = self.cost_amount.quantize(Decimal("0.01"))
        self.billable_amount = self.billable_amount.quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Payment(models.Model):
    project = models.ForeignKey(Project, related_name='payments', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.project.name} - {self.amount}"
