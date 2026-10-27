from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import BrandRuleForm, ContentSubmissionForm
from .models import BrandRule, ContentSubmission, ExplainableFinding, AuditLog
from .ai_engine import run_pre_publication_governance_scan, seed_default_brand_knowledge_base


def dashboard_view(request):
    seed_default_brand_knowledge_base()

    if request.method == 'POST' and 'submit_content' in request.POST:
        form = ContentSubmissionForm(request.POST)
        if not form.is_valid():
            for error in form.errors.values():
                messages.error(request, error)
            return redirect('dashboard')
        sub = form.save()
        run_pre_publication_governance_scan(sub)
        messages.success(request, f"'{sub.title}' checked against Inkloom governance rules.")
        return redirect('review_detail', pk=sub.pk)

    if request.method == 'POST' and 'add_rule' in request.POST:
        form = BrandRuleForm(request.POST)
        if not form.is_valid():
            for error in form.errors.values():
                messages.error(request, error)
            return redirect('dashboard')
        form.save()
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

        if action_type == 'accept_fix':
            finding_id = request.POST.get('finding_id')
            finding = get_object_or_404(ExplainableFinding, id=finding_id, submission=submission)
            if finding.creator_decision != 'OPEN':
                messages.error(request, "This finding has already been resolved.")
                return redirect('review_detail', pk=submission.pk)

            with transaction.atomic():
                if finding.rule_code == 'VIS-01':
                    submission.hex_color_used = finding.suggested_fix
                elif finding.rule_code == 'A11Y-01':
                    submission.alt_text_provided = finding.suggested_fix
                else:
                    submission.working_text = submission.working_text.replace(
                        finding.flagged_snippet, finding.suggested_fix
                    )

                finding.creator_decision = 'ACCEPTED'
                finding.save()
                _update_submission_workflow(submission)
                submission.save()
                AuditLog.objects.create(
                    submission=submission,
                    actor_name=submission.creator_name,
                    actor_role="Content Creator",
                    action=f"Accepted AI Fix for [{finding.rule_code}]",
                    details=f"Replaced '{finding.flagged_snippet}' with '{finding.suggested_fix}'",
                )
            messages.success(request, f"Applied suggested fix for {finding.rule_code}.")

        elif action_type == 'override_flag':
            finding_id = request.POST.get('finding_id')
            finding = get_object_or_404(ExplainableFinding, id=finding_id, submission=submission)
            justification = request.POST.get('justification', '').strip()
            if not justification:
                messages.error(request, "Provide a justification before overriding a finding.")
                return redirect('review_detail', pk=submission.pk)
            if finding.creator_decision != 'OPEN':
                messages.error(request, "This finding has already been resolved.")
                return redirect('review_detail', pk=submission.pk)

            with transaction.atomic():
                finding.creator_decision = 'OVERRIDDEN'
                finding.human_note = justification
                finding.save()
                _update_submission_workflow(submission)
                submission.save()
                AuditLog.objects.create(
                    submission=submission,
                    actor_name=submission.creator_name,
                    actor_role="Content Creator",
                    action=f"Overrode AI Flag [{finding.rule_code}]",
                    details=f"Human Justification: {justification}",
                )
            messages.warning(request, f"Flag {finding.rule_code} overridden with justification.")

        elif action_type == 'manager_decision':
            decision = request.POST.get('manager_status')
            manager_comment = request.POST.get('manager_comment', '').strip()
            allowed_decisions = {'APPROVED', 'REJECTED'}
            unresolved_findings = submission.findings.filter(creator_decision='OPEN').exists()
            if decision not in allowed_decisions:
                messages.error(request, "Choose either approve or request changes.")
            elif decision == 'APPROVED' and unresolved_findings:
                messages.error(request, "Resolve or override every open finding before approval.")
            else:
                with transaction.atomic():
                    submission.status = decision
                    submission.save()
                    AuditLog.objects.create(
                        submission=submission,
                        actor_name="Priya Nair (Brand Manager)",
                        actor_role="Authorised Reviewer",
                        action=f"Final Governance Decision: {decision}",
                        details=f"Reviewer Note: {manager_comment or 'No reviewer note provided.'}",
                    )
                messages.info(request, f"Submission marked as {submission.get_status_display()}.")

        return redirect('review_detail', pk=submission.pk)

    return render(request, 'governance/review_detail.html', {
        'submission': submission,
        'findings': findings,
        'audit_logs': audit_logs,
    })


def _update_submission_workflow(submission):
    open_findings = submission.findings.filter(creator_decision='OPEN')
    if open_findings.filter(requires_human_escalation=True).exists():
        submission.status = 'ESCALATED'
    elif open_findings.exists():
        submission.status = 'PENDING_REVIEW'
    else:
        submission.status = 'READY_FOR_MANAGER'
    resolved_count = submission.findings.exclude(creator_decision='OPEN').count()
    submission.compliance_score = max(
        10, min(100, 100 - open_findings.count() * 15 + resolved_count * 5)
    )