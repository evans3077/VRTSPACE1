from django import forms

from .models import GeneratedContent


class GeneratedContentRequestForm(forms.Form):
    output_type = forms.ChoiceField(choices=GeneratedContent.OutputType.choices)
    business_type = forms.CharField(max_length=160)
    location = forms.CharField(max_length=160, required=False)
    target_audience = forms.CharField(max_length=255)
    page_goal = forms.CharField(max_length=255)
    offer_summary = forms.CharField(max_length=255)
    target_keywords = forms.CharField(
        help_text="Comma-separated keywords or phrases to use in the draft.",
    )
    search_intent = forms.CharField(max_length=120, required=False, initial="commercial")

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
