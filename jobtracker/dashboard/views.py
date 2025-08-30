from decimal import Decimal
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from tempfile import NamedTemporaryFile

try:
    from xhtml2pdf import pisa
except Exception:  # pragma: no cover - optional dependency
    pisa = None

from tracker.models import Asset, Employee, JobEntry, Payment, Project


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


def _render_pdf(template_src, context, filename):
    if pisa is None:
        return None
    template = get_template(template_src)
    html = template.render(context)
    tmp = NamedTemporaryFile()
    pdf = pisa.CreatePDF(html, dest=tmp, link_callback=link_callback)
    tmp.seek(0)
    if pdf.err:
        tmp.close()
        return None
    return FileResponse(tmp, as_attachment=True, filename=filename)


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
            'contractor': contractor,
            'contractor_logo_url': contractor.logo.url if contractor.logo else None,
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

    if request.method == "POST":
        date = request.POST.get("date")
        hours_list = request.POST.getlist("hours[]") or request.POST.getlist("hours")
        asset_ids = request.POST.getlist("asset[]") or request.POST.getlist("asset")
        employee_ids = request.POST.getlist("employee[]") or request.POST.getlist("employee")
        mat_descs = request.POST.getlist("material_description[]") or request.POST.getlist("material_description")
        mat_costs = request.POST.getlist("material_cost[]") or request.POST.getlist("material_cost")
        descriptions = request.POST.getlist("description[]") or request.POST.getlist("description")

        rows = zip(hours_list, asset_ids, employee_ids, mat_descs, mat_costs, descriptions)
        for hours, asset_id, employee_id, mat_desc, mat_cost, desc in rows:
            if not any([hours, asset_id, employee_id, mat_desc, mat_cost, desc]):
                continue
            asset = assets.filter(pk=asset_id).first() if asset_id else None
            employee = employees.filter(pk=employee_id).first() if employee_id else None
            hours_dec = Decimal(hours or 0)
            mat_cost_dec = Decimal(mat_cost or 0) if mat_cost else None
            JobEntry.objects.create(
                project=project,
                date=date,
                hours=hours_dec,
                asset=asset,
                employee=employee,
                material_description=mat_desc or "",
                material_cost=mat_cost_dec,
                description=desc or "",
            )
        return redirect("dashboard:project_detail", pk=project.pk)

    return render(
        request,
        "dashboard/jobentry_form.html",
        {
            "project": project,
            "assets": assets,
            "employees": employees,
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
    projects_qs = contractor.projects.all().annotate(
        total_cost=Sum("job_entries__cost_amount"),
        total_billable=Sum("job_entries__billable_amount"),
    )
    projects = []
    for p in projects_qs.iterator():
        total_billable = p.total_billable or Decimal("0")
        total_cost = p.total_cost or Decimal("0")
        p.profit = total_billable - total_cost
        p.margin = (
            (p.profit / total_billable) * Decimal("100") if total_billable else Decimal("0")
        )
        projects.append(p)
    logo_url = (
        contractor.logo_thumbnail.url
        if contractor and contractor.logo_thumbnail
        else None
    )
    export_pdf = request.GET.get("export") == "pdf"
    context = {
        "contractor": contractor,
        "projects": projects,
        "contractor_logo_url": logo_url,
        "report": export_pdf,
    }
    if export_pdf:
        pdf = _render_pdf(
            "dashboard/contractor_report.html", context, "contractor_report.pdf"
        )
        if pdf:
            return pdf
    return render(request, "dashboard/contractor_report.html", context)


@login_required
def customer_report(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    entries_qs = project.job_entries.select_related("asset", "employee")
    entries = list(entries_qs)
    total = project.job_entries.aggregate(total=Sum("billable_amount"))["total"] or 0
    payments = list(project.payments.all())
    total_payments = project.payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total - (total_payments or 0)
    logo_url = (
        contractor.logo_thumbnail.url
        if contractor and contractor.logo_thumbnail
        else None
    )
    show_description = any(e.description for e in entries)
    show_asset = any(e.asset for e in entries)
    show_employee = any(e.employee for e in entries)
    show_material = any(e.material_description for e in entries)
    cols_before_billable = 2 + int(show_description) + int(show_asset) + int(show_employee) + int(show_material)
    total_columns = cols_before_billable + 1
    export_pdf = request.GET.get("export") == "pdf"
    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
        "total": total,
        "contractor_logo_url": logo_url,
        "report": export_pdf,
        "show_description": show_description,
        "show_asset": show_asset,
        "show_employee": show_employee,
        "show_material": show_material,
        "colspan_before_total": cols_before_billable,
        "total_columns": total_columns,
        "payments": payments,
        "total_payments": total_payments or 0,
        "outstanding": outstanding,
    }
    if export_pdf:
        pdf = _render_pdf(
            "dashboard/customer_report.html", context, "customer_report.pdf"
        )
        if pdf:
            return pdf
    return render(request, "dashboard/customer_report.html", context)
