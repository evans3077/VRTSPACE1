from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model

from .models import AuditRequest, ClientProject, Lead
from .intake_options import BUSINESS_TYPE_CHOICES, LOCATION_MODE_CHOICES, LOCATION_SCOPE_CHOICES
from .location_services import get_country_choices, get_country_ui_metadata, validate_location_selection


class StructuredLocationMixin:
    location = forms.CharField(required=False, widget=forms.HiddenInput())
    location_display = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_location(self):
        return self.cleaned_data.get("location", "").strip()

    def clean(self):
        cleaned_data = super().clean()

        # `location_display` is the value the client-side location autocomplete
        # submits. It is NOT a declared ModelForm field (it lives on this plain
        # mixin, which Django's form metaclass does not collect), so it never
        # reaches cleaned_data — read it straight from the raw submission and
        # fall back to the bound `location` field. Without this the location
        # was always forced to "Worldwide", silently discarding user input.
        val = (self.data.get("location_display") or cleaned_data.get("location") or "").strip()
        if not val or val.lower() == "worldwide":
            cleaned_data["location"] = "Worldwide"
        else:
            cleaned_data["location"] = val

        # Keep legacy structured fields empty for backwards database compatibility
        cleaned_data["location_mode"] = "targeted"
        cleaned_data["location_country"] = ""
        cleaned_data["location_scope"] = ""
        cleaned_data["location_area"] = ""
        return cleaned_data


class BusinessContextMixin:
    business_type = forms.ChoiceField(choices=BUSINESS_TYPE_CHOICES, required=False)
    business_subtype = forms.CharField(required=False)
    target_audience = forms.CharField(required=False)

    def clean_business_subtype(self):
        return self.cleaned_data.get("business_subtype", "").strip()

    def clean_target_audience(self):
        return self.cleaned_data.get("target_audience", "").strip()


class LeadCaptureForm(forms.ModelForm):
    website = forms.CharField(required=False)
    consent_to_contact = forms.BooleanField(required=False)

    class Meta:
        model = Lead
        fields = [
            "name",
            "email",
            "interest_area",
            "message",
            "consent_to_contact",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Full name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Business email"}),
            "interest_area": forms.Select(),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Briefly describe what you're looking for..."}),
        }

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website


class AuditRequestForm(BusinessContextMixin, StructuredLocationMixin, forms.ModelForm):
    website = forms.CharField()
    monthly_leads_goal = forms.IntegerField(required=False, initial=20, widget=forms.HiddenInput())
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
            "business_subtype",
            "target_audience",
            "location_mode",
            "location_country",
            "location_scope",
            "location_area",
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
            "business_subtype": forms.TextInput(attrs={"placeholder": "Used car dealership, wedding venue, dermatology clinic"}),
            "target_audience": forms.TextInput(attrs={"placeholder": "The people or buyers you most want this site to reach"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "Increase qualified leads from search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "Used car sales"}),
            "market_context": forms.Textarea(attrs={"rows": 3, "placeholder": "Market, audience, location, or commercial context that should shape the audit."}),
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "What should this audit focus on first? Share the offer, audience, or visibility issue you care about most."}),
            # Legacy location fields — overwritten by StructuredLocationMixin.clean(), never shown to user
            "location_mode": forms.HiddenInput(),
            "location_country": forms.HiddenInput(),
            "location_scope": forms.HiddenInput(),
            "location_area": forms.HiddenInput(),
            "location": forms.HiddenInput(),
        }

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website

    def clean_target_goal(self):
        return self.cleaned_data.get("target_goal", "").strip()

    def clean_primary_service(self):
        return self.cleaned_data.get("primary_service", "").strip()

    def clean_monthly_leads_goal(self):
        value = self.cleaned_data.get("monthly_leads_goal")
        return value or 20

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


class WorkspaceProjectForm(BusinessContextMixin, StructuredLocationMixin, forms.ModelForm):
    website = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "example.com"}))

    class Meta:
        model = ClientProject
        fields = [
            "name",
            "website",
            "business_type",
            "business_subtype",
            "target_audience",
            "location_mode",
            "location_country",
            "location_scope",
            "location_area",
            "location",
            "target_goal",
            "primary_service",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Project name or brand"}),
            "business_type": forms.Select(choices=BUSINESS_TYPE_CHOICES),
            "business_subtype": forms.TextInput(attrs={"placeholder": "Used car dealership, wedding venue, dermatology clinic"}),
            "target_audience": forms.TextInput(attrs={"placeholder": "The buyers or users you want this project to reach"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "Increase qualified leads from search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "Used car sales"}),
            # Legacy location fields — overwritten by StructuredLocationMixin.clean(), never shown to user
            "location_mode": forms.HiddenInput(),
            "location_country": forms.HiddenInput(),
            "location_scope": forms.HiddenInput(),
            "location_area": forms.HiddenInput(),
            "location": forms.HiddenInput(),
        }

    def clean_name(self):
        return self.cleaned_data.get("name", "").strip()

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website

    def clean_target_goal(self):
        return self.cleaned_data.get("target_goal", "").strip()

    def clean_primary_service(self):
        return self.cleaned_data.get("primary_service", "").strip()


class WorkspaceAuditStartForm(BusinessContextMixin, StructuredLocationMixin, forms.ModelForm):
    email = forms.EmailField(widget=forms.HiddenInput())

    class Meta:
        model = AuditRequest
        fields = [
            "company_name",
            "email",
            "website",
            "business_type",
            "business_subtype",
            "target_audience",
            "location_mode",
            "location_country",
            "location_scope",
            "location_area",
            "location",
            "target_goal",
            "primary_service",
            "notes",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Company or brand"}),
            "website": forms.TextInput(attrs={"placeholder": "example.com"}),
            "business_subtype": forms.TextInput(attrs={"placeholder": "Used car dealership, wedding venue, dermatology clinic"}),
            "target_audience": forms.TextInput(attrs={"placeholder": "The buyers or users you want this project to reach"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "Increase qualified leads from search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "Used car sales"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "What should this first audit focus on?"}),
            # Legacy location fields — overwritten by StructuredLocationMixin.clean(), never shown to user
            "location_mode": forms.HiddenInput(),
            "location_country": forms.HiddenInput(),
            "location_scope": forms.HiddenInput(),
            "location_area": forms.HiddenInput(),
            "location": forms.HiddenInput(),
        }

    def clean_company_name(self):
        return self.cleaned_data.get("company_name", "").strip()

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()

    def clean_website(self):
        website = self.cleaned_data["website"].strip()
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        return website

    def clean_target_goal(self):
        return self.cleaned_data.get("target_goal", "").strip()

    def clean_primary_service(self):
        return self.cleaned_data.get("primary_service", "").strip()

    def clean_notes(self):
        return self.cleaned_data.get("notes", "").strip()


class AccountProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@company.com"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        user_model = get_user_model()
        queryset = user_model.objects.filter(email__iexact=email)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save(update_fields=["first_name", "last_name", "email", "username"])
        return user


class AccountPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update({"placeholder": "Current password"})
        self.fields["new_password1"].widget.attrs.update({"placeholder": "New password"})
        self.fields["new_password2"].widget.attrs.update({"placeholder": "Confirm new password"})
