from decimal import Decimal
from io import BytesIO
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template

try:
    from xhtml2pdf import pisa
except Exception:  # pragma: no cover - optional dependency
    pisa = None

from tracker.models import Asset, Employee, JobEntry, Material, Payment, Project


def link_callback(uri, rel):
    if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, "")) or os.path.join(
            settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, "")
        )
    else:
        return uri
    if not os.path.isfile(path):
        return uri
    return path


def _render_pdf(template_src, context):
    if pisa is None:
        return None
    template = get_template(template_src)
    html = template.render(context)
    result = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")), result, link_callback=link_callback
    )
    if pdf.err:
        return None
    return HttpResponse(result.getvalue(), content_type="application/pdf")


@login_required
def contractor_summary(request):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    projects = contractor.projects.all().annotate(
        total_billable=Sum('job_entries__billable_amount'),
        total_payments=Sum('payments__amount'),
    )
    overall_billable = sum([(p.total_billable or 0) for p in projects])
    overall_payments = sum([(p.total_payments or 0) for p in projects])
    outstanding = overall_billable - overall_payments
    return render(
        request,
        'dashboard/contractor_summary.html',
        {
            'projects': projects,
            'overall_billable': overall_billable,
            'overall_payments': overall_payments,
            'outstanding': outstanding,
        },
    )


@login_required
def project_list(request):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    projects = contractor.projects.all().annotate(
        total_billable=Sum('job_entries__billable_amount'),
        total_payments=Sum('payments__amount'),
    )
    for p in projects:
        p.outstanding = (p.total_billable or 0) - (p.total_payments or 0)
    return render(
        request,
        'dashboard/project_list.html',
        {
            'projects': projects,
        },
    )


@login_required
def project_detail(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    job_entries = project.job_entries.all()
    payments = project.payments.all()
    total_billable = job_entries.aggregate(total=Sum('billable_amount'))['total'] or 0
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0
    outstanding = total_billable - total_payments
    return render(
        request,
        'dashboard/project_detail.html',
        {
            'project': project,
            'job_entries': job_entries,
            'payments': payments,
            'total_billable': total_billable,
            'total_payments': total_payments,
            'outstanding': outstanding,
        },
    )


@login_required
def add_job_entry(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    assets = contractor.assets.all()
    employees = contractor.employees.all()
    materials = contractor.materials.all()

    if request.method == "POST":
        date = request.POST.get("date")
        hours = Decimal(request.POST.get("hours") or 0)
        asset_id = request.POST.get("asset")
        employee_id = request.POST.get("employee")
        material_id = request.POST.get("material")
        description = request.POST.get("description", "")

        asset = assets.filter(pk=asset_id).first() if asset_id else None
        employee = employees.filter(pk=employee_id).first() if employee_id else None
        material = materials.filter(pk=material_id).first() if material_id else None

        cost_amount = Decimal("0")
        billable_amount = Decimal("0")
        if asset:
            cost_amount += asset.cost_rate
            billable_amount += asset.billable_rate
        if employee:
            cost_amount += employee.cost_rate * hours
            billable_amount += employee.billable_rate * hours
        if material:
            cost_amount += material.actual_cost
            billable_amount += material.actual_cost * (
                1 + contractor.material_markup / Decimal("100")
            )

        JobEntry.objects.create(
            project=project,
            date=date,
            hours=hours,
            asset=asset,
            employee=employee,
            material=material,
            cost_amount=cost_amount,
            billable_amount=billable_amount,
            description=description,
        )
        return redirect("dashboard:project_detail", pk=project.pk)

    return render(
        request,
        "dashboard/jobentry_form.html",
        {
            "project": project,
            "assets": assets,
            "employees": employees,
            "materials": materials,
            "markup": contractor.material_markup,
        },
    )


@login_required
def add_payment(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)

    if request.method == "POST":
        date = request.POST.get("date")
        amount = Decimal(request.POST.get("amount") or 0)
        notes = request.POST.get("notes", "")
        Payment.objects.create(project=project, amount=amount, date=date, notes=notes)
        return redirect("dashboard:project_detail", pk=project.pk)

    return render(
        request,
        "dashboard/payment_form.html",
        {
            "project": project,
        },
    )


@login_required
def contractor_report(request):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    projects = contractor.projects.all().annotate(
        total_cost=Sum("job_entries__cost_amount"),
        total_billable=Sum("job_entries__billable_amount"),
    )
    for p in projects:
        p.margin = (p.total_billable or 0) - (p.total_cost or 0)
    context = {"contractor": contractor, "projects": projects}
    if request.GET.get("export") == "pdf":
        pdf = _render_pdf("dashboard/contractor_report.html", context)
        if pdf:
            pdf["Content-Disposition"] = "attachment; filename=contractor_report.pdf"
            return pdf
    return render(request, "dashboard/contractor_report.html", context)


@login_required
def customer_report(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    entries = project.job_entries.select_related("material").all()
    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
    }
    if request.GET.get("export") == "pdf":
        pdf = _render_pdf("dashboard/customer_report.html", context)
        if pdf:
            pdf["Content-Disposition"] = "attachment; filename=customer_report.pdf"
            return pdf
    return render(request, "dashboard/customer_report.html", context)
