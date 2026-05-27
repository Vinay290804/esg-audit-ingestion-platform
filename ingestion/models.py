from django.db import models
from django.utils import timezone
import json


class JSONTextField(models.TextField):
    description = "JSON stored as text for SQLite builds without JSON1"

    def __init__(self, *args, **kwargs):
        if kwargs.get("default") in (list, dict):
            kwargs["default"] = kwargs["default"]
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return json.loads(value)

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        return json.dumps(value)


class Tenant(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Facility(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="facilities")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    country = models.CharField(max_length=2, default="US")

    class Meta:
        unique_together = ("tenant", "code")

    def __str__(self):
        return "%s - %s" % (self.code, self.name)


class SourceSystem(models.Model):
    SAP = "sap"
    UTILITY = "utility"
    TRAVEL = "travel"
    SOURCE_TYPES = (
        (SAP, "SAP fuel/procurement"),
        (UTILITY, "Utility electricity"),
        (TRAVEL, "Corporate travel"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    name = models.CharField(max_length=160)
    extraction_mode = models.CharField(max_length=160)

    def __str__(self):
        return self.name


class IngestionBatch(models.Model):
    PENDING = "pending"
    PROCESSED = "processed"
    STATUS_CHOICES = ((PENDING, "Pending"), (PROCESSED, "Processed"))

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="batches")
    source = models.ForeignKey(SourceSystem, on_delete=models.PROTECT, related_name="batches")
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    imported_at = models.DateTimeField(default=timezone.now)
    imported_by = models.CharField(max_length=120, default="analyst")
    total_rows = models.PositiveIntegerField(default=0)
    accepted_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-imported_at",)


class RawRecord(models.Model):
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="raw_records")
    row_number = models.PositiveIntegerField()
    source_row_id = models.CharField(max_length=120, blank=True)
    payload = JSONTextField()
    status = models.CharField(max_length=20, default="accepted")
    errors = JSONTextField(default=list, blank=True)
    warnings = JSONTextField(default=list, blank=True)

    class Meta:
        unique_together = ("batch", "row_number")


class NormalizedActivity(models.Model):
    SCOPE_1 = "scope_1"
    SCOPE_2 = "scope_2"
    SCOPE_3 = "scope_3"
    SCOPE_CHOICES = (
        (SCOPE_1, "Scope 1"),
        (SCOPE_2, "Scope 2"),
        (SCOPE_3, "Scope 3"),
    )
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    LOCKED = "locked"
    REVIEW_CHOICES = (
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (LOCKED, "Locked"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="activities")
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name="activity")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, null=True, blank=True)
    activity_type = models.CharField(max_length=80)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=30)
    normalized_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    normalized_unit = models.CharField(max_length=30)
    co2e_kg = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    source_reference = models.CharField(max_length=160)
    description = models.CharField(max_length=255, blank=True)
    suspicious_reasons = JSONTextField(default=list, blank=True)
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default=PENDING)
    edited = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("review_status", "-activity_date")


class AuditEvent(models.Model):
    activity = models.ForeignKey(NormalizedActivity, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.CharField(max_length=120, default="analyst")
    action = models.CharField(max_length=80)
    before = JSONTextField(null=True, blank=True)
    after = JSONTextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
