from django.contrib import admin

from .models import AuditEvent, Facility, IngestionBatch, NormalizedActivity, RawRecord, SourceSystem, Tenant


admin.site.register(Tenant)
admin.site.register(Facility)
admin.site.register(SourceSystem)
admin.site.register(IngestionBatch)
admin.site.register(RawRecord)
admin.site.register(NormalizedActivity)
admin.site.register(AuditEvent)
