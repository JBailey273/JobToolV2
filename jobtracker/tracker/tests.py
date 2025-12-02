from decimal import Decimal

from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.db.utils import OperationalError

from tracker.models import (
    Contractor,
    Project,
    Asset,
    Employee,
    JobEntry,
    ContractorUser,
)
from tracker.forms import ContractorForm
from tracker.admin import ContractorAdmin
from tracker import context_processors


class JobEntryCalculationTests(TestCase):
    def test_rates_and_material_cost_multiply_by_hours(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="contractor@example.com", material_margin=Decimal("25")
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
        entry = JobEntry.objects.create(
            project=project,
            date="2024-01-02",
            hours=Decimal("5"),
            asset=asset,
            employee=employee,
            material_description="Concrete",
            material_cost=Decimal("50"),
            description="Test entry",
        )
        self.assertEqual(entry.cost_amount, Decimal("400"))
        self.assertEqual(entry.billable_amount, Decimal("558.33"))


class ContractorAdminTests(TestCase):
    def test_password_creates_user(self):
        factory = RequestFactory()
        data = {
            "name": "Example Contractor",
            "email": "contractor@example.com",
            "phone": "",
            "material_margin": "0",
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


class LoginRedirectTests(TestCase):
    def test_login_redirects_to_root(self):
        contractor = Contractor.objects.create(
            name="Example Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )
        response = self.client.post(
            reverse("login"),
            {"username": "user@example.com", "password": "secret"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


class ContractorContextProcessorTests(TestCase):
    def test_db_errors_do_not_break_templates(self):
        class FakeUser:
            is_authenticated = True

            @property
            def contractor(self):  # pragma: no cover - exercised via context processor
                raise OperationalError("contractor table missing")

        request = RequestFactory().get("/")
        request.user = FakeUser()

        context = context_processors.contractor(request)

        self.assertEqual(context["contractor"], None)

