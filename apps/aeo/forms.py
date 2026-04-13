from django import forms


class AEOAuditRequestForm(forms.Form):
    target_keyword = forms.CharField(
        max_length=160,
        required=False,
        label="Exact Target Keyword",
        widget=forms.TextInput(attrs={"placeholder": "e.g. best used car dealership in Nairobi"}),
        help_text="Optional: Ground the analysis to a specific search query. If left blank, we will default to your primary service.",
    )
