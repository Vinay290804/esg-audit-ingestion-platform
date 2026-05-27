import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import AuditEvent, IngestionBatch, NormalizedActivity, RawRecord, SourceSystem
from .services import IngestionError, activity_snapshot, bootstrap_demo_data, ingest_file, seed_demo_records


def index(request):
    bootstrap_demo_data()
    return render(request, "index.html")


def serialize_activity(activity):
    source = activity.raw_record.batch.source
    return {
        "id": activity.id,
        "source": source.get_source_type_display(),
        "batch": activity.raw_record.batch.filename,
        "facility": activity.facility.name if activity.facility else "Unmapped",
        "activity_type": activity.activity_type,
        "scope": activity.get_scope_display(),
        "activity_date": activity.activity_date.isoformat(),
        "period": [
            activity.period_start.isoformat() if activity.period_start else None,
            activity.period_end.isoformat() if activity.period_end else None,
        ],
        "quantity": float(activity.quantity),
        "unit": activity.unit,
        "normalized_quantity": float(activity.normalized_quantity),
        "normalized_unit": activity.normalized_unit,
        "co2e_kg": float(activity.co2e_kg or 0),
        "source_reference": activity.source_reference,
        "description": activity.description,
        "suspicious_reasons": activity.suspicious_reasons,
        "review_status": activity.review_status,
        "edited": activity.edited,
        "raw": activity.raw_record.payload,
    }


def dashboard(request):
    tenant = seed_demo_records()
    activities = NormalizedActivity.objects.filter(tenant=tenant).select_related(
        "facility", "raw_record", "raw_record__batch", "raw_record__batch__source"
    )
    batches = IngestionBatch.objects.filter(tenant=tenant).select_related("source")
    totals = {
        "rows": activities.count(),
        "pending": activities.filter(review_status=NormalizedActivity.PENDING).count(),
        "approved": activities.filter(review_status=NormalizedActivity.APPROVED).count(),
        "locked": activities.filter(review_status=NormalizedActivity.LOCKED).count(),
        "warnings": activities.exclude(suspicious_reasons=[]).count(),
        "failed": RawRecord.objects.filter(batch__tenant=tenant, status="failed").count(),
        "co2e_kg": float(sum([activity.co2e_kg or 0 for activity in activities])),
    }
    return JsonResponse(
        {
            "tenant": {"id": tenant.id, "name": tenant.name},
            "totals": totals,
            "sources": [
                {"value": key, "label": label}
                for key, label in SourceSystem.SOURCE_TYPES
            ],
            "batches": [
                {
                    "id": batch.id,
                    "filename": batch.filename,
                    "source": batch.source.get_source_type_display(),
                    "imported_at": batch.imported_at.isoformat(),
                    "total_rows": batch.total_rows,
                    "accepted_rows": batch.accepted_rows,
                    "warning_rows": batch.warning_rows,
                    "failed_rows": batch.failed_rows,
                }
                for batch in batches
            ],
            "activities": [serialize_activity(activity) for activity in activities[:300]],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def upload(request):
    tenant = bootstrap_demo_data()
    source_type = request.POST.get("source_type")
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "file is required"}, status=400)
    if source_type not in dict(SourceSystem.SOURCE_TYPES):
        return JsonResponse({"error": "unknown source_type"}, status=400)
    try:
        batch = ingest_file(tenant, source_type, uploaded_file)
    except IngestionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"batch_id": batch.id, "message": "Imported %s rows" % batch.total_rows})


@csrf_exempt
@require_http_methods(["POST"])
def review_activity(request, activity_id):
    activity = get_object_or_404(NormalizedActivity, pk=activity_id)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "request body must be valid JSON"}, status=400)
    action = payload.get("action")
    before = activity_snapshot(activity)
    if activity.review_status == NormalizedActivity.LOCKED:
        return JsonResponse({"error": "locked activities cannot be changed"}, status=409)
    if action == "approve":
        activity.review_status = NormalizedActivity.APPROVED
    elif action == "reject":
        activity.review_status = NormalizedActivity.REJECTED
    elif action == "lock":
        activity.review_status = NormalizedActivity.LOCKED
        activity.locked_at = timezone.now()
    else:
        return JsonResponse({"error": "action must be approve, reject, or lock"}, status=400)
    activity.save()
    AuditEvent.objects.create(
        activity=activity,
        actor=payload.get("actor", "analyst"),
        action=action,
        before=before,
        after=activity_snapshot(activity),
    )
    return JsonResponse(serialize_activity(activity))
