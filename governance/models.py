from django.db import models

# Create your models here.
import hashlib
from django.db import models
from django.utils import timezone


# ==========================================
# NAVEEN M: Brand Knowledge Base & Rules Schema
# ==========================================
class BrandRule(models.Model):
    CATEGORY_CHOICES = [
        ('TONE', 'Tone & Voice'),
        ('TERM', 'Terminology & Glossary'),
        ('FACT', 'Approved Facts & Claims'),
        ('VISUAL', 'Visual & Logo Guidelines'),
        ('A11Y', 'Accessibility (WCAG 2.1 AA)'),
        ('POLICY', 'Legal & Confidentiality Policy'),
    ]
    SEVERITY_CHOICES = [
        ('HIGH', 'High Risk (Blocker)'),
        ('MEDIUM', 'Medium Warning'),
        ('LOW', 'Low Suggestion'),
    ]

    rule_code = models.CharField(max_length=20, unique=True, help_text="e.g., TERM-01, FACT-04")
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='MEDIUM')
    forbidden_pattern = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated forbidden phrases or claims to trigger this rule"
    )
    approved_replacement = models.CharField(
        max_length=255, blank=True,
        help_text="Suggested compliant replacement text"
    )
    guideline_clause = models.TextField(help_text="Exact rule source citation from brand book")
    rationale = models.TextField(help_text="Why this matters for brand trust/compliance")
    trigger_count = models.PositiveIntegerField(default=0, help_text="Analytics: how often violated")

    def __str__(self):
        return f"[{self.rule_code}] {self.title}"


# ==========================================
# MOHAMMED NIYAS: Workflow State Machine & Submissions
# ==========================================
class ContentSubmission(models.Model):
    FORMAT_CHOICES = [
        ('SOCIAL', 'Social Media Post'),
        ('EMAIL', 'Marketing Email'),
        ('LANDING', 'Landing Page Copy'),
        ('DOC', 'Brochure / PDF Document'),
    ]
    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Creator Action'),
        ('ESCALATED', 'Escalated (Low AI Confidence / Legal)'),
        ('READY_FOR_MANAGER', 'Submitted for Manager Approval'),
        ('APPROVED', 'Approved & Ready to Publish'),
        ('REJECTED', 'Changes Requested by Manager'),
    ]

    title = models.CharField(max_length=200)
    creator_name = models.CharField(max_length=100, default="Alex (Content Marketer)")
    creator_role = models.CharField(max_length=100, default="Internal Marketing / Agency")
    content_format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='SOCIAL')
    original_text = models.TextField()
    working_text = models.TextField(blank=True)
    hex_color_used = models.CharField(max_length=20, default="#0052CC", help_text="Primary HEX color in visual")
    alt_text_provided = models.CharField(max_length=255, blank=True, help_text="Image accessibility alt-text")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    compliance_score = models.IntegerField(default=100)
    ai_model_disclosed = models.CharField(
        max_length=120,
        default="Inkloom Hybrid RAG Engine v1.2 (Rules + LLM Verifier)"
    )
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.working_text:
            self.working_text = self.original_text
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


# ==========================================
# IMRAN & NITHISH: Explainable Finding Cards Model
# ==========================================
class ExplainableFinding(models.Model):
    DECISION_CHOICES = [
        ('OPEN', 'Open Flag'),
        ('ACCEPTED', 'Accepted AI Suggestion'),
        ('OVERRIDDEN', 'Human Override (With Justification)'),
        ('ESCALATED', 'Escalated to Human Reviewer'),
    ]

    submission = models.ForeignKey(ContentSubmission, on_delete=models.CASCADE, related_name='findings')
    rule_code = models.CharField(max_length=30)
    category = models.CharField(max_length=30)
    severity = models.CharField(max_length=15)
    flagged_snippet = models.CharField(max_length=255)
    guideline_citation = models.TextField()
    why_it_matters = models.TextField()
    suggested_fix = models.CharField(max_length=255)
    confidence_score = models.FloatField(default=0.92)
    requires_human_escalation = models.BooleanField(default=False)
    creator_decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default='OPEN')
    human_note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.rule_code} on {self.submission.title}"


# ==========================================
# MOHAMMED NIYAS: SHA-256 Immutable Audit Trail
# ==========================================
class AuditLog(models.Model):
    submission = models.ForeignKey(ContentSubmission, on_delete=models.CASCADE, related_name='audit_logs')
    actor_name = models.CharField(max_length=100)
    actor_role = models.CharField(max_length=100)
    action = models.CharField(max_length=255)
    details = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    sha256_hash = models.CharField(max_length=64, editable=False)

    def save(self, *args, **kwargs):
        payload = f"{self.submission_id}|{self.actor_name}|{self.action}|{self.details}|{self.timestamp}"
        self.sha256_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.actor_name}: {self.action}"