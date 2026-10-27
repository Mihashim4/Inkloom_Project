import re
from .models import BrandRule, ExplainableFinding, AuditLog

APPROVED_BRAND_HEX = ["#0F172A", "#2563EB", "#10B981", "#FFFFFF"]


def seed_default_brand_knowledge_base():
    """
    Naveen M & Imran: Seeds default brand guidelines if the database is empty.
    """
    if BrandRule.objects.exists():
        return

    default_rules = [
        {
            "rule_code": "FACT-01",
            "title": "Unsupported 100% / Instant Cure or Guarantee Claims",
            "category": "FACT",
            "severity": "HIGH",
            "forbidden_pattern": "100% guaranteed,instant results,zero risk, #1 in the world",
            "approved_replacement": "clinically backed results for up to 89% of users (2026 study)",
            "guideline_clause": "Section 4.2 Legal Claims Policy: Absolute superlatives and unverified 100% guarantees are strictly prohibited.",
            "rationale": "Exposes the organisation to regulatory fines and FTC/ASCI misleading advertising penalties.",
        },
        {
            "rule_code": "TERM-02",
            "title": "Outdated Pricing & Legacy Product Naming",
            "category": "TERM",
            "severity": "HIGH",
            "forbidden_pattern": "$19/month,Rs. 499,Inkloom Basic,old logo",
            "approved_replacement": "$29/month (Pro Tier) using the 2026 Brand Kit",
            "guideline_clause": "Section 2.1 Product Glossary (Updated Q3 2026): Legacy 'Basic' tier and $19 pricing were retired.",
            "rationale": "Publishing outdated pricing creates customer billing disputes and agency inconsistency.",
        },
        {
            "rule_code": "TONE-01",
            "title": "Aggressive / Fear-Mongering Urgency Language",
            "category": "TONE",
            "severity": "MEDIUM",
            "forbidden_pattern": "buy now or regret forever,last chance ever,don't be stupid,hurry up",
            "approved_replacement": "Explore how our workflow fits your team's schedule",
            "guideline_clause": "Section 1.3 Brand Voice: Our tone is consultative, clear, and empowering—never manipulative or hostile.",
            "rationale": "Aggressive urgency damages long-term brand trust with enterprise buyers.",
        },
        {
            "rule_code": "POLICY-03",
            "title": "Confidential Internal Code Names & PII Leakage",
            "category": "POLICY",
            "severity": "HIGH",
            "forbidden_pattern": "project titan,internal-only,confidential roadmap",
            "approved_replacement": "[REDACTED — Public Release Version]",
            "guideline_clause": "Section 6.1 Data Governance: Unreleased codenames and internal metrics must never appear in public drafts.",
            "rationale": "Prevents intellectual property leakage prior to official launch.",
        },
    ]

    for item in default_rules:
        BrandRule.objects.create(**item)


def run_pre_publication_governance_scan(submission):
    """
    Mohamed Imran Hashim M: Multi-modal Pre-Publication Copilot Engine.
    Evaluates Tone, Terminology, Claims (RAG simulation), Visual HEX rules, Accessibility, and Policy.
    """
    seed_default_brand_knowledge_base()
    submission.findings.all().delete()

    text = submission.working_text
    findings_created = []
    deduction = 0

    # 1. Check against Brand Knowledge Base Rules (Text, Tone, Claims, Policy)
    for rule in BrandRule.objects.all():
        patterns = [p.strip() for p in rule.forbidden_pattern.split(',') if p.strip()]
        for pat in patterns:
            match = re.search(re.escape(pat), text, re.IGNORECASE)
            if match:
                matched_str = match.group(0)
                # Assign confidence score (simulate nuanced AI evaluation)
                confidence = 0.94 if rule.severity == "HIGH" else 0.72
                needs_escalation = confidence < 0.75

                finding = ExplainableFinding.objects.create(
                    submission=submission,
                    rule_code=rule.rule_code,
                    category=rule.category,
                    severity=rule.severity,
                    flagged_snippet=matched_str,
                    guideline_citation=rule.guideline_clause,
                    why_it_matters=rule.rationale,
                    suggested_fix=rule.approved_replacement,
                    confidence_score=confidence,
                    requires_human_escalation=needs_escalation,
                )
                findings_created.append(finding)
                rule.trigger_count += 1
                rule.save()
                deduction += 22 if rule.severity == "HIGH" else 12

    # 2. Visual Consistency Check (HEX Color Palette Validation)
    hex_val = (submission.hex_color_used or "").strip().upper()
    if hex_val and hex_val not in APPROVED_BRAND_HEX:
        finding = ExplainableFinding.objects.create(
            submission=submission,
            rule_code="VIS-01",
            category="Visual Consistency",
            severity="MEDIUM",
            flagged_snippet=f"Off-Brand Color HEX: {hex_val}",
            guideline_citation=f"Section 3.1 Visual Identity: Only approved primary palette {APPROVED_BRAND_HEX} is permitted.",
            why_it_matters="Off-brand colors break visual recognition across regional agencies and social feeds.",
            suggested_fix="#2563EB",
            confidence_score=0.98,
            requires_human_escalation=False,
        )
        findings_created.append(finding)
        deduction += 15

    # 3. Accessibility Check (WCAG 2.1 AA Alt-Text Verification)
    if not submission.alt_text_provided or len(submission.alt_text_provided.strip()) < 10:
        finding = ExplainableFinding.objects.create(
            submission=submission,
            rule_code="A11Y-01",
            category="Accessibility (WCAG 2.1)",
            severity="MEDIUM",
            flagged_snippet="Missing or Insufficient Image Alt-Text",
            guideline_citation="Section 5.1 Inclusive Design: Every visual asset requires descriptive alt-text (>=10 chars) for screen readers.",
            why_it_matters="Excludes visually impaired users and violates WCAG 2.1 AA compliance standards.",
            suggested_fix=f"Descriptive alt-text for '{submission.title}' banner showing key product message.",
            confidence_score=0.96,
            requires_human_escalation=False,
        )
        findings_created.append(finding)
        deduction += 12

    # Calculate final compliance score
    submission.compliance_score = max(10, 100 - deduction)

    # Check if any finding requires low-confidence human escalation
    if any(f.requires_human_escalation for f in findings_created):
        submission.status = 'ESCALATED'
    elif not findings_created:
        submission.status = 'READY_FOR_MANAGER'
    else:
        submission.status = 'PENDING_REVIEW'

    submission.save()

    # Log AI Review Disclosure in SHA-256 Audit Trail
    AuditLog.objects.create(
        submission=submission,
        actor_name="Inkloom AI Copilot",
        actor_role="Automated Governance Layer",
        action="Executed Pre-Publication Scan",
        details=(
            f"Disclosed Model: {submission.ai_model_disclosed} | "
            f"Findings Flagged: {len(findings_created)} | "
            f"Compliance Score: {submission.compliance_score}%"
        ),
    )

    return findings_created