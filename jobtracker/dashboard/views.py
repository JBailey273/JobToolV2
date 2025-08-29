from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from tracker.models import Asset, Employee, JobEntry, Material, Payment, Project


@login_required
def contractor_summary(request):
    contractor = request.user.contractor
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
            'contractor': contractor,
            'projects': projects,
            'overall_billable': overall_billable,
            'overall_payments': overall_payments,
            'outstanding': outstanding,
        },
    )


@login_required
def project_list(request):
    contractor = request.user.contractor
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
            'contractor': contractor,
            'projects': projects,
        },
    )


@login_required
def project_detail(request, pk):
    contractor = request.user.contractor
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
            'contractor': contractor,
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
    contractor = request.user.contractor
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

        if asset:
            cost_amount = asset.cost_rate * hours
            billable_amount = asset.billable_rate * hours
        elif employee:
            cost_amount = employee.cost_rate * hours
            billable_amount = employee.billable_rate * hours
        elif material:
            cost_amount = material.actual_cost * hours
            billable_amount = (
                material.actual_cost * (1 + contractor.material_markup / Decimal("100")) * hours
            )
        else:
            cost_amount = Decimal("0")
            billable_amount = Decimal("0")

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
            "contractor": contractor,
            "project": project,
            "assets": assets,
            "employees": employees,
            "materials": materials,
            "markup": contractor.material_markup,
        },
    )


@login_required
def add_payment(request, pk):
    contractor = request.user.contractor
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
            "contractor": contractor,
            "project": project,
        },
    )
