from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.templatetags.static import static

from tracker.models import (
    Contractor,
    ContractorUser,
    Asset,
    JobEntry,
    Payment,
    Estimate,
    EstimateEntry,
)
from dashboard.views import _render_pdf


class RenderPdfTests(TestCase):
    def test_render_pdf_generates_pdf(self):
        template = SimpleNamespace(render=lambda ctx: "<html></html>")
        pdf_bytes = b"%PDF-1.4"
        html_obj = SimpleNamespace(write_pdf=lambda: pdf_bytes)
        with patch("dashboard.views.get_template", return_value=template):
            with patch("dashboard.views.HTML", return_value=html_obj):
                response = _render_pdf("tpl.html", {}, "out.pdf")
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")

    def test_render_pdf_missing_library_returns_500(self):
        with patch("dashboard.views.HTML", None):
            response = _render_pdf("tpl.html", {}, "out.pdf")
        assert response.status_code == 500

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
    def test_customer_report_displays_name(self):
        """Customer report should show contractor name and new title without logo."""

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

        self.assertNotContains(response, contractor.logo.url)
        self.assertNotContains(response, "contractor-logo")
        self.assertContains(response, contractor.name)
        self.assertContains(response, "Summary of Work")

    def test_customer_report_pdf_renders_without_logo(self):
        """PDF export should render without contractor logo."""

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

        with patch("dashboard.views._render_pdf", return_value=None):
            response = self.client.get(url + "?export=pdf")

        self.assertNotContains(response, contractor.logo_thumbnail.url)
        self.assertNotContains(response, "contractor-logo")


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

    def test_contractor_report_excludes_logo(self):
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

        self.assertNotContains(response, contractor.logo.url)
        self.assertNotContains(response, "contractor-logo")


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

    def test_contractor_job_report_excludes_logo(self):
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

        self.assertNotContains(response, contractor.logo.url)
        self.assertNotContains(response, "contractor-logo")


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
        JobEntry.objects.create(
            project=project, date="2024-01-03", hours=Decimal("0.5"), asset=asset
        )
        Payment.objects.create(
            project=project, amount=Decimal("5"), date="2024-01-04"
        )
        Payment.objects.create(
            project=project, amount=Decimal("8"), date="2024-01-05"
        )

        response = self.client.get(reverse("dashboard:contractor_summary"))

        self.assertContains(response, "$30")
        self.assertContains(response, "$13")
        self.assertContains(response, "$17")


class PdfExportTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.project = self.contractor.projects.create(
            name="Proj", start_date="2024-01-01"
        )
        asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        JobEntry.objects.create(
            project=self.project, date="2024-01-02", hours=Decimal("1"), asset=asset
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

    def _fake_html(self, pdf_bytes=b"%PDF-1.4\n"):
        return SimpleNamespace(write_pdf=lambda: pdf_bytes)

    @patch("dashboard.views.HTML")
    def test_contractor_report_pdf(self, mock_html):
        mock_html.side_effect = lambda *args, **kwargs: self._fake_html()
        response = self.client.get(
            reverse("dashboard:contractor_report") + "?export=pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @patch("dashboard.views.HTML")
    def test_contractor_job_report_pdf(self, mock_html):
        mock_html.side_effect = lambda *args, **kwargs: self._fake_html()
        url = reverse("dashboard:contractor_job_report", args=[self.project.pk])
        response = self.client.get(url + "?export=pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @patch("dashboard.views.HTML")
    def test_customer_report_pdf(self, mock_html):
        mock_html.side_effect = lambda *args, **kwargs: self._fake_html()
        url = reverse("dashboard:customer_report", args=[self.project.pk])
        response = self.client.get(url + "?export=pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @patch("dashboard.views.HTML")
    def test_pdf_export_error_returns_error(self, mock_html):
        mock_html.side_effect = Exception("boom")
        response = self.client.get(
            reverse("dashboard:contractor_report") + "?export=pdf"
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Error generating PDF", response.content)

    @patch("dashboard.views.HTML")
    def test_pdf_with_leading_whitespace_is_trimmed(self, mock_html):
        mock_html.side_effect = lambda *args, **kwargs: self._fake_html(b"\n%PDF-1.4\n")
        response = self.client.get(
            reverse("dashboard:contractor_report") + "?export=pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))


class JobEntryOrderingTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        self.project = self.contractor.projects.create(
            name="Proj", start_date="2024-01-01"
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

    def _create_entries(self):
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-01",
            hours=Decimal("1"),
            asset=self.asset,
        )
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-10",
            hours=Decimal("1"),
            asset=self.asset,
        )

    def test_customer_report_entries_sorted_desc(self):
        self._create_entries()
        url = reverse("dashboard:customer_report", args=[self.project.pk])
        response = self.client.get(url)
        entries = list(response.context["entries"])
        self.assertEqual(
            [e.date.isoformat() for e in entries], ["2024-01-10", "2024-01-01"]
        )

    def test_contractor_job_report_entries_sorted_desc(self):
        self._create_entries()
        url = reverse("dashboard:contractor_job_report", args=[self.project.pk])
        response = self.client.get(url)
        entries = list(response.context["entries"])
        self.assertEqual(
            [e.date.isoformat() for e in entries], ["2024-01-10", "2024-01-01"]
        )

    def test_search_entries_sorted_desc(self):
        self._create_entries()
        url = reverse("dashboard:search_entries")
        response = self.client.get(url)
        results = response.json()["results"]
        self.assertEqual(
            [r["date"] for r in results], ["2024-01-10", "2024-01-01"]
        )


class ReportsPageTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.project = self.contractor.projects.create(
            name="Proj", start_date="2024-01-01"
        )

    def test_reports_page_lists_project_links(self):
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(reverse("dashboard:reports"))
        self.assertContains(response, "Project Reports")
        self.assertContains(response, self.project.name)
        self.assertContains(
            response, reverse("dashboard:customer_report", args=[self.project.pk])
        )

    def test_reports_page_has_no_breadcrumb(self):
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(reverse("dashboard:reports"))
        self.assertNotContains(response, '<nav aria-label="breadcrumb"')


class ProjectDetailPageTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.project = self.contractor.projects.create(
            name="Proj", start_date="2024-01-01"
        )

    def test_project_detail_has_no_breadcrumb(self):
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )
        response = self.client.get(
            reverse("dashboard:project_detail", args=[self.project.pk])
        )
        self.assertNotContains(response, '<nav aria-label="breadcrumb"')


class ProjectDetailRobustnessTests(TestCase):
    def test_project_detail_handles_bad_numeric_data(self):
        contractor = Contractor.objects.create(
            name="Test Contractor", email="user2@example.com"
        )
        user = ContractorUser.objects.create_user(
            email="user2@example.com", password="secret", contractor=contractor
        )
        project = contractor.projects.create(name="Proj", start_date="2024-01-01")
        asset = contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        JobEntry.objects.create(
            project=project,
            date="2024-01-02",
            hours=Decimal("1"),
            asset=asset,
            cost_amount=Decimal("10"),
            billable_amount=Decimal("20"),
        )
        # Corrupt asset cost_rate with invalid value to simulate bad data
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("UPDATE tracker_asset SET cost_rate='' WHERE id=%s", [asset.id])

        self.client.force_login(user)
        url = reverse("dashboard:project_detail", args=[project.pk])
        response = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)


class ProjectAnalyticsHoursTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.project = self.contractor.projects.create(
            name="Proj", start_date="2024-01-01"
        )
        self.asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        self.employee = self.contractor.employees.create(
            name="Gary", cost_rate=Decimal("15"), billable_rate=Decimal("30")
        )
        self.client.post(
            reverse("login"), {"username": "user@example.com", "password": "secret"}
        )

    def test_total_hours_excludes_material_entries(self):
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=self.asset,
        )
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-03",
            hours=Decimal("5"),
            material_description="Pipe",
            material_cost=Decimal("5"),
        )
        url = reverse("dashboard:project_detail", args=[self.project.pk])
        response = self.client.get(url)
        self.assertEqual(response.context["total_hours"], Decimal("2"))

    def test_total_hours_excludes_equipment_only_entries(self):
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=self.asset,
        )
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-03",
            hours=Decimal("3"),
            employee=self.employee,
        )
        JobEntry.objects.create(
            project=self.project,
            date="2024-01-04",
            hours=Decimal("4"),
            asset=self.asset,
            employee=self.employee,
        )
        url = reverse("dashboard:project_detail", args=[self.project.pk])
        response = self.client.get(url)
        self.assertEqual(response.context["total_hours"], Decimal("7"))


class JobEstimateReportTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        self.user = ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.estimate = self.contractor.estimates.create(
            name="Proj", created_date="2024-01-01"
        )
        self.asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )

    def test_job_estimate_report_totals(self):
        EstimateEntry.objects.create(
            estimate=self.estimate,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=self.asset,
            cost_amount=Decimal("20"),
            billable_amount=Decimal("40"),
        )
        EstimateEntry.objects.create(
            estimate=self.estimate,
            date="2024-01-02",
            hours=Decimal("1"),
            material_description="Pipe",
            material_cost=Decimal("5"),
            cost_amount=Decimal("5"),
            billable_amount=Decimal("5"),
        )

        self.client.force_login(self.user)
        url = reverse("dashboard:job_estimate_report", args=[self.estimate.pk])
        response = self.client.get(url)
        self.assertContains(response, "$40.00")
        self.assertContains(response, "$5.00")
        self.assertContains(response, "$45.00")
        self.assertContains(response, "$25.00")
        self.assertContains(response, "$20.00")
        self.assertContains(response, "44.44%")


class EstimateListTests(TestCase):
    def setUp(self):
        self.contractor = Contractor.objects.create(
            name="Test Contractor", email="user@example.com"
        )
        self.user = ContractorUser.objects.create_user(
            email="user@example.com", password="secret", contractor=self.contractor
        )
        self.estimate = self.contractor.estimates.create(
            name="Estimate", created_date="2024-01-01"
        )
        self.asset = self.contractor.assets.create(
            name="Excavator", cost_rate=Decimal("10"), billable_rate=Decimal("20")
        )
        EstimateEntry.objects.create(
            estimate=self.estimate,
            date="2024-01-02",
            hours=Decimal("2"),
            asset=self.asset,
            cost_amount=Decimal("20"),
            billable_amount=Decimal("40"),
        )

    def test_estimate_list_shows_profit_and_margin(self):
        self.client.force_login(self.user)
        url = reverse("dashboard:estimate_list")
        response = self.client.get(url)
        self.assertContains(response, "$40.00")
        self.assertContains(response, "$20.00")
        self.assertContains(response, "50.00%")

    def test_add_estimate_creates_record(self):
        self.client.force_login(self.user)
        url = reverse("dashboard:estimate_list")
        response = self.client.post(url, {"name": "New Est"})
        self.assertRedirects(response, url)
        self.assertTrue(
            self.contractor.estimates.filter(name="New Est").exists()
        )

    def test_accept_estimate_converts_to_project(self):
        self.client.force_login(self.user)
        url = reverse("dashboard:accept_estimate", args=[self.estimate.pk])
        self.client.post(url)
        self.assertFalse(Estimate.objects.filter(pk=self.estimate.pk).exists())
        self.assertTrue(
            self.contractor.projects.filter(name="Estimate").exists()
        )


class ProjectEstimateCRUDTests(TestCase):
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

    def test_add_project_via_post(self):
        response = self.client.post(
            reverse("dashboard:project_list"),
            {"name": "NewProj", "start_date": "2024-01-01"},
        )
        self.assertRedirects(response, reverse("dashboard:project_list"))
        self.assertTrue(self.contractor.projects.filter(name="NewProj").exists())

    def test_delete_project(self):
        project = self.contractor.projects.create(name="Proj", start_date="2024-01-01")
        response = self.client.post(
            reverse("dashboard:delete_project", args=[project.pk])
        )
        self.assertRedirects(response, reverse("dashboard:project_list"))
        self.assertFalse(self.contractor.projects.filter(pk=project.pk).exists())

    def test_delete_estimate(self):
        estimate = self.contractor.estimates.create(name="Est", created_date="2024-01-01")
        response = self.client.post(
            reverse("dashboard:delete_estimate", args=[estimate.pk])
        )
        self.assertRedirects(response, reverse("dashboard:estimate_list"))
        self.assertFalse(self.contractor.estimates.filter(pk=estimate.pk).exists())
