from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from decimal import Decimal
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image
import os
from django.utils import timezone
from datetime import datetime


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
    contractor = models.ForeignKey(
        Contractor, related_name="projects", on_delete=models.CASCADE
    )
    estimate = models.ForeignKey(
        "Estimate",
        related_name="projects",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Source estimate for this project, if applicable",
    )
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class Estimate(models.Model):
    contractor = models.ForeignKey(
        Contractor, related_name="estimates", on_delete=models.CASCADE
    )
    
    # Basic Information
    name = models.CharField(max_length=255, help_text="Internal name for this estimate")
    created_date = models.DateField(default=timezone.now)
    estimate_number = models.CharField(max_length=50, blank=True, help_text="Estimate number for customer reference")
    
    # Customer Information
    customer_name = models.CharField(max_length=255, default="")
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_address = models.TextField(blank=True)
    
    # Project Information
    project_location = models.TextField(blank=True, help_text="Job site address")
    project_description = models.TextField(blank=True, help_text="Brief description of the work")
    
    # Terms and Conditions
    payment_terms = models.TextField(
        blank=True, 
        default="50% deposit required upon acceptance. Balance due upon completion.",
        help_text="Payment terms and conditions"
    )
    exclusions = models.TextField(
        blank=True,
        help_text="Work or materials not included in this estimate"
    )
    special_terms = models.TextField(
        blank=True,
        help_text="Additional terms, warranties, or conditions"
    )
    liability_statement = models.TextField(
        blank=True,
        default="Contractor maintains general liability insurance. Customer responsible for permits unless otherwise specified.",
        help_text="Liability and insurance information"
    )
    
    # Estimate Details
    valid_until = models.DateField(blank=True, null=True, help_text="Estimate expiration date")
    notes = models.TextField(blank=True, help_text="Internal notes (not shown to customer)")
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent to Customer'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    def __str__(self) -> str:
        return f"{self.estimate_number or self.name} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if isinstance(self.created_date, str):
            try:
                self.created_date = datetime.strptime(self.created_date, "%Y-%m-%d").date()
            except ValueError:
                self.created_date = timezone.now().date()

        # Auto-generate estimate number if not provided
        if not self.estimate_number:
            year = self.created_date.year
            # Get the next number for this year
            latest = Estimate.objects.filter(
                contractor=self.contractor,
                created_date__year=year,
                estimate_number__startswith=f"EST-{year}-"
            ).order_by('-estimate_number').first()
            
            if latest and latest.estimate_number:
                try:
                    last_num = int(latest.estimate_number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.estimate_number = f"EST-{year}-{next_num:03d}"
        
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        """Calculate total cost amount for internal reporting"""
        return sum((entry.cost_amount or 0) for entry in self.entries.all())
    
    @property
    def total_billable(self):
        """Calculate total billable amount"""
        return sum((entry.billable_amount or 0) for entry in self.entries.all())
    
    @property
    def total_profit(self):
        """Calculate total projected profit"""
        return self.total_billable - self.total_cost
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.total_billable:
            return (self.total_profit / self.total_billable) * 100
        return 0

    @property
    def labor_equipment_total(self):
        """Get total for labor and equipment combined"""
        return sum(
            (entry.billable_amount or 0) 
            for entry in self.entries.filter(
                models.Q(asset__isnull=False) | models.Q(employee__isnull=False)
            ).exclude(material_description__isnull=False, material_description__gt='')
        )
    
    @property
    def materials_entries(self):
        """Get all material entries"""
        return self.entries.filter(
            material_description__isnull=False,
            material_description__gt='',
            description__startswith='Material:'
        )
    
    @property
    def services_entries(self):
        """Get all outside service entries"""
        return self.entries.filter(
            material_description__isnull=False,
            material_description__gt='',
            description__startswith='Outside Service:'
        )


class JobEntry(models.Model):
    project = models.ForeignKey(Project, related_name='job_entries', on_delete=models.CASCADE)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    asset = models.ForeignKey(Asset, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    employee = models.ForeignKey(Employee, related_name='job_entries', on_delete=models.SET_NULL, blank=True, null=True)
    material_description = models.CharField(max_length=255, blank=True)
    material_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    service_markup = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Percentage markup for outside services",
    )
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
            if self.service_markup:
                self.billable_amount += material_total * (
                    Decimal("1") + self.service_markup / Decimal("100")
                )
            else:
                margin = contractor.material_margin / Decimal("100")
                self.billable_amount += material_total / (Decimal("1") - margin)
        self.cost_amount = self.cost_amount.quantize(Decimal("0.01"))
        self.billable_amount = self.billable_amount.quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class EstimateEntry(models.Model):
    estimate = models.ForeignKey(
        Estimate, related_name="entries", on_delete=models.CASCADE
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
    service_markup = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"), help_text="Percentage markup for outside services"
    )
    cost_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Estimate: {self.estimate.name} - {self.date}"

    def save(self, *args, **kwargs):
        contractor = self.estimate.contractor
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
            if self.service_markup:
                self.billable_amount += material_total * (
                    Decimal("1") + self.service_markup / Decimal("100")
                )
            else:
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
