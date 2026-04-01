from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

from .models import AuditRequest, Lead


BUSINESS_TYPE_CHOICES = (
    ("", "Select business type"),
    ("automotive", "Automotive"),
    ("agency", "Agency / Professional Services"),
    ("saas", "SaaS"),
    ("hotel", "Hotel / Hospitality"),
    ("ecommerce", "Ecommerce"),
    ("healthcare", "Healthcare"),
    ("real_estate", "Real Estate"),
    ("local_service", "Local Service Business"),
    ("education", "Education"),
    ("finance", "Finance / Fintech"),
    ("other", "Other"),
)


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
    business_type = forms.ChoiceField(choices=BUSINESS_TYPE_CHOICES, required=False)
    competitor_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "https://competitor-one.com, https://competitor-two.com",
            }
        ),
    )

    class Meta:
        model = AuditRequest
        fields = [
            "company_name",
            "email",
            "website",
            "business_type",
            "location",
            "target_goal",
            "primary_service",
            "monthly_leads_goal",
            "market_context",
            "competitor_urls",
            "notes",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Company or brand"}),
            "email": forms.EmailInput(attrs={"placeholder": "team@company.com"}),
            "website": forms.TextInput(attrs={"placeholder": "example.com"}),
            "location": forms.TextInput(attrs={"placeholder": "Nairobi, Kenya"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "Increase qualified leads from search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "Used car sales"}),
            "market_context": forms.Textarea(attrs={"rows": 3, "placeholder": "Market, audience, location, or commercial context that should shape the audit."}),
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Share the market, offer, or visibility problem you want the audit to surface."}),
        }

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website

    def clean_location(self):
        return self.cleaned_data.get("location", "").strip()

    def clean_target_goal(self):
        return self.cleaned_data.get("target_goal", "").strip()

    def clean_primary_service(self):
        return self.cleaned_data.get("primary_service", "").strip()

    def clean_competitor_urls(self):
        raw_value = self.cleaned_data.get("competitor_urls", "")
        urls = []
        for part in raw_value.replace("\r", "\n").replace(",", "\n").split("\n"):
            value = part.strip()
            if not value:
                continue
            if not value.startswith(("http://", "https://")):
                value = f"https://{value}"
            urls.append(value)
        deduped = []
        for url in urls:
            if url not in deduped:
                deduped.append(url)
        return deduped[:3]


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
