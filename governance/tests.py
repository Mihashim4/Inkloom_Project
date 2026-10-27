from django.test import TestCase
from django.urls import reverse

from .ai_engine import run_pre_publication_governance_scan
from .models import AuditLog, BrandRule, ContentSubmission, ExplainableFinding


class GovernanceWorkflowTests(TestCase):
    def setUp(self):
        self.dashboard_url = reverse("dashboard")

    def create_submission(self, text="A straightforward draft.", **kwargs):
        defaults = {
            "title": "Test campaign",
            "creator_name": "Test creator",
            "original_text": text,
            "working_text": text,
            "hex_color_used": "#2563EB",
            "alt_text_provided": "A descriptive image of the product",
        }
        defaults.update(kwargs)
        return ContentSubmission.objects.create(**defaults)

    def test_dashboard_renders_and_seeds_valid_rule_categories(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "governance/dashboard.html")
        self.assertContains(response, "Add a Brand Rule")
        self.assertTrue(BrandRule.objects.exists())
        self.assertTrue(
            all(
                rule.category in dict(BrandRule.CATEGORY_CHOICES)
                for rule in BrandRule.objects.all()
            )
        )

    def test_submission_rejects_malformed_hex_color(self):
        response = self.client.post(
            self.dashboard_url,
            {
                "submit_content": "1",
                "title": "Test campaign",
                "creator_name": "Test creator",
                "content_format": "SOCIAL",
                "original_text": "A draft to review.",
                "hex_color_used": "not-a-color",
                "alt_text_provided": "",
            },
        )

        self.assertRedirects(response, self.dashboard_url)
        self.assertFalse(ContentSubmission.objects.exists())

    def test_accepting_finding_applies_fix_and_advances_workflow(self):
        submission = self.create_submission("The legacy price is $19/month.")
        findings = run_pre_publication_governance_scan(submission)
        finding = next(item for item in findings if item.rule_code == "TERM-02")

        response = self.client.post(
            reverse("review_detail", args=[submission.pk]),
            {"action_type": "accept_fix", "finding_id": finding.pk},
        )

        submission.refresh_from_db()
        finding.refresh_from_db()
        self.assertRedirects(response, reverse("review_detail", args=[submission.pk]))
        self.assertIn("$29/month (Pro Tier)", submission.working_text)
        self.assertEqual(finding.creator_decision, "ACCEPTED")
        self.assertEqual(submission.status, "READY_FOR_MANAGER")
        self.assertTrue(AuditLog.objects.filter(submission=submission).exists())

    def test_override_requires_justification_and_is_audited(self):
        submission = self.create_submission("The legacy price is $19/month.")
        finding = next(
            item
            for item in run_pre_publication_governance_scan(submission)
            if item.rule_code == "TERM-02"
        )
        url = reverse("review_detail", args=[submission.pk])

        self.client.post(
            url,
            {"action_type": "override_flag", "finding_id": finding.pk},
        )
        finding.refresh_from_db()
        self.assertEqual(finding.creator_decision, "OPEN")

        self.client.post(
            url,
            {
                "action_type": "override_flag",
                "finding_id": finding.pk,
                "justification": "Approved exception for this campaign.",
            },
        )
        finding.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(finding.creator_decision, "OVERRIDDEN")
        self.assertEqual(submission.status, "READY_FOR_MANAGER")
        self.assertTrue(
            AuditLog.objects.filter(action__contains="Overrode AI Flag").exists()
        )

    def test_manager_cannot_approve_with_open_findings_or_invalid_decision(self):
        submission = self.create_submission("A straightforward draft.")
        finding = ExplainableFinding.objects.create(
            submission=submission,
            rule_code="TEST-01",
            category="TONE",
            severity="HIGH",
            flagged_snippet="draft",
            guideline_citation="Test citation",
            why_it_matters="Test rationale",
            suggested_fix="copy",
        )
        url = reverse("review_detail", args=[submission.pk])

        self.client.post(
            url,
            {"action_type": "manager_decision", "manager_status": "APPROVED"},
        )
        submission.refresh_from_db()
        self.assertNotEqual(submission.status, "APPROVED")

        finding.creator_decision = "OVERRIDDEN"
        finding.human_note = "Reviewed exception."
        finding.save()
        self.client.post(
            url,
            {"action_type": "manager_decision", "manager_status": "INVALID"},
        )
        submission.refresh_from_db()
        self.assertNotEqual(submission.status, "INVALID")

        self.client.post(
            url,
            {"action_type": "manager_decision", "manager_status": "APPROVED"},
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, "APPROVED")
