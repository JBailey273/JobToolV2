from decimal import Decimal
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Sum, Count, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from tempfile import NamedTemporaryFile
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
    
    projects = contractor.projects.filter(end_date__isnull=True)
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
