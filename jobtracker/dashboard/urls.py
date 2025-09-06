from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.contractor_summary, name="contractor_summary"),
    path("projects/", views.project_list, name="project_list"),
    path("estimates/", views.estimate_list, name="estimate_list"),
    path("estimates/create/", views.create_estimate, name="create_estimate"),
    path("estimates/<int:pk>/edit/", views.edit_estimate, name="edit_estimate"),
    path("estimates/<int:pk>/delete/", views.delete_estimate, name="delete_estimate"),
    path("estimates/<int:pk>/accept/", views.accept_estimate, name="accept_estimate"),
    path("estimates/<int:pk>/duplicate/", views.duplicate_estimate, name="duplicate_estimate"),
    path("estimates/<int:pk>/email/", views.email_estimate, name="email_estimate"),
    path(
        "estimates/<int:pk>/add-entry/",
        views.add_estimate_entry,
        name="add_estimate_entry",
    ),
    path(
        "estimates/<int:pk>/customer-report/",
        views.customer_estimate_report,
        name="customer_estimate_report",
    ),
    path(
        "estimates/<int:pk>/internal-report/",
        views.internal_estimate_report,
        name="internal_estimate_report",
    ),
    path(
        "estimates/<int:pk>/report/",
        views.job_estimate_report,
        name="job_estimate_report",
    ),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:pk>/delete/", views.delete_project, name="delete_project"),
    path(
        "projects/add-entry/select/",
        views.select_job_entry_project,
        name="select_job_entry_project",
    ),
    path(
        "projects/add-payment/select/",
        views.select_payment_project,
        name="select_payment_project",
    ),
    path("projects/<int:pk>/add-entry/", views.add_job_entry, name="add_job_entry"),
    path("entries/<int:pk>/edit/", views.edit_job_entry, name="edit_job_entry"),
    path("projects/<int:pk>/add-payment/", views.add_payment, name="add_payment"),
    path("reports/", views.reports, name="reports"),
    path("reports/contractor/", views.contractor_report, name="contractor_report"),
    path(
        "projects/<int:pk>/customer-report/",
        views.customer_report,
        name="customer_report",
    ),
    path(
        "projects/<int:pk>/contractor-report/",
        views.contractor_job_report,
        name="contractor_job_report",
    ),
    # New API endpoints
    path("api/search-entries/", views.search_entries, name="search_entries"),
    path(
        "api/material-templates/",
        views.get_material_templates,
        name="material_templates",
    ),
    path(
        "api/projects/<int:pk>/analytics/",
        views.project_analytics_data,
        name="project_analytics",
    ),
]
