from django import forms
from .models import Contractor, ContractorUser


class ContractorForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Set the contractor's login password.",
    )

    class Meta:
        model = Contractor
        fields = ["name", "email", "phone", "logo", "material_markup"]

    def save(self, commit=True):
        password = self.cleaned_data.pop("password", None)
        contractor = super().save(commit)
        if password:
            user, _ = ContractorUser.objects.get_or_create(
                contractor=contractor, defaults={"email": contractor.email}
            )
            user.email = contractor.email
            user.set_password(password)
            user.save()
        return contractor
