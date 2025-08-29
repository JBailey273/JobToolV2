from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from tracker.models import Contractor, Project, Asset, Employee, Material, JobEntry, ContractorUser
from tracker.forms import ContractorForm
from tracker.admin import ContractorAdmin


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


class ContractorAdminTests(TestCase):
    def test_password_creates_user(self):
        factory = RequestFactory()
        data = {
            "name": "Example Contractor",
            "email": "contractor@example.com",
            "phone": "",
            "material_markup": "0",
            "password": "secret123",
        }
        form = ContractorForm(data)
        self.assertTrue(form.is_valid())
        admin = ContractorAdmin(Contractor, AdminSite())
        obj = form.save(commit=False)
        request = factory.post("/admin/tracker/contractor/add/")
        admin.save_model(request, obj, form, False)
        user = ContractorUser.objects.get(contractor=obj)
        self.assertEqual(user.email, "contractor@example.com")
        self.assertTrue(user.check_password("secret123"))

