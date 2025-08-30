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
        fields = ["name", "email", "phone", "logo", "material_margin"]

    def save(self, commit=True):
        contractor = super().save(commit)
        password = self.cleaned_data.get("password")
        if commit:
            self._password = None
            if password:
                user, _ = ContractorUser.objects.get_or_create(
                    contractor=contractor, defaults={"email": contractor.email}
                )
                user.email = contractor.email
                user.set_password(password)
                user.save()
        else:
            # Store the password for use after the instance is saved
            self._password = password
        return contractor
