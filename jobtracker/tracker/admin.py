from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.conf import settings

from .models import (
    GlobalSettings,
    Contractor,
    ContractorUser,
    Asset,
    Employee,
    Material,
    Project,
    JobEntry,
    Payment,
)
from .forms import ContractorForm


class AssetInline(admin.TabularInline):
    model = Asset
    extra = 0


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0


@admin.register(ContractorUser)
class ContractorUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('contractor',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('contractor',)}),
    )
    list_display = ('email', 'contractor', 'is_staff', 'is_superuser')
    search_fields = ('email',)
    ordering = ('email',)


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    form = ContractorForm
    list_display = ('name', 'email', 'phone', 'material_margin')
    search_fields = ('name', 'email')
    fieldsets = (
        (None, {'fields': ('name', 'email', 'phone', 'logo', 'material_margin', 'password')}),
    )
    inlines = [AssetInline, EmployeeInline, MaterialInline, ProjectInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        password = getattr(form, "_password", None)
        if password:
            user, _ = ContractorUser.objects.get_or_create(
                contractor=obj, defaults={"email": obj.email}
            )
            user.email = obj.email
            user.set_password(password)
            user.save()


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    pass


class JobEntryInline(admin.TabularInline):
    model = JobEntry
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'contractor', 'start_date', 'end_date')
    search_fields = ('name',)
    inlines = [JobEntryInline, PaymentInline]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'contractor', 'cost_rate', 'billable_rate')
    search_fields = ('name',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'contractor', 'cost_rate', 'billable_rate')
    search_fields = ('name',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('description', 'contractor', 'actual_cost')
    search_fields = ('description',)


@admin.register(JobEntry)
class JobEntryAdmin(admin.ModelAdmin):
    list_display = ('project', 'date', 'hours', 'cost_amount', 'billable_amount')
    list_filter = ('project',)
    fields = (
        'project',
        'date',
        'hours',
        'asset',
        'employee',
        'material_description',
        'material_cost',
        'description',
        'cost_amount',
        'billable_amount',
    )
    readonly_fields = ('cost_amount', 'billable_amount')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('project', 'amount', 'date')
    list_filter = ('project',)


admin.site.site_header = settings.SITE_NAME
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = 'Administration'
