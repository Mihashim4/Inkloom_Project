# Register your models here.
from django.contrib import admin
from .models import BrandRule, ContentSubmission, ExplainableFinding, AuditLog

admin.site.register(BrandRule)
admin.site.register(ContentSubmission)
admin.site.register(ExplainableFinding)
admin.site.register(AuditLog)