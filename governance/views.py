from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import BrandRule, ContentSubmission, ExplainableFinding, AuditLog
from .ai_engine import run_pre_publication_governance_scan, seed_default_brand_knowledge_base


def dashboard_view(request):
    seed_default_brand_knowledge_base()

    if request.method == 'POST' and 'submit_content' in request.POST:
        title = request.POST.get('title', 'Untitled Campaign Post')
        creator_name = request.POST.get('creator_name', 'Alex (Content Marketer)')
        content_format = request.POST.get('content_format', 'SOCIAL')
        original_text = request.POST.get('original_text', '')
        hex_color = request.POST.get('hex_color_used', '#2563EB')
        alt_text = request.POST.get('alt_text_provided', '')

        sub = ContentSubmission.objects.create(
            title=title,
            creator_name=creator_name,
            content_format=content_format,
            original_text=original_text,
            working_text=original_text,
            hex_color_used=hex_color,
            alt_text_provided=alt_text,
        )
        run_pre_publication_governance_scan(sub)
        messages.success(request, f"'{sub.title}' analyzed by Inkloom AI Copilot!")
        return redirect('review_detail', pk=sub.pk)

    if request.method == 'POST' and 'add_rule' in request.POST:
        BrandRule.objects.create(
            rule_code=request.POST.get('rule_code', 'CUSTOM-01'),
            title=request.POST.get('rule_title', 'Custom Brand Rule'),
            category=request.POST.get('category', 'TERM'),
            severity=request.POST.get('severity', 'MEDIUM'),
            forbidden_pattern=request.POST.get('forbidden_pattern', ''),
            approved_replacement=request.POST.get('approved_replacement', ''),
            guideline_clause=request.POST.get('guideline_clause', 'Brand Guideline Custom Clause'),
            rationale=request.POST.get('rationale', 'Ensures consistent brand messaging.'),
        )
        messages.info(request, "New rule added to Brand Knowledge Base!")
        return redirect('dashboard')

    submissions = ContentSubmission.objects.all().order_by('-created_at')
    rules = BrandRule.objects.all().order_by('-trigger_count')
    total_findings = ExplainableFinding.objects.count()
    resolved_findings = ExplainableFinding.objects.exclude(creator_decision='OPEN').count()

    context = {
        'submissions': submissions,
        'rules': rules,
        'total_submissions': submissions.count(),
        'approved_count': submissions.filter(status='APPROVED').count(),
        'total_findings': total_findings,
        'resolved_findings': resolved_findings,
    }
    return render(request, 'governance/dashboard.html', context)


def review_detail_view(request, pk):
    submission = get_object_or_404(ContentSubmission, pk=pk)
    findings = submission.findings.all()
    audit_logs = submission.audit_logs.all().order_by('-timestamp')

    if request.method == 'POST':
        action_type = request.POST.get('action_type')

        # 1. Creator Accepts AI Suggestion (No silent changes - explicitly triggered by human)
        if action_type == 'accept_fix':
            finding_id = request.POST.get('finding_id')
            finding = get_object_or_404(ExplainableFinding, id=finding_id, submission=submission)

            if finding.rule_code == 'VIS-01':
                submission.hex_color_used = '#2563EB'
            elif finding.rule_code == 'A11Y-01':
                submission.alt_text_provided = finding.suggested_fix
            else:
                submission.working_text = submission.working_text.replace(
                    finding.flagged_snippet, finding.suggested_fix
                )

            finding.creator_decision = 'ACCEPTED'
            finding.save()
            submission.compliance_score = min(100, submission.compliance_score + 15)
            submission.save()

            AuditLog.objects.create(
                submission=submission,
                actor_name=submission.creator_name,
                actor_role="Content Creator",
                action=f"Accepted AI Fix for [{finding.rule_code}]",
                details=f"Replaced '{finding.flagged_snippet}' with '{finding.suggested_fix}'",
            )
            messages.success(request, f"Applied suggested fix for {finding.rule_code}.")

        # 2. Creator Overrides AI Flag with Justification (Human-in-the-loop control)
        elif action_type == 'override_flag':
            finding_id = request.POST.get('finding_id')
            justification = request.POST.get('justification', 'Creative context exception approved.')
            finding = get_object_or_404(ExplainableFinding, id=finding_id, submission=submission)
            finding.creator_decision = 'OVERRIDDEN'
            finding.human_note = justification
            finding.save()

            AuditLog.objects.create(
                submission=submission,
                actor_name=submission.creator_name,
                actor_role="Content Creator",
                action=f"Overrode AI Flag [{finding.rule_code}]",
                details=f"Human Justification: {justification}",
            )
            messages.warning(request, f"Flag {finding.rule_code} overridden with justification.")

        # 3. Manager / Reviewer Final Approval or Rejection (Priya Nair Persona)
        elif action_type == 'manager_decision':
            decision = request.POST.get('manager_status')
            manager_comment = request.POST.get('manager_comment', 'Reviewed against brand guidelines.')
            submission.status = decision
            submission.save()

            AuditLog.objects.create(
                submission=submission,
                actor_name="Priya Nair (Brand Manager)",
                actor_role="Authorised Reviewer",
                action=f"Final Governance Decision: {decision}",
                details=f"Reviewer Note: {manager_comment}",
            )
            messages.info(request, f"Submission marked as {submission.get_status_display()}.")

        return redirect('review_detail', pk=submission.pk)

    return render(request, 'governance/review_detail.html', {
        'submission': submission,
        'findings': findings,
        'audit_logs': audit_logs,
    })