from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Contractor, ContractorUser


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
    list_display = ('email', 'material_markup')
    search_fields = ('email',)
