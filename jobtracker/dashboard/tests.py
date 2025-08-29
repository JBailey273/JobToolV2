from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.templatetags.static import static

from tracker.models import Contractor, ContractorUser


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

