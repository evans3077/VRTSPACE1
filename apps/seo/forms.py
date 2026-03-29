from django import forms

from .models import SEOProjectProfile


BUSINESS_TYPE_CHOICES = (
    ("automotive", "Automotive"),
    ("agency", "Agency / Professional Services"),
    ("saas", "SaaS"),
    ("hotel", "Hotel / Hospitality"),
    ("ecommerce", "Ecommerce"),
    ("healthcare", "Healthcare"),
    ("real_estate", "Real Estate"),
    ("local_service", "Local Service Business"),
)


class SEOProjectProfileForm(forms.ModelForm):
    business_type = forms.ChoiceField(choices=BUSINESS_TYPE_CHOICES)
    competitor_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "https://competitor-one.com\nhttps://competitor-two.com",
            }
        ),
        help_text="Optional manual competitors, one URL per line. The system will also auto-discover competitors from SERPs when search discovery is configured.",
    )

    class Meta:
        model = SEOProjectProfile
        fields = (
            "business_type",
            "location",
            "target_goal",
            "primary_service",
            "target_audience",
        )
        widgets = {
            "location": forms.TextInput(attrs={"placeholder": "Nairobi, Kenya"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "Increase qualified leads from organic search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "Used car sales"}),
            "target_audience": forms.TextInput(attrs={"placeholder": "Price-sensitive car buyers in Nairobi"}),
        }
