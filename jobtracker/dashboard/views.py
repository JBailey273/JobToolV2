from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404

from tracker.models import Project


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
