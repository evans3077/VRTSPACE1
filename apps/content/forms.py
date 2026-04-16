from django import forms

from .models import GeneratedContent


class GeneratedContentRequestForm(forms.Form):
    output_type = forms.ChoiceField(
        choices=GeneratedContent.OutputType.choices,
        label="Content Format",
        help_text="Choose the structure for your output (e.g. Service Page, FAQ Block)."
    )
    business_type = forms.CharField(
        max_length=160,
        label="Brand or Business Type",
        help_text="e.g. Boutique Hotel, Real Estate Agency."
    )
    location = forms.CharField(
        max_length=160,
        required=False,
        label="Target Location",
        help_text="Optional: City or region to localize the content."
    )
    target_audience = forms.CharField(
        max_length=255,
        label="Target Audience",
        help_text="Who are you writing for? (e.g. First-time homebuyers)."
    )
    page_goal = forms.CharField(
        max_length=255,
        label="Goal of this Page",
        help_text="What should the user do? (e.g. Book a viewing, sign up for newsletter)."
    )
    offer_summary = forms.CharField(
        max_length=255,
        label="Primary Offer",
        help_text="Summarize the value proposition or product."
    )
    target_keywords = forms.CharField(
        label="Target Keywords",
        help_text="Comma-separated keywords to include in the draft.",
    )
    search_intent = forms.CharField(
        max_length=120,
        required=False,
        initial="commercial",
        label="Search Intent",
        help_text="The buyer journey stage (e.g. informational, commercial)."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_target_keywords(self):
        raw_value = self.cleaned_data["target_keywords"]
        keywords = [item.strip() for item in raw_value.split(",") if item.strip()]
        if not keywords:
            raise forms.ValidationError("Add at least one target keyword.")
        return keywords


class GeneratedContentEditForm(forms.ModelForm):
    class Meta:
        model = GeneratedContent
        fields = (
            "title",
            "meta_title",
            "meta_description",
            "body",
            "cta",
            "status",
        )
        widgets = {
            "meta_description": forms.Textarea(attrs={"rows": 3}),
            "body": forms.Textarea(attrs={"rows": 18}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
