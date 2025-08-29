from decimal import Decimal
from django.test import TestCase
from tracker.models import Contractor, Project, Asset, Employee, Material, JobEntry


class JobEntryCalculationTests(TestCase):
    def test_asset_rates_multiply_by_hours(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="contractor@example.com", material_markup=Decimal("25")
        )
        project = Project.objects.create(
            contractor=contractor, name="Test Project", start_date="2024-01-01"
        )
        asset = Asset.objects.create(
            contractor=contractor,
            name="Excavator",
            cost_rate=Decimal("10"),
            billable_rate=Decimal("15"),
        )
        employee = Employee.objects.create(
            contractor=contractor,
            name="Worker",
            cost_rate=Decimal("20"),
            billable_rate=Decimal("30"),
        )
        material = Material.objects.create(
            contractor=contractor, description="Concrete", actual_cost=Decimal("50")
        )
        entry = JobEntry.objects.create(
            project=project,
            date="2024-01-02",
            hours=Decimal("5"),
            asset=asset,
            employee=employee,
            material=material,
            description="Test entry",
        )
        self.assertEqual(entry.cost_amount, Decimal("200"))
        self.assertEqual(entry.billable_amount, Decimal("287.50"))

