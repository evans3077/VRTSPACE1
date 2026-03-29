from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

from .models import AuditRequest, Lead


class LeadCaptureForm(forms.ModelForm):
    website = forms.CharField(required=False)
    consent_to_contact = forms.BooleanField(required=False)

    class Meta:
        model = Lead
        fields = [
            "name",
            "email",
            "company",
            "website",
            "interest_area",
            "message",
            "consent_to_contact",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Jane Mwangi"}),
            "email": forms.EmailInput(attrs={"placeholder": "jane@company.com"}),
            "company": forms.TextInput(attrs={"placeholder": "Company or brand"}),
            "website": forms.TextInput(attrs={"placeholder": "example.com"}),
            "interest_area": forms.Select(),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us what needs to change and what success should look like."}),
        }

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website


class AuditRequestForm(forms.ModelForm):
    website = forms.CharField()

    class Meta:
        model = AuditRequest
        fields = ["company_name", "email", "website", "monthly_leads_goal", "notes"]
        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Company or brand"}),
            "email": forms.EmailInput(attrs={"placeholder": "team@company.com"}),
            "website": forms.TextInput(attrs={"placeholder": "example.com"}),
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Share the market, offer, or visibility problem you want the audit to surface."}),
        }

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website


class WorkspaceSignupForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@company.com"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Create a password"}))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        user_model = get_user_model()
        if user_model.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists. Sign in instead.")
        return email


class WorkspaceLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"placeholder": "you@company.com", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
        strip=False,
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
