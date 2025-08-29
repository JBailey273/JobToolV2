from django.db import models


class Contractor(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    logo = models.CharField(max_length=255, blank=True)
    material_markup = models.DecimalField(max_digits=5, decimal_places=2, default=0)

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
