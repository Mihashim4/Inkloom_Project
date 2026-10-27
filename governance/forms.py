import re

from django import forms

from .models import BrandRule, ContentSubmission


class ContentSubmissionForm(forms.ModelForm):
    class Meta:
        model = ContentSubmission
        fields = (
            "title",
            "creator_name",
            "content_format",
            "original_text",
            "hex_color_used",
            "alt_text_provided",
        )

    def clean_hex_color_used(self):
        value = self.cleaned_data["hex_color_used"].strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise forms.ValidationError("Enter a six-digit HEX color, such as #2563EB.")
        return value.upper()


class BrandRuleForm(forms.ModelForm):
    class Meta:
        model = BrandRule
        fields = (
            "rule_code",
            "title",
            "category",
            "severity",
            "forbidden_pattern",
            "approved_replacement",
            "guideline_clause",
            "rationale",
        )
