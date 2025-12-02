from decimal import Decimal, InvalidOperation
from collections import defaultdict
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None

from tracker.models import (
    Asset,
    Employee,
    JobEntry,
    Payment,
    Project,
    Estimate,
    EstimateEntry,
)


def safe_decimal(value, default=Decimal("0")):
    """Return a Decimal, falling back to default on invalid input."""
    try:
        return Decimal(value)
    except (TypeError, InvalidOperation, ValueError):
        return default


def get_contractor(user):
    """Safely return the contractor associated with the given user."""
    try:
        return user.contractor
    except ObjectDoesNotExist:
        return None


# Update this function in your dashboard/views.py file
def _render_pdf(template_src, context, filename, request=None):
    """Render PDF with proper base_url for images.

    Returns None instead of an error response when PDF generation isn't available
    so callers can gracefully fall back to the HTML view without throwing a 500.
    """
    if HTML is None:
        if request:
            messages.error(
                request,
                "PDF generation is unavailable on this server. Please contact the administrator.",
            )
        return None

    template = get_template(template_src)
    html = template.render(context)

    try:
        # Use request.build_absolute_uri() for proper image loading
        if request:
            base_url = request.build_absolute_uri('/')
        else:
            base_url = str(settings.BASE_DIR)
            
        pdf = HTML(
            string=html,
            base_url=base_url,
            encoding='utf-8'
        ).write_pdf()
    except Exception as e:
        print(f"PDF Generation Error: {e}")  # For debugging
        if request:
            messages.error(
                request,
                "There was a problem generating the PDF. Please try again later.",
            )
            return None
        return HttpResponse("Error generating PDF", status=500)

    start = pdf.find(b"%PDF")
    if start == -1:
        if request:
            messages.error(
                request,
                "PDF generation failed. Please try again later.",
            )
            return None
        return HttpResponse("Error generating PDF", status=500)
    
    response = HttpResponse(pdf[start:], content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response



@login_required
def contractor_summary(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    projects = contractor.projects.filter(
        end_date__isnull=True
    ).prefetch_related("job_entries", "payments")
    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments
    first_project = projects.first()

    overall_billable = (
        JobEntry.objects.filter(
            project__contractor=contractor, project__end_date__isnull=True
        )
        .aggregate(total=Sum("billable_amount"))
        .get("total")
        or 0
    )
    overall_payments = (
        Payment.objects.filter(
            project__contractor=contractor, project__end_date__isnull=True
        )
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    outstanding = overall_billable - overall_payments

    # Recent activity for dashboard
    recent_entries = (
        JobEntry.objects.filter(project__contractor=contractor)
        .select_related("project", "asset", "employee")
        .order_by("-date")[:5]
    )

    recent_payments = (
        Payment.objects.filter(project__contractor=contractor)
        .select_related("project")
        .order_by("-date")[:5]
    )

    current_hour = timezone.localtime().hour
    if current_hour < 12:
        greeting = "Good Morning"
    elif current_hour < 18:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"

    return render(
        request,
        "dashboard/contractor_summary.html",
        {
            "projects": projects,
            "first_project": first_project,
            "overall_billable": overall_billable,
            "overall_payments": overall_payments,
            "outstanding": outstanding,
            "contractor": contractor,
            "contractor_logo_url": contractor.logo.url if contractor.logo else None,
            "recent_entries": recent_entries,
            "recent_payments": recent_payments,
            "greeting": greeting,
        },
    )


@login_required
def project_list(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")
    if request.method == "POST":
        name = request.POST.get("name")
        start_date = request.POST.get("start_date") or timezone.now().date()
        if name:
            Project.objects.create(
                contractor=contractor, name=name, start_date=start_date
            )
            messages.success(request, f"Project '{name}' created.")
        return redirect("dashboard:project_list")

    # Search functionality
    search_query = request.GET.get("search", "")
    projects = contractor.projects.filter(
        end_date__isnull=True
    ).prefetch_related("job_entries", "payments")

    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query)
            | Q(job_entries__description__icontains=search_query)
        ).distinct()

    total_billable = Decimal("0")
    total_payments = Decimal("0")

    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments
        total_billable += Decimal(p.total_billable)
        total_payments += Decimal(p.total_payments)

    total_outstanding = total_billable - total_payments

    today = timezone.now().date()

    return render(
        request,
        "dashboard/project_list.html",
        {
            "projects": projects,
            "total_billable": total_billable,
            "total_payments": total_payments,
            "total_outstanding": total_outstanding,
            "search_query": search_query,
            "today": today,
        },
    )


@login_required
def estimate_list(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    if request.method == "POST":
        name = request.POST.get("name", "New Estimate")
        estimate = contractor.estimates.create(name=name)
        return redirect("dashboard:add_estimate_entry", pk=estimate.pk)

    try:
        print("=== ESTIMATE LIST DEBUG ===")
        
        estimates = contractor.estimates.all().prefetch_related("entries")
        print(f"Found {estimates.count()} estimates")
        
        # Calculate totals and summary statistics
        total_value = Decimal("0")
        total_profit = Decimal("0")
        accepted_count = 0
        
        today = timezone.now().date()
        week_from_now = today + timedelta(days=7)
        
        estimates_list = []
        
        for est in estimates:
            try:
                print(f"Processing estimate: {est.id} - {est.name}")
                
                # Use the model's @property methods directly - don't try to override them
                calculated_billable = est.total_billable  # This calls the @property method
                calculated_cost = est.total_cost          # This calls the @property method
                calculated_profit = est.total_profit      # This calls the @property method
                calculated_margin = est.profit_margin     # This calls the @property method
                
                print(f"  Calculated totals: Billable=${calculated_billable}, Cost=${calculated_cost}")
                
                # Add calculated values as new attributes (not overriding properties)
                est.display_total_billable = calculated_billable
                est.display_total_cost = calculated_cost
                est.display_total_profit = calculated_profit
                est.display_profit_margin = calculated_margin
                
                # Add to summary totals
                total_value += calculated_billable
                total_profit += calculated_profit
                
                # Check status
                if getattr(est, 'status', 'draft') == 'accepted':
                    accepted_count += 1
                
                estimates_list.append(est)
                    
            except Exception as e:
                print(f"Error processing estimate {est.id}: {e}")
                import traceback
                traceback.print_exc()
                
                # Add with safe defaults
                est.display_total_billable = Decimal("0")
                est.display_total_cost = Decimal("0") 
                est.display_total_profit = Decimal("0")
                est.display_profit_margin = Decimal("0")
                estimates_list.append(est)
                continue

        print(f"Summary totals: Value=${total_value}, Profit=${total_profit}, Accepted={accepted_count}")

        return render(request, "dashboard/estimate_list.html", {
            "estimates": estimates_list,
            "total_value": total_value,
            "total_profit": total_profit,
            "accepted_count": accepted_count,
            "today": today,
            "week_from_now": week_from_now,
        })
        
    except Exception as e:
        print(f"CRITICAL ERROR in estimate_list: {e}")
        import traceback
        traceback.print_exc()
        
        return HttpResponse(f"""
        <h1>Critical Error in estimate_list</h1>
        <p>Error: {e}</p>
        <pre>{traceback.format_exc()}</pre>
        """)


@login_required
def accept_estimate(request, pk):
    """Convert an estimate to a project"""
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")
    
    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    
    if request.method == "POST":
        try:
            # Create a new project from the estimate
            project = Project.objects.create(
                contractor=contractor,
                name=estimate.name,
                start_date=estimate.created_date,
                estimate=estimate,
            )
            
            # Convert all estimate entries to job entries
            for estimate_entry in estimate.entries.all():
                JobEntry.objects.create(
                    project=project,
                    date=estimate_entry.date,
                    hours=estimate_entry.hours,
                    asset=estimate_entry.asset,
                    employee=estimate_entry.employee,
                    material_description=estimate_entry.material_description,
                    material_cost=estimate_entry.material_cost,
                    service_markup=estimate_entry.service_markup,
                    description=estimate_entry.description,
                )
            
            # Update estimate status
            estimate.status = 'accepted'
            estimate.save()

            # Remove the estimate record once it's converted
            estimate.delete()
            
            messages.success(
                request, 
                f"Estimate '{estimate.name}' has been accepted and converted to project '{project.name}'."
            )
            
            return redirect("dashboard:project_detail", pk=project.pk)
            
        except Exception as e:
            messages.error(request, f"Error converting estimate: {e}")
            return redirect("dashboard:estimate_list")
    
    return redirect("dashboard:estimate_list")


@login_required
def delete_estimate(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")
    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    if request.method == "POST":
        estimate.delete()
        messages.success(request, "Estimate deleted.")
        return redirect("dashboard:estimate_list")
    return redirect("dashboard:estimate_list")


@login_required
def delete_project(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")
    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted.")
        return redirect("dashboard:project_list")
    return redirect("dashboard:project_detail", pk=pk)


@login_required
def reports(request):
    """Display available report links."""
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    projects = contractor.projects.filter(
        end_date__isnull=True
    ).prefetch_related("job_entries", "payments")

    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments

    return render(
        request,
        "dashboard/reports.html",
        {
            "projects": projects,
        },
    )


# Add this updated project_detail function to your existing views.py file
# Replace the existing project_detail function with this enhanced version

@login_required
def project_detail(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    project = get_object_or_404(Project, pk=pk, contractor=contractor)

    # Get filter parameters
    entry_filter = request.GET.get("filter", "all")
    search_query = request.GET.get("search", "")

    # Base queryset for job entries
    job_entries = project.job_entries.select_related("asset", "employee").order_by(
        "-date"
    )

    # Apply filters
    if entry_filter == "labor":
        job_entries = job_entries.filter(employee__isnull=False)
    elif entry_filter == "equipment":
        job_entries = job_entries.filter(asset__isnull=False)
    elif entry_filter == "materials":
        job_entries = job_entries.exclude(material_description="")

    # Apply search
    if search_query:
        job_entries = job_entries.filter(
            Q(description__icontains=search_query)
            | Q(material_description__icontains=search_query)
            | Q(asset__name__icontains=search_query)
            | Q(employee__name__icontains=search_query)
        )

    job_entries_qs = job_entries
    payments = list(project.payments.all().order_by("-date"))

    # Convert queryset to list for repeated iteration, guarding against bad data
    try:
        job_entries = list(job_entries_qs)
    except Exception:
        job_entries = []

    # Build timeline combining job entries and payments
    entries_by_date = defaultdict(list)
    for je in job_entries:
        if getattr(je, "date", None):
            entries_by_date[je.date].append(je)

    payments_by_date = defaultdict(list)
    for payment in payments:
        if getattr(payment, "date", None):
            payments_by_date[payment.date].append(payment)

    timeline_items = []
    for dt in sorted(set(entries_by_date) | set(payments_by_date), reverse=True):
        if dt in entries_by_date:
            timeline_items.append({"date": dt, "entries": entries_by_date[dt]})
        if dt in payments_by_date:
            timeline_items.append({"date": dt, "payments": payments_by_date[dt]})

    # Calculate totals
    total_billable = sum(((je.billable_amount or Decimal("0")) for je in job_entries), Decimal("0"))
    total_payments = sum(((p.amount or Decimal("0")) for p in payments), Decimal("0"))
    outstanding = total_billable - total_payments
    collection_rate = float(total_payments / total_billable * 100) if total_billable else 0

    # Enhanced cost and billable breakdowns for analytics
    labor_cost = equipment_cost = material_cost = Decimal("0")
    billable_labor = billable_equipment = billable_material = Decimal("0")

    # Get contractor's material margin
    raw_margin = getattr(project.contractor, "material_margin", 0)
    contractor_margin = safe_decimal(raw_margin)
    material_margin = contractor_margin / Decimal("100") if contractor_margin else Decimal("0")
    margin_multiplier = Decimal("1") - material_margin

    try:
        for je in job_entries:
            hours = safe_decimal(getattr(je, "hours", 0))
            
            # Labor calculations
            if je.employee:
                emp_cost_rate = safe_decimal(getattr(je.employee, "cost_rate", 0))
                emp_billable_rate = safe_decimal(getattr(je.employee, "billable_rate", 0))
                labor_cost += emp_cost_rate * hours
                billable_labor += emp_billable_rate * hours
            
            # Equipment calculations
            if je.asset:
                asset_cost_rate = safe_decimal(getattr(je.asset, "cost_rate", 0))
                asset_billable_rate = safe_decimal(getattr(je.asset, "billable_rate", 0))
                equipment_cost += asset_cost_rate * hours
                billable_equipment += asset_billable_rate * hours
            
            # Material calculations
            if je.material_cost:
                mat_cost = safe_decimal(je.material_cost) * hours
                material_cost += mat_cost
                if margin_multiplier > 0:
                    billable_material += mat_cost / margin_multiplier
                else:
                    # If no margin multiplier, use the billable amount directly
                    billable_material += safe_decimal(getattr(je, "billable_amount", 0))
    except Exception:
        # Fallback to zero values if calculation fails
        labor_cost = equipment_cost = material_cost = Decimal("0")
        billable_labor = billable_equipment = billable_material = Decimal("0")

    # Calculate totals and percentages
    total_cost = labor_cost + equipment_cost + material_cost
    profit = total_billable - total_cost
    margin = (profit / total_billable * 100) if total_billable else 0

    # Cost breakdown percentages
    if total_cost > 0:
        labor_percent = float(labor_cost / total_cost * 100)
        equipment_percent = float(equipment_cost / total_cost * 100)
        material_percent = float(material_cost / total_cost * 100)
    else:
        labor_percent = equipment_percent = material_percent = 0

    # Billable breakdown percentages
    if total_billable > 0:
        billable_labor_percent = float(billable_labor / total_billable * 100)
        billable_equipment_percent = float(billable_equipment / total_billable * 100)
        billable_material_percent = float(billable_material / total_billable * 100)
    else:
        billable_labor_percent = billable_equipment_percent = billable_material_percent = 0

    # Profit metrics for each category
    labor_profit = billable_labor - labor_cost
    equipment_profit = billable_equipment - equipment_cost
    material_profit = billable_material - material_cost

    # Cost vs revenue percentages for progress bars
    if billable_labor > 0:
        labor_cost_percent = float(labor_cost / billable_labor * 100)
        labor_profit_percent = 100 - labor_cost_percent
    else:
        labor_cost_percent = labor_profit_percent = 0

    if billable_equipment > 0:
        equip_cost_percent = float(equipment_cost / billable_equipment * 100)
        equip_profit_percent = 100 - equip_cost_percent
    else:
        equip_cost_percent = equip_profit_percent = 0

    if billable_material > 0:
        mat_cost_percent = float(material_cost / billable_material * 100)
        mat_profit_percent = 100 - mat_cost_percent
    else:
        mat_cost_percent = mat_profit_percent = 0

    # Weekly breakdown for trends - Enhanced for analytics
    weekly_data = []
    current_date = timezone.now().date()
    start_date = project.start_date

    while start_date <= current_date:
        end_date = start_date + timedelta(days=6)

        # Filter entries for this week
        week_entries = [
            je for je in job_entries
            if hasattr(je, "date") and je.date and start_date <= je.date <= end_date
        ]

        # Calculate totals for the week
        week_hours = sum(
            (
                safe_decimal(getattr(je, "hours", 0))
                for je in week_entries
                if not getattr(je, "material_description", "")
            ),
            Decimal("0"),
        )
        week_billable = sum(
            (safe_decimal(getattr(je, "billable_amount", 0)) for je in week_entries),
            Decimal("0"),
        )

        # Calculate week costs more accurately
        week_cost = Decimal("0")
        for je in week_entries:
            hours = safe_decimal(getattr(je, "hours", 0))
            if je.employee:
                week_cost += safe_decimal(getattr(je.employee, "cost_rate", 0)) * hours
            if je.asset:
                week_cost += safe_decimal(getattr(je.asset, "cost_rate", 0)) * hours
            if je.material_cost:
                week_cost += safe_decimal(je.material_cost) * hours

        weekly_data.append(
            {
                "week": f"{start_date.strftime('%b %d')}",
                "hours": float(week_hours),
                "billable": float(week_billable),
                "cost": float(week_cost),
            }
        )

        start_date += timedelta(weeks=1)

    # Determine maximum value for scaling trend bars
    max_weekly_value = max(
        (max(d["billable"], d["cost"]) for d in weekly_data),
        default=0,
    ) or 1

    # Additional analytics calculations
    has_employee_entries = any(getattr(je, "employee", None) for je in job_entries)
    total_hours = sum(
        (
            safe_decimal(getattr(je, "hours", 0))
            for je in job_entries
            if (
                (
                    has_employee_entries
                    and getattr(je, "employee", None)
                )
                or (
                    not has_employee_entries
                    and getattr(je, "asset", None)
                )
            )
            and not getattr(je, "material_description", "")
        ),
        Decimal("0"),
    )
    avg_hourly_rate = (total_billable / total_hours) if total_hours > 0 else Decimal("0")

    project_duration_weeks = max(1, ((current_date - project.start_date).days // 7) + 1)
    potential_hours = Decimal(project_duration_weeks * 40)
    resource_utilization = (
        float(total_hours / potential_hours * 100) if potential_hours > 0 else 0
    )

    return render(
        request,
        "dashboard/project_detail.html",
        {
            "project": project,
            "job_entries": job_entries,
            "payments": payments[:10],  # Limit payments displayed
            "timeline_items": timeline_items,
            "total_billable": total_billable,
            "total_payments": total_payments,
            "outstanding": outstanding,
            "collection_rate": collection_rate,
            "total_cost": total_cost,
            "profit": profit,
            "margin": margin,
            
            # Enhanced category breakdowns
            "labor_cost": labor_cost,
            "equipment_cost": equipment_cost,
            "material_cost": material_cost,
            "labor_percent": labor_percent,
            "equipment_percent": equipment_percent,
            "material_percent": material_percent,
            
            # Billable breakdowns
            "billable_labor": billable_labor,
            "billable_equipment": billable_equipment,
            "billable_material": billable_material,
            "billable_labor_percent": billable_labor_percent,
            "billable_equipment_percent": billable_equipment_percent,
            "billable_material_percent": billable_material_percent,

            # Category profit and cost percentages
            "labor_profit": labor_profit,
            "equipment_profit": equipment_profit,
            "material_profit": material_profit,
            "labor_cost_percent": labor_cost_percent,
            "labor_profit_percent": labor_profit_percent,
            "equip_cost_percent": equip_cost_percent,
            "equip_profit_percent": equip_profit_percent,
            "mat_cost_percent": mat_cost_percent,
            "mat_profit_percent": mat_profit_percent,

            # Enhanced analytics data
            "weekly_data": weekly_data,
            "max_weekly_value": max_weekly_value,
            "total_hours": total_hours,
            "avg_hourly_rate": avg_hourly_rate,
            "resource_utilization": resource_utilization,
            
            # Filter and search parameters
            "entry_filter": entry_filter,
            "search_query": search_query,
        },
    )

@login_required
def select_job_entry_project(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    projects = contractor.projects.filter(
        end_date__isnull=True
    ).prefetch_related("job_entries", "payments")

    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments

    if not projects.exists():
        messages.info(request, "Please create a project before adding job entries.")
        return redirect("dashboard:project_list")

    return render(
        request,
        "dashboard/select_project.html",
        {
            "projects": projects,
            "action_url_name": "dashboard:add_job_entry",
            "page_title": "Select Project for Job Entry",
        },
    )


@login_required
def select_payment_project(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    projects = contractor.projects.filter(
        end_date__isnull=True
    ).prefetch_related("job_entries", "payments")

    for p in projects:
        p.total_billable = sum((je.billable_amount or 0) for je in p.job_entries.all())
        p.total_payments = sum((pay.amount or 0) for pay in p.payments.all())
        p.outstanding = p.total_billable - p.total_payments

    if not projects.exists():
        messages.info(request, "Please create a project before recording payments.")
        return redirect("dashboard:project_list")

    return render(
        request,
        "dashboard/select_project.html",
        {
            "projects": projects,
            "action_url_name": "dashboard:add_payment",
            "page_title": "Select Project for Payment",
        },
    )


@login_required
def add_job_entry(request, pk):
    contractor = get_contractor(request.user)
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
            materials = zip(
                material_descriptions,
                material_quantities,
                material_units,
                material_costs,
            )
            for desc, qty, unit, cost in materials:
                if not any([desc, qty, cost]):
                    continue

                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)

                if desc and qty_dec > 0 and cost_dec > 0:
                    # Create material entry with description including unit
                    suffix = f"({qty_dec} {unit})" if unit else ""
                    desc_stripped = desc.strip()
                    full_desc = (
                        f"{desc_stripped} {suffix}".strip()
                        if suffix and not desc_stripped.endswith(suffix)
                        else desc_stripped
                    )

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
            messages.success(
                request, f"Successfully created {entries_created} job entries."
            )
        else:
            messages.warning(
                request,
                "No entries were created. Please fill in at least one complete entry.",
            )

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
    contractor = get_contractor(request.user)
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
        entry.employee = (
            employees.filter(pk=employee_id).first() if employee_id else None
        )

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
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    project = get_object_or_404(Project, pk=pk, contractor=contractor)

    if request.method == "POST":
        date = request.POST.get("date")
        amount = Decimal(request.POST.get("amount") or 0)
        notes = request.POST.get("notes", "")

        if amount > 0:
            Payment.objects.create(
                project=project, amount=amount, date=date, notes=notes
            )
            messages.success(
                request, f"Payment of ${amount:,.2f} recorded successfully."
            )
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
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    projects_qs = contractor.projects.annotate(
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
    context = {
        "contractor": contractor,
        "projects": projects,
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
            "dashboard/contractor_report.html",
            context,
            "contractor_summary_report.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/contractor_report.html", context)


@login_required
def customer_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    entries_qs = project.job_entries.select_related("asset", "employee").order_by(
        "-date"
    )
    entries = list(entries_qs)
    total = project.job_entries.aggregate(total=Sum("billable_amount"))["total"] or 0
    payments = list(project.payments.all())
    total_payments = project.payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total - (total_payments or 0)

    export_pdf = request.GET.get("export") == "pdf"

    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
        "total": total,
        "report": export_pdf,
        "colspan_before_total": 6,
        "total_columns": 7,
        "payments": payments,
        "total_payments": total_payments or 0,
        "outstanding": outstanding,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/customer_report.html",
            context,
            "customer_report.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/customer_report.html", context)


@login_required
def contractor_job_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    project = get_object_or_404(Project, pk=pk, contractor=contractor)
    entries_qs = project.job_entries.select_related("asset", "employee").order_by(
        "-date"
    )
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
        (total_profit / total_billable) * Decimal("100")
        if total_billable
        else Decimal("0")
    )

    payments = list(project.payments.all())
    total_payments = project.payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total_billable - (total_payments or 0)

    export_pdf = request.GET.get("export") == "pdf"

    context = {
        "contractor": contractor,
        "project": project,
        "entries": entries,
        "total_billable": total_billable,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "overall_margin": overall_margin,
        "report": export_pdf,
        "payments": payments,
        "total_payments": total_payments or 0,
        "outstanding": outstanding,
        "colspan_before_total": 6,
        "total_columns": 10,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/contractor_job_report.html",
            context,
            "contractor_job_report.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/contractor_job_report.html", context)


@login_required
def job_estimate_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    entries = estimate.entries.all()

    labor_total = (
        entries.filter(material_cost__isnull=True).aggregate(total=Sum("billable_amount"))[
            "total"
        ]
        or Decimal("0")
    )
    material_entries = entries.filter(material_cost__isnull=False)
    material_total = (
        material_entries.aggregate(total=Sum("billable_amount"))["total"]
        or Decimal("0")
    )
    service_total = (
        material_entries.filter(service_markup__gt=0).aggregate(
            total=Sum("billable_amount")
        )["total"]
        or Decimal("0")
    )
    billable_total = labor_total + material_total + service_total
    cost_total = (
        entries.aggregate(total=Sum("cost_amount"))["total"] or Decimal("0")
    )
    profit = billable_total - cost_total
    margin = (profit / billable_total * 100) if billable_total else Decimal("0")

    export_pdf = request.GET.get("export") == "pdf"

    context = {
        "contractor": contractor,
        "estimate": estimate,
        "labor_total": labor_total,
        "material_total": material_total,
        "service_total": service_total,
        "grand_total": billable_total,
        "cost_total": cost_total,
        "profit": profit,
        "margin": margin,
        "report": export_pdf,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/job_estimate_report.html",
            context,
            "job_estimate_report.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/job_estimate_report.html", context)


# API endpoints for enhanced functionality
@login_required
def search_entries(request):
    """API endpoint for searching entries"""
    contractor = get_contractor(request.user)
    if contractor is None:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    query = request.GET.get("q", "")
    project_id = request.GET.get("project_id")

    entries = JobEntry.objects.filter(project__contractor=contractor)

    if project_id:
        entries = entries.filter(project_id=project_id)

    if query:
        entries = entries.filter(
            Q(description__icontains=query)
            | Q(material_description__icontains=query)
            | Q(asset__name__icontains=query)
            | Q(employee__name__icontains=query)
        )

    entries = entries.order_by("-date")

    results = []
    for entry in entries[:10]:  # Limit results
        results.append(
            {
                "id": entry.id,
                "date": entry.date.strftime("%Y-%m-%d"),
                "description": entry.description,
                "amount": str(entry.billable_amount),
                "project": entry.project.name,
            }
        )

    return JsonResponse({"results": results})


@login_required
def get_material_templates(request):
    """API endpoint for material templates"""
    contractor = get_contractor(request.user)
    if contractor is None:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # This could be expanded to store actual templates in the database
    # For now, return some common templates
    templates = [
        {
            "name": "Office Supplies Basic",
            "materials": [
                {
                    "description": "Office Supplies - Basic",
                    "quantity": 1,
                    "unit": "Each",
                    "cost": 25.00,
                },
                {
                    "description": "Printer Paper",
                    "quantity": 5,
                    "unit": "Reams",
                    "cost": 8.50,
                },
                {
                    "description": "Writing Supplies",
                    "quantity": 1,
                    "unit": "Set",
                    "cost": 15.00,
                },
            ],
        },
        {
            "name": "Basic Maintenance",
            "materials": [
                {
                    "description": "Cleaning Supplies",
                    "quantity": 1,
                    "unit": "Each",
                    "cost": 15.00,
                },
                {
                    "description": "Safety Equipment",
                    "quantity": 1,
                    "unit": "Each",
                    "cost": 45.00,
                },
                {
                    "description": "Maintenance Tools",
                    "quantity": 1,
                    "unit": "Set",
                    "cost": 35.00,
                },
            ],
        },
    ]

    return JsonResponse({"templates": templates})


# Add these views to the existing views.py file

@login_required
def create_estimate(request):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    assets = contractor.assets.all()
    employees = contractor.employees.all()

    if request.method == "POST":
        try:
            # Debug: Print all POST data
            print("=== CREATE ESTIMATE DEBUG ===")
            print("POST data keys:", list(request.POST.keys()))
            print("Form data:", dict(request.POST))
            
            # Create the estimate with proper error handling
            estimate_data = {
                'contractor': contractor,
                'name': request.POST.get("name", "Untitled Estimate"),
                'estimate_number': request.POST.get("estimate_number", ""),
                'customer_name': request.POST.get("customer_name", ""),
                'customer_email': request.POST.get("customer_email", ""),
                'customer_phone': request.POST.get("customer_phone", ""),
                'customer_address': request.POST.get("customer_address", ""),
                'project_location': request.POST.get("project_location", ""),
                'project_description': request.POST.get("project_description", ""),
                'payment_terms': request.POST.get("payment_terms", ""),
                'exclusions': request.POST.get("exclusions", ""),
                'special_terms': request.POST.get("special_terms", ""),
                'liability_statement': request.POST.get("liability_statement", ""),
                'notes': request.POST.get("notes", ""),
                'created_date': request.POST.get("created_date"),
                'valid_until': request.POST.get("valid_until") or None,
            }
            
            print("Creating estimate with data:", estimate_data)
            estimate = Estimate.objects.create(**estimate_data)
            print("Estimate created with ID:", estimate.id)

            entries_created = 0
            date = request.POST.get("created_date")
            
            if not date:
                date = timezone.now().date()

            # Process labor/equipment entries
            hours_list = request.POST.getlist("hours[]")
            asset_ids = request.POST.getlist("asset[]")
            employee_ids = request.POST.getlist("employee[]")
            descriptions = request.POST.getlist("description[]")

            print("Labor entries - Hours:", hours_list)
            print("Labor entries - Assets:", asset_ids)
            print("Labor entries - Employees:", employee_ids)
            print("Labor entries - Descriptions:", descriptions)

            # Create labor/equipment entries
            if hours_list:
                for i, (hours, asset_id, employee_id, desc) in enumerate(zip(hours_list, asset_ids, employee_ids, descriptions)):
                    try:
                        if not any([hours, asset_id, employee_id]):
                            continue

                        asset = None
                        employee = None
                        
                        if asset_id:
                            asset = assets.filter(pk=asset_id).first()
                        if employee_id:
                            employee = employees.filter(pk=employee_id).first()
                            
                        hours_dec = Decimal(hours or 0)

                        if hours_dec > 0 and (asset or employee):
                            EstimateEntry.objects.create(
                                estimate=estimate,
                                date=date,
                                hours=hours_dec,
                                asset=asset,
                                employee=employee,
                                material_description="",
                                material_cost=None,
                                description=desc or "",
                            )
                            entries_created += 1
                            print(f"Created labor entry {i+1}")
                            
                    except Exception as e:
                        print(f"Error creating labor entry {i+1}: {e}")
                        continue

            # Process materials entries
            material_descriptions = request.POST.getlist("material_description[]")
            material_quantities = request.POST.getlist("material_quantity[]")
            material_units = request.POST.getlist("material_unit[]")
            material_costs = request.POST.getlist("material_cost[]")

            print("Material entries - Descriptions:", material_descriptions)
            print("Material entries - Quantities:", material_quantities)
            print("Material entries - Units:", material_units)
            print("Material entries - Costs:", material_costs)

            if material_descriptions:
                for i, (desc, qty, unit, cost) in enumerate(zip(
                    material_descriptions, material_quantities, material_units, material_costs
                )):
                    try:
                        if not desc or not qty or not cost:
                            continue

                        qty_dec = Decimal(qty or 0)
                        cost_dec = Decimal(cost or 0)

                        if desc and qty_dec > 0 and cost_dec > 0:
                            suffix = f"({qty_dec} {unit})" if unit else ""
                            desc_stripped = desc.strip()
                            full_desc = (
                                f"{desc_stripped} {suffix}".strip()
                                if suffix and not desc_stripped.endswith(suffix)
                                else desc_stripped
                            )

                            EstimateEntry.objects.create(
                                estimate=estimate,
                                date=date,
                                hours=qty_dec,
                                asset=None,
                                employee=None,
                                material_description=full_desc,
                                material_cost=cost_dec,
                                description=f"Material: {full_desc}",
                            )
                            entries_created += 1
                            print(f"Created material entry {i+1}")
                            
                    except Exception as e:
                        print(f"Error creating material entry {i+1}: {e}")
                        continue

            # Process services entries
            service_descriptions = request.POST.getlist("service_description[]")
            service_quantities = request.POST.getlist("service_quantity[]")
            service_units = request.POST.getlist("service_unit[]")
            service_costs = request.POST.getlist("service_cost[]")
            service_markups = request.POST.getlist("service_markup[]")

            print("Service entries - Descriptions:", service_descriptions)
            print("Service entries - Quantities:", service_quantities)
            print("Service entries - Units:", service_units)
            print("Service entries - Costs:", service_costs)
            print("Service entries - Markups:", service_markups)

            if service_descriptions:
                for i, (desc, qty, unit, cost, markup) in enumerate(zip(
                    service_descriptions, service_quantities, service_units, service_costs, service_markups
                )):
                    try:
                        if not desc or not qty or not cost:
                            continue

                        qty_dec = Decimal(qty or 0)
                        cost_dec = Decimal(cost or 0)
                        markup_dec = Decimal(markup or 0)

                        if desc and qty_dec > 0 and cost_dec > 0:
                            suffix = f"({qty_dec} {unit})" if unit else ""
                            desc_stripped = desc.strip()
                            full_desc = (
                                f"{desc_stripped} {suffix}".strip()
                                if suffix and not desc_stripped.endswith(suffix)
                                else desc_stripped
                            )

                            EstimateEntry.objects.create(
                                estimate=estimate,
                                date=date,
                                hours=qty_dec,
                                asset=None,
                                employee=None,
                                material_description=full_desc,
                                material_cost=cost_dec,
                                service_markup=markup_dec,
                                description=f"Outside Service: {full_desc}",
                            )
                            entries_created += 1
                            print(f"Created service entry {i+1}")
                            
                    except Exception as e:
                        print(f"Error creating service entry {i+1}: {e}")
                        continue

            print(f"Total entries created: {entries_created}")

            if entries_created > 0:
                messages.success(
                    request, f"Estimate '{estimate.name}' created successfully with {entries_created} entries."
                )
            else:
                messages.warning(request, f"Estimate '{estimate.name}' created but no entries were added.")

            return redirect("dashboard:estimate_list")
            
        except Exception as e:
            print(f"ERROR in create_estimate: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error creating estimate: {e}")
            return redirect("dashboard:estimate_list")

    return render(
        request,
        "dashboard/create_estimate.html",
        {
            "assets": assets,
            "employees": employees,
            "margin": contractor.material_margin,
        },
    )

# File: jobtracker/dashboard/views.py
# Replace the existing edit_estimate function with this updated version

@login_required
def edit_estimate(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    assets = contractor.assets.all()
    employees = contractor.employees.all()

    if request.method == "POST":
        try:
            # Update the estimate basic information
            estimate.name = request.POST.get("name")
            estimate.estimate_number = request.POST.get("estimate_number", "")
            estimate.customer_name = request.POST.get("customer_name")
            estimate.customer_email = request.POST.get("customer_email", "")
            estimate.customer_phone = request.POST.get("customer_phone", "")
            estimate.customer_address = request.POST.get("customer_address", "")
            estimate.project_location = request.POST.get("project_location")
            estimate.project_description = request.POST.get("project_description", "")
            estimate.payment_terms = request.POST.get("payment_terms", "")
            estimate.exclusions = request.POST.get("exclusions", "")
            estimate.special_terms = request.POST.get("special_terms", "")
            estimate.liability_statement = request.POST.get("liability_statement", "")
            estimate.notes = request.POST.get("notes", "")
            estimate.created_date = request.POST.get("created_date")
            estimate.valid_until = request.POST.get("valid_until") or None
            estimate.save()

            # Process existing and new line items
            processed_entry_ids = set()
            processed_material_ids = set()
            processed_service_ids = set()

            date = request.POST.get("created_date")

            # Process labor/equipment entries
            hours_list = request.POST.getlist("hours[]")
            asset_ids = request.POST.getlist("asset[]")
            employee_ids = request.POST.getlist("employee[]")
            descriptions = request.POST.getlist("description[]")
            entry_ids = request.POST.getlist("entry_id[]")

            for i, (hours, asset_id, employee_id, desc, entry_id) in enumerate(zip(
                hours_list, asset_ids, employee_ids, descriptions, entry_ids
            )):
                # Skip empty entries
                if not any([hours, asset_id, employee_id]):
                    continue

                hours_dec = Decimal(hours or 0)
                if hours_dec <= 0 and not asset_id and not employee_id:
                    continue

                asset = assets.filter(pk=asset_id).first() if asset_id else None
                employee = employees.filter(pk=employee_id).first() if employee_id else None

                if entry_id:
                    # Update existing entry
                    try:
                        entry = EstimateEntry.objects.get(pk=entry_id, estimate=estimate)
                        entry.hours = hours_dec
                        entry.asset = asset
                        entry.employee = employee
                        entry.description = desc or ""
                        entry.material_description = ""
                        entry.material_cost = None
                        entry.save()
                        processed_entry_ids.add(int(entry_id))
                    except EstimateEntry.DoesNotExist:
                        pass
                else:
                    # Create new entry
                    EstimateEntry.objects.create(
                        estimate=estimate,
                        date=date,
                        hours=hours_dec,
                        asset=asset,
                        employee=employee,
                        material_description="",
                        material_cost=None,
                        description=desc or "",
                    )

            # Process materials entries
            material_descriptions = request.POST.getlist("material_description[]")
            material_quantities = request.POST.getlist("material_quantity[]")
            material_units = request.POST.getlist("material_unit[]")
            material_costs = request.POST.getlist("material_cost[]")
            material_entry_ids = request.POST.getlist("material_entry_id[]")

            for i, (desc, qty, unit, cost, entry_id) in enumerate(zip(
                material_descriptions, material_quantities, material_units, 
                material_costs, material_entry_ids
            )):
                if not desc or not qty or not cost:
                    continue

                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)

                if desc and qty_dec > 0 and cost_dec > 0:
                    suffix = f"({qty_dec} {unit})" if unit else ""
                    desc_stripped = desc.strip()
                    full_desc = (
                        f"{desc_stripped} {suffix}".strip()
                        if suffix and not desc_stripped.endswith(suffix)
                        else desc_stripped
                    )

                    if entry_id:
                        # Update existing entry
                        try:
                            entry = EstimateEntry.objects.get(pk=entry_id, estimate=estimate)
                            entry.hours = qty_dec
                            entry.material_description = full_desc
                            entry.material_cost = cost_dec
                            entry.description = f"Material: {full_desc}"
                            entry.asset = None
                            entry.employee = None
                            entry.save()
                            processed_material_ids.add(int(entry_id))
                        except EstimateEntry.DoesNotExist:
                            pass
                    else:
                        # Create new entry
                        EstimateEntry.objects.create(
                            estimate=estimate,
                            date=date,
                            hours=qty_dec,
                            asset=None,
                            employee=None,
                            material_description=full_desc,
                            material_cost=cost_dec,
                            description=f"Material: {full_desc}",
                        )

            # Process services entries
            service_descriptions = request.POST.getlist("service_description[]")
            service_quantities = request.POST.getlist("service_quantity[]")
            service_units = request.POST.getlist("service_unit[]")
            service_costs = request.POST.getlist("service_cost[]")
            service_markups = request.POST.getlist("service_markup[]")
            service_entry_ids = request.POST.getlist("service_entry_id[]")

            for i, (desc, qty, unit, cost, markup, entry_id) in enumerate(zip(
                service_descriptions, service_quantities, service_units,
                service_costs, service_markups, service_entry_ids
            )):
                if not desc or not qty or not cost:
                    continue

                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)
                markup_dec = Decimal(markup or 0)

                if desc and qty_dec > 0 and cost_dec > 0:
                    suffix = f"({qty_dec} {unit})" if unit else ""
                    desc_stripped = desc.strip()
                    full_desc = (
                        f"{desc_stripped} {suffix}".strip()
                        if suffix and not desc_stripped.endswith(suffix)
                        else desc_stripped
                    )

                    if entry_id:
                        # Update existing entry
                        try:
                            entry = EstimateEntry.objects.get(pk=entry_id, estimate=estimate)
                            entry.hours = qty_dec
                            entry.material_description = full_desc
                            entry.material_cost = cost_dec
                            entry.service_markup = markup_dec
                            entry.description = f"Outside Service: {full_desc}"
                            entry.asset = None
                            entry.employee = None
                            entry.save()
                            processed_service_ids.add(int(entry_id))
                        except EstimateEntry.DoesNotExist:
                            pass
                    else:
                        # Create new entry
                        EstimateEntry.objects.create(
                            estimate=estimate,
                            date=date,
                            hours=qty_dec,
                            asset=None,
                            employee=None,
                            material_description=full_desc,
                            material_cost=cost_dec,
                            service_markup=markup_dec,
                            description=f"Outside Service: {full_desc}",
                        )

            # Delete entries that were removed (not in processed lists)
            all_entry_ids = set(estimate.entries.values_list('id', flat=True))
            to_delete = all_entry_ids - processed_entry_ids - processed_material_ids - processed_service_ids
            if to_delete:
                EstimateEntry.objects.filter(id__in=to_delete).delete()

            messages.success(request, f"Estimate '{estimate.name}' updated successfully.")
            return redirect("dashboard:estimate_list")

        except Exception as e:
            messages.error(request, f"Error updating estimate: {e}")
            return redirect("dashboard:edit_estimate", pk=pk)

    # Prepare existing entries for the template
    entries = estimate.entries.all()
    
    # Separate entries by type
    labor_entries = entries.filter(
        (Q(asset__isnull=False) | Q(employee__isnull=False)),
        material_description=""
    )
    
    material_entries = entries.filter(
        material_description__isnull=False,
        material_description__gt="",
        description__startswith="Material:"
    )
    
    service_entries = entries.filter(
        material_description__isnull=False,
        material_description__gt="",
        description__startswith="Outside Service:"
    )

    return render(
        request,
        "dashboard/edit_estimate.html",
        {
            "estimate": estimate,
            "assets": assets,
            "employees": employees,
            "margin": contractor.material_margin,
            "labor_entries": labor_entries,
            "material_entries": material_entries,
            "service_entries": service_entries,
        },
    )

@login_required
def duplicate_estimate(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    original = get_object_or_404(Estimate, pk=pk, contractor=contractor)

    if request.method == "POST":
        # Create duplicate estimate
        duplicate = Estimate.objects.create(
            contractor=contractor,
            name=f"{original.name} (Copy)",
            customer_name=original.customer_name,
            customer_email=original.customer_email,
            customer_phone=original.customer_phone,
            customer_address=original.customer_address,
            project_location=original.project_location,
            project_description=original.project_description,
            payment_terms=original.payment_terms,
            exclusions=original.exclusions,
            special_terms=original.special_terms,
            liability_statement=original.liability_statement,
            notes=original.notes,
            created_date=timezone.now().date(),
            valid_until=None,
        )

        # Duplicate all entries
        for entry in original.entries.all():
            EstimateEntry.objects.create(
                estimate=duplicate,
                date=duplicate.created_date,
                hours=entry.hours,
                asset=entry.asset,
                employee=entry.employee,
                material_description=entry.material_description,
                material_cost=entry.material_cost,
                service_markup=entry.service_markup,
                description=entry.description,
            )

        messages.success(request, f"Estimate duplicated as '{duplicate.name}'.")
        return redirect("dashboard:edit_estimate", pk=duplicate.pk)

    return redirect("dashboard:estimate_list")


@login_required
def email_estimate(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    
    # TODO: Implement email functionality
    messages.info(request, "Email functionality will be implemented in a future update.")
    return redirect("dashboard:estimate_list")


@login_required
def customer_estimate_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    
    # Group entries for customer presentation
    labor_equipment_entries = estimate.entries.filter(
        Q(asset__isnull=False) | Q(employee__isnull=False)
    ).exclude(material_description__isnull=False, material_description__gt='')
    
    material_entries = estimate.entries.filter(
        material_description__isnull=False,
        material_description__gt='',
        description__startswith='Material:'
    )
    
    service_entries = estimate.entries.filter(
        material_description__isnull=False,
        material_description__gt='',
        description__startswith='Outside Service:'
    )
    
    # Calculate totals
    labor_equipment_total = sum((entry.billable_amount or 0) for entry in labor_equipment_entries)
    materials_total = sum((entry.billable_amount or 0) for entry in material_entries)
    services_total = sum((entry.billable_amount or 0) for entry in service_entries)
    grand_total = labor_equipment_total + materials_total + services_total

    export_pdf = request.GET.get("export") == "pdf"

    contractor_logo = None
    if contractor.logo:
        contractor_logo = (
            f"file://{contractor.logo.path}" if export_pdf else contractor.logo.url
        )

    context = {
        "contractor": contractor,
        "contractor_logo": contractor_logo,
        "estimate": estimate,
        "labor_equipment_entries": labor_equipment_entries,
        "material_entries": material_entries,
        "service_entries": service_entries,
        "labor_equipment_total": labor_equipment_total,
        "materials_total": materials_total,
        "services_total": services_total,
        "grand_total": grand_total,
        "report": export_pdf,
        "document_title": "Customer Estimate",
        "document_type_label": "ESTIMATE",
        "document_number": estimate.estimate_number,
        "document_date": estimate.created_date,
        "document_valid_until": estimate.valid_until,
        "show_acceptance": True,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/customer_estimate_report.html",
            context,
            f"estimate_{estimate.estimate_number}.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/customer_estimate_report.html", context)


@login_required
def customer_invoice_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    project = get_object_or_404(Project, pk=pk, contractor=contractor)

    labor_equipment_entries = project.job_entries.filter(
        Q(asset__isnull=False) | Q(employee__isnull=False)
    ).exclude(material_description__isnull=False, material_description__gt="")

    material_entries = project.job_entries.filter(
        material_description__isnull=False,
        material_description__gt="",
        description__startswith="Material:",
    )

    service_entries = project.job_entries.filter(
        material_description__isnull=False,
        material_description__gt="",
        description__startswith="Outside Service:",
    )

    labor_equipment_total = sum((entry.billable_amount or 0) for entry in labor_equipment_entries)
    materials_total = sum((entry.billable_amount or 0) for entry in material_entries)
    services_total = sum((entry.billable_amount or 0) for entry in service_entries)
    grand_total = labor_equipment_total + materials_total + services_total

    export_pdf = request.GET.get("export") == "pdf"

    contractor_logo = None
    if contractor.logo:
        contractor_logo = (
            f"file://{contractor.logo.path}" if export_pdf else contractor.logo.url
        )

    invoice_number = f"INV-{project.pk:04d}"
    estimate = project.estimate or SimpleNamespace(
        customer_name=project.name,
        customer_email="",
        customer_phone="",
        customer_address="",
        project_location="",
        created_date=project.start_date,
        valid_until=None,
        project_description="",
        payment_terms="",
        exclusions="",
        special_terms="",
        liability_statement="",
    )

    context = {
        "contractor": contractor,
        "contractor_logo": contractor_logo,
        "estimate": estimate,
        "labor_equipment_entries": labor_equipment_entries,
        "material_entries": material_entries,
        "service_entries": service_entries,
        "labor_equipment_total": labor_equipment_total,
        "materials_total": materials_total,
        "services_total": services_total,
        "grand_total": grand_total,
        "report": export_pdf,
        "document_title": "Invoice",
        "document_type_label": "INVOICE",
        "document_number": invoice_number,
        "document_date": timezone.now().date(),
        "document_valid_until": None,
        "show_acceptance": False,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/customer_estimate_report.html",
            context,
            f"invoice_{invoice_number}.pdf",
            request=request,
        )
        if pdf:
            return pdf

    return render(request, "dashboard/customer_estimate_report.html", context)


@login_required
def internal_estimate_report(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
    entries = list(estimate.entries.all().order_by("-date"))
    
    # Calculate detailed totals and margins
    total_billable = estimate.total_billable
    total_cost = estimate.total_cost
    total_profit = estimate.total_profit
    overall_margin = estimate.profit_margin

    # Category breakdowns
    labor_cost = equipment_cost = material_cost = service_cost = Decimal("0")
    labor_billable = equipment_billable = material_billable = service_billable = Decimal("0")

    for entry in entries:
        if entry.asset and not entry.material_description:
            equipment_cost += (entry.asset.cost_rate * entry.hours) if entry.asset else Decimal("0")
            equipment_billable += (entry.asset.billable_rate * entry.hours) if entry.asset else Decimal("0")
        
        if entry.employee and not entry.material_description:
            labor_cost += (entry.employee.cost_rate * entry.hours) if entry.employee else Decimal("0")
            labor_billable += (entry.employee.billable_rate * entry.hours) if entry.employee else Decimal("0")
        
        if entry.material_description:
            mat_cost = (entry.material_cost * entry.hours) if entry.material_cost else Decimal("0")
            if "Outside Service:" in entry.description:
                service_cost += mat_cost
                service_billable += entry.billable_amount or Decimal("0")
            else:
                material_cost += mat_cost
                material_billable += entry.billable_amount or Decimal("0")

    export_pdf = request.GET.get("export") == "pdf"

    contractor_logo = None
    if contractor.logo:
        contractor_logo = (
            f"file://{contractor.logo.path}" if export_pdf else contractor.logo.url
        )

    context = {
        "contractor": contractor,
        "contractor_logo": contractor_logo,
        "estimate": estimate,
        "entries": entries,
        "total_billable": total_billable,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "overall_margin": overall_margin,
        "labor_cost": labor_cost,
        "labor_billable": labor_billable,
        "equipment_cost": equipment_cost,
        "equipment_billable": equipment_billable,
        "material_cost": material_cost,
        "material_billable": material_billable,
        "service_cost": service_cost,
        "service_billable": service_billable,
        "report": export_pdf,
    }

    if export_pdf:
        pdf = _render_pdf(
            "dashboard/internal_estimate_report.html", context, f"internal_estimate_{estimate.estimate_number}.pdf"
        )
        if pdf:
            return pdf

    return render(request, "dashboard/internal_estimate_report.html", context)


@login_required
def project_analytics_data(request, pk):
    """API endpoint for project analytics data"""
    contractor = get_contractor(request.user)
    if contractor is None:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    project = get_object_or_404(Project, pk=pk, contractor=contractor)

    # Weekly breakdown
    weekly_data = []
    current_date = timezone.now().date()
    start_date = project.start_date

    while start_date <= current_date:
        end_date = start_date + timedelta(days=6)

        week_entries = project.job_entries.filter(
            date__range=[start_date, end_date], material_description=""
        )
        week_hours = week_entries.aggregate(hours=Sum("hours"))["hours"] or 0
        week_billable = (
            week_entries.aggregate(total=Sum("billable_amount"))["total"] or 0
        )
        week_cost = week_entries.aggregate(total=Sum("cost_amount"))["total"] or 0

        weekly_data.append(
            {
                "week": f"{start_date.strftime('%b %d')}",
                "hours": float(week_hours),
                "billable": float(week_billable),
                "cost": float(week_cost),
            }
        )

        start_date += timedelta(weeks=1)

    # Category breakdown
    labor_total = (
        project.job_entries.filter(employee__isnull=False).aggregate(
            total=Sum("billable_amount")
        )["total"]
        or 0
    )
    equipment_total = (
        project.job_entries.filter(asset__isnull=False).aggregate(
            total=Sum("billable_amount")
        )["total"]
        or 0
    )
    materials_total = (
        project.job_entries.exclude(material_description="").aggregate(
            total=Sum("billable_amount")
        )["total"]
        or 0
    )

    return JsonResponse(
        {
            "weekly_data": weekly_data,
            "category_breakdown": {
                "labor": float(labor_total),
                "equipment": float(equipment_total),
                "materials": float(materials_total),
            },
            "totals": {
                "billable": float(
                    project.job_entries.aggregate(total=Sum("billable_amount"))["total"]
                    or 0
                ),
                "cost": float(
                    project.job_entries.aggregate(total=Sum("cost_amount"))["total"]
                    or 0
                ),
            },
        }
    )


@login_required
def add_estimate_entry(request, pk):
    contractor = get_contractor(request.user)
    if contractor is None:
        return redirect("login")

    estimate = get_object_or_404(Estimate, pk=pk, contractor=contractor)
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

        labor_entries = zip(hours_list, asset_ids, employee_ids, descriptions)
        for hours, asset_id, employee_id, desc in labor_entries:
            if not any([hours, asset_id, employee_id, desc]):
                continue

            asset = assets.filter(pk=asset_id).first() if asset_id else None
            employee = employees.filter(pk=employee_id).first() if employee_id else None
            hours_dec = Decimal(hours or 0)

            if hours_dec > 0 or asset or employee:
                EstimateEntry.objects.create(
                    estimate=estimate,
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
            materials = zip(
                material_descriptions,
                material_quantities,
                material_units,
                material_costs,
            )
            for desc, qty, unit, cost in materials:
                if not any([desc, qty, cost]):
                    continue

                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)

                if desc and qty_dec > 0 and cost_dec > 0:
                    suffix = f"({qty_dec} {unit})" if unit else ""
                    desc_stripped = desc.strip()
                    full_desc = (
                        f"{desc_stripped} {suffix}".strip()
                        if suffix and not desc_stripped.endswith(suffix)
                        else desc_stripped
                    )

                    EstimateEntry.objects.create(
                        estimate=estimate,
                        date=date,
                        hours=qty_dec,
                        asset=None,
                        employee=None,
                        material_description=full_desc,
                        material_cost=cost_dec,
                        description=f"Material: {full_desc}",
                    )
                    entries_created += 1

        # Process services entries
        service_descriptions = request.POST.getlist("service_description[]")
        service_quantities = request.POST.getlist("service_quantity[]")
        service_units = request.POST.getlist("service_unit[]")
        service_costs = request.POST.getlist("service_cost[]")
        service_markups = request.POST.getlist("service_markup[]")

        if service_descriptions:
            services = zip(
                service_descriptions,
                service_quantities,
                service_units,
                service_costs,
                service_markups,
            )
            for desc, qty, unit, cost, markup in services:
                if not any([desc, qty, cost]):
                    continue

                qty_dec = Decimal(qty or 0)
                cost_dec = Decimal(cost or 0)
                markup_dec = Decimal(markup or 0)

                if desc and qty_dec > 0 and cost_dec > 0:
                    suffix = f"({qty_dec} {unit})" if unit else ""
                    desc_stripped = desc.strip()
                    full_desc = (
                        f"{desc_stripped} {suffix}".strip()
                        if suffix and not desc_stripped.endswith(suffix)
                        else desc_stripped
                    )

                    EstimateEntry.objects.create(
                        estimate=estimate,
                        date=date,
                        hours=qty_dec,
                        asset=None,
                        employee=None,
                        material_description=full_desc,
                        material_cost=cost_dec,
                        service_markup=markup_dec,
                        description=f"Outside Service: {full_desc}",
                    )
                    entries_created += 1

        if entries_created > 0:
            messages.success(
                request, f"Successfully created {entries_created} estimate entries."
            )
        else:
            messages.warning(
                request,
                "No entries were created. Please fill in at least one complete entry.",
            )

        return redirect("dashboard:estimate_list")

    return render(
        request,
        "dashboard/estimate_form.html",
        {
            "estimate": estimate,
            "assets": assets,
            "employees": employees,
            "margin": contractor.material_margin,
        },
    )
