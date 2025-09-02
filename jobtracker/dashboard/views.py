from decimal import Decimal
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from io import BytesIO
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta

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
        return HttpResponse("PDF generation is unavailable", status=500)
    template = get_template(template_src)
    html = template.render(context)
    result = BytesIO()
    try:
        pdf = pisa.CreatePDF(html, dest=result, link_callback=link_callback)
    except Exception:
        return HttpResponse("Error generating PDF", status=500)
    if pdf.err:
        return HttpResponse("Error generating PDF", status=500)
    result.seek(0)
    response = HttpResponse(result.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@login_required
def contractor_summary(request):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    
    projects = contractor.projects.filter(end_date__isnull=True).prefetch_related(
        "job_entries", "payments"
    )
    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments
    first_project = projects.first()
    
    overall_billable = (
        JobEntry.objects.filter(project__contractor=contractor, project__end_date__isnull=True)
        .aggregate(total=Sum("billable_amount"))
        .get("total")
        or 0
    )
    overall_payments = (
        Payment.objects.filter(project__contractor=contractor, project__end_date__isnull=True)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    outstanding = overall_billable - overall_payments
    
    # Recent activity for dashboard
    recent_entries = JobEntry.objects.filter(
        project__contractor=contractor
    ).select_related('project', 'asset', 'employee').order_by('-date')[:5]
    
    recent_payments = Payment.objects.filter(
        project__contractor=contractor
    ).select_related('project').order_by('-date')[:5]
    
    return render(
        request,
        'dashboard/contractor_summary.html',
        {
            'projects': projects,
            'first_project': first_project,
            'overall_billable': overall_billable,
            'overall_payments': overall_payments,
            'outstanding': outstanding,
            'contractor': contractor,
            'contractor_logo_url': contractor.logo.url if contractor.logo else None,
            'recent_entries': recent_entries,
            'recent_payments': recent_payments,
        },
    )


@login_required
def project_list(request):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    
    # Search functionality
    search_query = request.GET.get('search', '')
    projects = contractor.projects.filter(end_date__isnull=True).prefetch_related(
        "job_entries", "payments"
    )
    
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(job_entries__description__icontains=search_query)
        ).distinct()
    
    total_billable = Decimal("0")
    total_payments = Decimal("0")
    
    for p in projects:
        p.total_billable = sum(
            (je.billable_amount or 0) for je in p.job_entries.all()
        )
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments
        total_billable += Decimal(p.total_billable)
        total_payments += Decimal(p.total_payments)
    
    total_outstanding = total_billable - total_payments
    
    return render(
        request,
        'dashboard/project_list.html',
        {
            'projects': projects,
            'total_billable': total_billable,
            'total_payments': total_payments,
            'total_outstanding': total_outstanding,
            'search_query': search_query,
        },
    )


@login_required
def project_detail(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    
    # Get filter parameters
    entry_filter = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset for job entries
    job_entries = project.job_entries.select_related('asset', 'employee').order_by('-date')
    
    # Apply filters
    if entry_filter == 'labor':
        job_entries = job_entries.filter(employee__isnull=False)
    elif entry_filter == 'equipment':
        job_entries = job_entries.filter(asset__isnull=False)
    elif entry_filter == 'materials':
        job_entries = job_entries.exclude(material_description='')
    
    # Apply search
    if search_query:
        job_entries = job_entries.filter(
            Q(description__icontains=search_query) |
            Q(material_description__icontains=search_query) |
            Q(asset__name__icontains=search_query) |
            Q(employee__name__icontains=search_query)
        )
    
    payments = project.payments.all().order_by('-date')
    
    # Calculate totals
    total_billable = job_entries.aggregate(total=Sum('billable_amount'))['total'] or 0
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0
    outstanding = total_billable - total_payments
    
    # Analytics data
    total_cost = job_entries.aggregate(total=Sum('cost_amount'))['total'] or 0
    profit = total_billable - total_cost
    margin = (profit / total_billable * 100) if total_billable > 0 else 0
    
    # Weekly breakdown for analytics
    weekly_data = []
    for week in range(4):  # Last 4 weeks
        start_date = timezone.now().date() - timedelta(weeks=week+1)
        end_date = start_date + timedelta(days=6)
        
        week_entries = job_entries.filter(date__range=[start_date, end_date])
        week_hours = week_entries.aggregate(hours=Sum('hours'))['hours'] or 0
        week_billable = week_entries.aggregate(total=Sum('billable_amount'))['total'] or 0
        week_cost = week_entries.aggregate(total=Sum('cost_amount'))['total'] or 0
        
        weekly_data.append({
            'week': f"{start_date.strftime('%b %d')}-{end_date.strftime('%d')}",
            'hours': week_hours,
            'billable': week_billable,
            'cost': week_cost,
        })
    
    weekly_data.reverse()  # Show oldest to newest
    
    return render(
        request,
        'dashboard/project_detail.html',
        {
            'project': project,
            'job_entries': job_entries[:20],  # Limit for performance
            'payments': payments[:10],
            'total_billable': total_billable,
            'total_payments': total_payments,
            'outstanding': outstanding,
            'total_cost': total_cost,
            'profit': profit,
            'margin': margin,
            'weekly_data': weekly_data,
            'entry_filter': entry_filter,
            'search_query': search_query,
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
        entries_created = 0
        
        # Process labor/equipment entries
        hours_list = request.POST.getlist("hours[]") or request.POST.getlist("hours")
        asset_ids = request.POST.getlist("asset[]") or request.POST.getlist("asset")
        employee_ids = request.POST.getlist("employee[]") or request.POST.getlist("employee")
        descriptions = request.POST.getlist("description[]") or request.POST.getlist("description")

        # Create labor/equipment entries
        labor_entries = zip(hours_list, asset_ids, employee_ids, descriptions)
        for hours, asset_id, employee_id, desc in labor_entries:
            if not any([hours, asset_id, employee_id, desc]):
                continue
            
            asset = assets.filter(pk=asset_id).first() if asset_id else None
            employee = employees.filter(pk=employee_id).first() if employee_id else None
            hours_dec = Decimal(hours or 0)
            
            if hours_dec > 0 or asset or employee:
                JobEntry.objects.create(
                    project=project,
                    date=date,
                    hours=hours_dec,
                    asset=asset,
                    employee=employee,
                    material_description="",
                    material_cost=None,
                    description=desc or "",
                )
                entries_created += 1
        
        # Process materials entries
        material_descriptions = request.POST.getlist("material_description[]")
        material_quantities = request.POST.getlist("material_quantity[]")
        material_units = request.POST.getlist("material_unit[]")
        material_costs = request.POST.getlist("material_cost[]")
        
        if material_descriptions:
            materials = zip(material_descriptions, material_quantities, material_units, material_costs)
            for desc, qty, unit, cost in materials:
                if not any([desc, qty, cost]):
                    continue
                
                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)
                
                if desc and qty_dec > 0 and cost_dec > 0:
                    # Create material entry with description including unit
                    full_desc = f"{desc} ({qty_dec} {unit})" if unit else desc
                    
                    JobEntry.objects.create(
                        project=project,
                        date=date,
                        hours=qty_dec,  # Use quantity as hours for materials
                        asset=None,
                        employee=None,
                        material_description=full_desc,
                        material_cost=cost_dec,
                        description=f"Material: {full_desc}",
                    )
                    entries_created += 1
        
        if entries_created > 0:
            messages.success(request, f"Successfully created {entries_created} job entries.")
        else:
            messages.warning(request, "No entries were created. Please fill in at least one complete entry.")
        
        return redirect("dashboard:project_detail", pk=project.pk)

    return render(
        request,
        "dashboard/jobentry_form.html",
        {
            "project": project,
            "assets": assets,
            "employees": employees,
            "margin": contractor.material_margin,
        },
    )


@login_required
def edit_job_entry(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    
    entry = get_object_or_404(JobEntry, pk=pk, project__contractor=contractor)
    assets = contractor.assets.all()
    employees = contractor.employees.all()

    if request.method == "POST":
        entry.date = request.POST.get("date")
        entry.hours = Decimal(request.POST.get("hours") or 0)
        
        asset_id = request.POST.get("asset")
        employee_id = request.POST.get("employee")
        
        entry.asset = assets.filter(pk=asset_id).first() if asset_id else None
        entry.employee = employees.filter(pk=employee_id).first() if employee_id else None
        
        entry.material_description = request.POST.get("material_description", "")
        mat_cost = request.POST.get("material_cost")
        entry.material_cost = Decimal(mat_cost or 0) if mat_cost else None
        entry.description = request.POST.get("description", "")
        
        entry.save()
        messages.success(request, "Job entry updated successfully.")
        return redirect("dashboard:project_detail", pk=entry.project.pk)

    return render(
        request,
        "dashboard/jobentry_edit_form.html",
        {
            "entry": entry,
            "assets": assets,
            "employees": employees,
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
        
        if amount > 0:
            Payment.objects.create(
                project=project, 
                amount=amount, 
                date=date, 
                notes=notes
            )
            messages.success(request, f"Payment of ${amount:,.2f} recorded successfully.")
        else:
            messages.error(request, "Please enter a valid payment amount.")
        
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
    total_revenue = Decimal("0")
    total_cost = Decimal("0")
    total_profit = Decimal("0")
    total_margin = Decimal("0")
    profitable = 0
    breakeven = 0
    unprofitable = 0
    
    for p in projects_qs.iterator():
        billable = p.total_billable or Decimal("0")
        cost = p.total_cost or Decimal("0")
        profit = billable - cost
        margin = (profit / billable * Decimal("100")) if billable else Decimal("0")
        
        p.profit = profit
        p.margin = margin
        projects.append(p)
        
        total_revenue += billable
        total_cost += cost
        total_profit += profit
        total_margin += margin
        
        if profit > 100:
            profitable += 1
        elif profit >= 0:
            breakeven += 1
        else:
            unprofitable += 1
    
    avg_margin = (total_margin / len(projects)) if projects else Decimal("0")
    roi = (total_profit / total_cost * Decimal("100")) if total_cost else None
    
    export_pdf = request.GET.get("export") == "pdf"
    logo_url = (
        contractor.logo_thumbnail.url
        if export_pdf and contractor and contractor.logo_thumbnail
        else contractor.logo.url if contractor and contractor.logo else None
    )
    
    context = {
        "contractor": contractor,
        "projects": projects,
        "contractor_logo_url": logo_url,
        "report": export_pdf,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "average_margin": avg_margin,
        "roi": roi,
        "profitable_count": profitable,
        "breakeven_count": breakeven,
        "unprofitable_count": unprofitable,
    }
    
    if export_pdf:
        pdf = _render_pdf(
            "dashboard/contractor_report.html", context, "contractor_summary_report.pdf"
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
    entries_qs = project.job_entries.select_related("asset", "employee").order_by("-date")
    entries = list(entries_qs)
    total = project.job_entries.aggregate(total=Sum("billable_amount"))["total"] or 0
    payments = list(project.payments.all())
    total_payments = project.payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total - (total_payments or 0)
    
    export_pdf = request.GET.get("export") == "pdf"
    logo_url = (
        contractor.logo_thumbnail.url
        if export_pdf and contractor and contractor.logo_thumbnail
        else contractor.logo.url if contractor and contractor.logo else None
    )
    
    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
        "total": total,
        "contractor_logo_url": logo_url,
        "report": export_pdf,
        "colspan_before_total": 6,
        "total_columns": 7,
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


@login_required
def contractor_job_report(request, pk):
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return redirect("login")
    
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    entries_qs = project.job_entries.select_related("asset", "employee").order_by("-date")
    entries = []
    total_billable = Decimal("0")
    total_cost = Decimal("0")
    
    for e in entries_qs.iterator():
        billable = e.billable_amount or Decimal("0")
        cost = e.cost_amount or Decimal("0")
        profit = billable - cost
        margin = (profit / billable * Decimal("100")) if billable else Decimal("0")
        
        e.profit = profit
        e.margin = margin
        entries.append(e)
        total_billable += billable
        total_cost += cost
    
    total_profit = total_billable - total_cost
    overall_margin = (
        (total_profit / total_billable) * Decimal("100") if total_billable else Decimal("0")
    )
    
    payments = list(project.payments.all())
    total_payments = project.payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total_billable - (total_payments or 0)
    
    export_pdf = request.GET.get("export") == "pdf"
    logo_url = (
        contractor.logo_thumbnail.url
        if export_pdf and contractor and contractor.logo_thumbnail
        else contractor.logo.url if contractor and contractor.logo else None
    )
    
    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
        "total_billable": total_billable,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "overall_margin": overall_margin,
        "contractor_logo_url": logo_url,
        "report": export_pdf,
        "payments": payments,
        "total_payments": total_payments or 0,
        "outstanding": outstanding,
        "colspan_before_total": 6,
        "total_columns": 10,
    }
    
    if export_pdf:
        pdf = _render_pdf(
            "dashboard/contractor_job_report.html", context, "contractor_job_report.pdf"
        )
        if pdf:
            return pdf
    
    return render(request, "dashboard/contractor_job_report.html", context)


# API endpoints for enhanced functionality
@login_required
def search_entries(request):
    """API endpoint for searching entries"""
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    query = request.GET.get('q', '')
    project_id = request.GET.get('project_id')
    
    entries = JobEntry.objects.filter(project__contractor=contractor)
    
    if project_id:
        entries = entries.filter(project_id=project_id)
    
    if query:
        entries = entries.filter(
            Q(description__icontains=query) |
            Q(material_description__icontains=query) |
            Q(asset__name__icontains=query) |
            Q(employee__name__icontains=query)
        )

    entries = entries.order_by('-date')
    
    results = []
    for entry in entries[:10]:  # Limit results
        results.append({
            'id': entry.id,
            'date': entry.date.strftime('%Y-%m-%d'),
            'description': entry.description,
            'amount': str(entry.billable_amount),
            'project': entry.project.name,
        })
    
    return JsonResponse({'results': results})


@login_required
def get_material_templates(request):
    """API endpoint for material templates"""
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    # This could be expanded to store actual templates in the database
    # For now, return some common templates
    templates = [
        {
            'name': 'Office Supplies Basic',
            'materials': [
                {'description': 'Office Supplies - Basic', 'quantity': 1, 'unit': 'Each', 'cost': 25.00},
                {'description': 'Printer Paper', 'quantity': 5, 'unit': 'Reams', 'cost': 8.50},
                {'description': 'Writing Supplies', 'quantity': 1, 'unit': 'Set', 'cost': 15.00},
            ]
        },
        {
            'name': 'Basic Maintenance',
            'materials': [
                {'description': 'Cleaning Supplies', 'quantity': 1, 'unit': 'Each', 'cost': 15.00},
                {'description': 'Safety Equipment', 'quantity': 1, 'unit': 'Each', 'cost': 45.00},
                {'description': 'Maintenance Tools', 'quantity': 1, 'unit': 'Set', 'cost': 35.00},
            ]
        }
    ]
    
    return JsonResponse({'templates': templates})


@login_required
def project_analytics_data(request, pk):
    """API endpoint for project analytics data"""
    contractor = getattr(request.user, "contractor", None)
    if contractor is None:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    
    # Weekly breakdown
    weekly_data = []
    for week in range(8):  # Last 8 weeks
        start_date = timezone.now().date() - timedelta(weeks=week+1)
        end_date = start_date + timedelta(days=6)
        
        week_entries = project.job_entries.filter(date__range=[start_date, end_date])
        week_hours = week_entries.aggregate(hours=Sum('hours'))['hours'] or 0
        week_billable = week_entries.aggregate(total=Sum('billable_amount'))['total'] or 0
        week_cost = week_entries.aggregate(total=Sum('cost_amount'))['total'] or 0
        
        weekly_data.append({
            'week': f"{start_date.strftime('%b %d')}",
            'hours': float(week_hours),
            'billable': float(week_billable),
            'cost': float(week_cost),
        })
    
    weekly_data.reverse()
    
    # Category breakdown
    labor_total = project.job_entries.filter(employee__isnull=False).aggregate(
        total=Sum('billable_amount'))['total'] or 0
    equipment_total = project.job_entries.filter(asset__isnull=False).aggregate(
        total=Sum('billable_amount'))['total'] or 0
    materials_total = project.job_entries.exclude(material_description='').aggregate(
        total=Sum('billable_amount'))['total'] or 0
    
    return JsonResponse({
        'weekly_data': weekly_data,
        'category_breakdown': {
            'labor': float(labor_total),
            'equipment': float(equipment_total),
            'materials': float(materials_total),
        },
        'totals': {
            'billable': float(project.job_entries.aggregate(total=Sum('billable_amount'))['total'] or 0),
            'cost': float(project.job_entries.aggregate(total=Sum('cost_amount'))['total'] or 0),
        }
    })
