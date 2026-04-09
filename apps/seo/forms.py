from django import forms

from apps.leads.intake_options import BUSINESS_TYPE_CHOICES

from .models import SEOProjectProfile


class SEOProjectProfileForm(forms.ModelForm):
    business_type = forms.ChoiceField(choices=(("", "Auto-detect from website"),) + BUSINESS_TYPE_CHOICES[1:], required=False)
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
