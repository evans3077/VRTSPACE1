from django import forms

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
