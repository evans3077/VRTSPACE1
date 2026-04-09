from django import forms


class AEOAuditRequestForm(forms.Form):
    target_keyword = forms.CharField(
        max_length=160,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "best used car dealership in Nairobi"}),
        help_text="Optional keyword or question to anchor the AI visibility check.",
    )
