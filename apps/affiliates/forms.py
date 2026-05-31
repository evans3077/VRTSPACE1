from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import AffiliateApplication


class AffiliateApplicationForm(forms.ModelForm):
    class Meta:
        model = AffiliateApplication
        fields = (
            "name",
            "email",
            "website_or_handle",
            "audience_size",
            "promotion_plan",
        )
        widgets = {
            "promotion_plan": forms.Textarea(attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": (
                    "Newsletter, YouTube channel, Twitter audience, agency network… "
                    "tell us briefly how you'd promote VRTSPACE."
                ),
            }),
            "website_or_handle": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "https://yoursite.com or @yourhandle",
            }),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your name or brand"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@domain.com"}),
            "audience_size": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        return email

    def clean_website_or_handle(self):
        value = (self.cleaned_data.get("website_or_handle") or "").strip()
        if not value:
            raise forms.ValidationError("Tell us where your audience lives.")
        return value


class AffiliateLoginForm(AuthenticationForm):
    """Standalone login form for the affiliate portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "placeholder": "your@email.com",
            "autofocus": True,
        })
        self.fields["password"].widget.attrs.update({
            "placeholder": "Password",
        })


class AffiliateSettingsForm(forms.Form):
    display_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Your name or brand"}),
    )
    contact_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@domain.com"}),
    )
    new_password = forms.CharField(
        required=False,
        min_length=8,
        widget=forms.PasswordInput(attrs={"placeholder": "Leave blank to keep current password"}),
        help_text="Minimum 8 characters.",
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat new password"}),
    )

    def __init__(self, *args, instance=None, user=None, **kwargs):
        self._affiliate = instance
        self._user = user
        initial = kwargs.pop("initial", {})
        if instance:
            initial.setdefault("display_name", instance.display_name)
            initial.setdefault("contact_email", instance.contact_email)
        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("new_password")
        cpw = cleaned.get("confirm_password")
        if pw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned

    def save(self):
        affiliate = self._affiliate
        user = self._user
        affiliate.display_name = self.cleaned_data["display_name"]
        affiliate.contact_email = self.cleaned_data["contact_email"]
        affiliate.save(update_fields=["display_name", "contact_email", "updated_at"])
        user.email = self.cleaned_data["contact_email"]
        user.username = self.cleaned_data["contact_email"]
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        user.save()

