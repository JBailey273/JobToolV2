from decimal import Decimal

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.templatetags.static import static

from tracker.models import Contractor, ContractorUser, Asset, JobEntry, Payment


class DashboardLogoTests(TestCase):
    def test_dashboard_displays_contractor_logo(self):
        """The contractor's logo should appear on the dashboard navbar."""

        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(reverse("dashboard:contractor_summary"))

        self.assertContains(response, contractor.logo.url)
        self.assertContains(response, "contractor-logo")

    def test_navbar_displays_site_logo(self):
        """The navbar should always show the site branding logo."""

        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(reverse("dashboard:contractor_summary"))

        self.assertContains(response, static("img/logo.png"))

    def test_logo_persists_after_upload(self):
        """A newly uploaded logo remains visible after a refresh."""

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor.logo = logo_file
        contractor.save()

        response = self.client.get(reverse("dashboard:contractor_summary"))

        self.assertContains(response, contractor.logo.url)


class CustomerReportHeaderTests(TestCase):
    def test_customer_report_displays_logo_and_name(self):
        """Customer report should show contractor name, logo, and new title."""

        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        project = contractor.projects.create(name="Proj", start_date="2024-01-01")

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        url = reverse("dashboard:customer_report", args=[project.pk])
        response = self.client.get(url)

        self.assertContains(response, contractor.logo.url)
        self.assertContains(response, "contractor-logo")
        self.assertContains(response, contractor.name)
        self.assertContains(response, "Summary of Work")

    def test_customer_report_pdf_uses_thumbnail_logo(self):
        """PDF export should use the contractor's thumbnail logo."""

        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        project = contractor.projects.create(name="Proj", start_date="2024-01-01")

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        url = reverse("dashboard:customer_report", args=[project.pk])
        from unittest.mock import patch

        with patch("dashboard.views.pisa", None):
            response = self.client.get(url + "?export=pdf")

        self.assertContains(response, contractor.logo_thumbnail.url)
        self.assertContains(response, "contractor-logo")


class CustomerReportPaymentsTests(TestCase):
    def test_customer_report_shows_payments_and_outstanding(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )
        project = contractor.projects.create(name="Proj", start_date="2024-01-01")
        asset = contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        JobEntry.objects.create(
            project=project,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=asset,
        )
        Payment.objects.create(project=project, amount=Decimal("15"), date="2024-01-03")

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        url = reverse("dashboard:customer_report", args=[project.pk])
        response = self.client.get(url)

        self.assertContains(response, "$15")
        self.assertContains(response, "Outstanding Balance: $25")


class ContractorSummaryReportTests(TestCase):
    def test_contractor_summary_report_title(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(reverse("dashboard:contractor_report"))
        self.assertContains(response, "Contractor Summary Report")

    def test_contractor_report_displays_logo(self):
        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        response = self.client.get(reverse("dashboard:contractor_report"))

        self.assertContains(response, contractor.logo.url)
        self.assertContains(response, "contractor-logo")


class ContractorJobReportTests(TestCase):
    def test_contractor_job_report_shows_cost_profit_margin(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )
        project = contractor.projects.create(name="Proj", start_date="2024-01-01")
        asset = contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        JobEntry.objects.create(
            project=project,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=asset,
            material_cost=Decimal("5"),
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        url = reverse("dashboard:contractor_job_report", args=[project.pk])
        response = self.client.get(url)
        self.assertContains(response, "$30")
        self.assertContains(response, "$50")
        self.assertContains(response, "$20")
        self.assertContains(response, "40.00%")

    def test_contractor_job_report_displays_logo(self):
        logo_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        logo_file = SimpleUploadedFile("logo.gif", logo_content, content_type="image/gif")

        contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com", logo=logo_file
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=contractor
        )
        project = contractor.projects.create(name="Proj", start_date="2024-01-01")

        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

        url = reverse("dashboard:contractor_job_report", args=[project.pk])
        response = self.client.get(url)

        self.assertContains(response, contractor.logo.url)
        self.assertContains(response, "contractor-logo")


class ReportButtonPlacementTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

    def test_contractor_summary_buttons_without_projects(self):
        response = self.client.get(reverse("dashboard:contractor_summary"))
        self.assertContains(response, "View Projects")
        self.assertNotContains(response, "Contractor Summary Report")
        self.assertNotContains(response, "Customer Reports")
        self.assertNotContains(response, "Quick Entry")
        self.assertNotContains(response, "Add Payment")

    def test_contractor_summary_shows_job_and_payment_buttons_with_project(self):
        self.contractor.projects.create(name="Proj", start_date="2024-01-01")
        response = self.client.get(reverse("dashboard:contractor_summary"))
        self.assertContains(response, "Quick Entry")
        self.assertContains(response, "Add Payment")

    def test_project_list_shows_contractor_summary_report_button(self):
        self.contractor.projects.create(name="Proj", start_date="2024-01-01")
        response = self.client.get(reverse("dashboard:project_list"))
        self.assertContains(response, "Contractor Summary Report")


class ContractorSummaryProjectTotalsTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

    def test_project_totals_display_correctly(self):
        asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        project = self.contractor.projects.create(name="Proj", start_date="2024-01-01")
        JobEntry.objects.create(
            project=project, date="2024-01-02", hours=Decimal("1"), asset=asset
        )
        Payment.objects.create(
            project=project, amount=Decimal("5"), date="2024-01-03"
        )

        response = self.client.get(reverse("dashboard:contractor_summary"))

        self.assertContains(response, "$20")
        self.assertContains(response, "$5")
        self.assertContains(response, "$15")
