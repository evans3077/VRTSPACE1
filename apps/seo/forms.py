from django import forms

from apps.leads.intake_options import BUSINESS_TYPE_CHOICES

from .models import SEOProjectProfile


class SEOProjectProfileForm(forms.ModelForm):
    business_type = forms.ChoiceField(
        choices=(("", "Auto-detect from website"),) + BUSINESS_TYPE_CHOICES[1:], 
        required=False,
        label="Business Type",
        help_text="The core vertical (e.g. Ecommerce, SaaS, Local Service)."
    )
    competitor_urls = forms.CharField(
        required=False,
        label="Competitor URLs",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "https://competitor-one.com\nhttps://competitor-two.com",
            }
        ),
        help_text="Optional: Add up to 3 competitors (one URL per line). The system will also auto-discover SERP competitors for you.",
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
        labels = {
            "location": "Target Location",
            "target_goal": "Business Goal",
            "primary_service": "Primary Service or Product",
            "target_audience": "Target Audience",
        }
        help_texts = {
            "location": "Optional: City, physical region, or 'Worldwide'.",
            "target_goal": "What is the desired conversion action? (e.g. Sales, Leads, Booking).",
            "primary_service": "The baseline core offer.",
            "target_audience": "Who exactly are you trying to reach?",
        }
        widgets = {
            "location": forms.TextInput(attrs={"placeholder": "e.g. Nairobi, Kenya"}),
            "target_goal": forms.TextInput(attrs={"placeholder": "e.g. Increase qualified leads from organic search"}),
            "primary_service": forms.TextInput(attrs={"placeholder": "e.g. Used car sales"}),
            "target_audience": forms.TextInput(attrs={"placeholder": "e.g. Price-sensitive car buyers in Nairobi"}),
        }
