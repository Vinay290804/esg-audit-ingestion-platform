import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from .models import (
    AuditEvent,
    Facility,
    IngestionBatch,
    NormalizedActivity,
    RawRecord,
    SourceSystem,
    Tenant,
)


class IngestionError(ValueError):
    pass


SAP_HEADER_MAP = {
    "Buchungsdatum": "posting_date",
    "Werk": "plant",
    "Materialkurztext": "material_description",
    "Menge": "quantity",
    "Basismengeneinheit": "unit",
    "Materialbeleg": "document",
    "Kostenstelle": "cost_center",
}

UNIT_FACTORS = {
    "L": ("litre", Decimal("1")),
    "LTR": ("litre", Decimal("1")),
    "GAL": ("litre", Decimal("3.78541")),
    "KWH": ("kWh", Decimal("1")),
    "MWH": ("kWh", Decimal("1000")),
    "MILE": ("mile", Decimal("1")),
    "MI": ("mile", Decimal("1")),
    "KM": ("mile", Decimal("0.621371")),
    "NIGHT": ("night", Decimal("1")),
}

EMISSION_FACTORS = {
    "diesel": Decimal("2.68"),
    "gasoline": Decimal("2.31"),
    "natural_gas": Decimal("5.30"),
    "electricity_us_grid": Decimal("0.386"),
    "flight": Decimal("0.158"),
    "hotel_night": Decimal("19.00"),
    "rental_car": Decimal("0.251"),
    "rail": Decimal("0.041"),
}

AIRPORT_DISTANCE_MILES = {
    ("JFK", "LHR"): Decimal("3451"),
    ("SFO", "ORD"): Decimal("1846"),
    ("BOS", "SFO"): Decimal("2704"),
    ("DEL", "BOM"): Decimal("708"),
    ("LAX", "SEA"): Decimal("954"),
}


def bootstrap_demo_data():
    tenant, _ = Tenant.objects.get_or_create(slug="acme-industrial", defaults={"name": "Acme Industrial"})
    facilities = {
        "1000": ("Bayonne Chemical Plant", "US"),
        "2000": ("Austin Assembly", "US"),
        "BER1": ("Berlin Sales Office", "DE"),
    }
    for code, (name, country) in facilities.items():
        Facility.objects.get_or_create(tenant=tenant, code=code, defaults={"name": name, "country": country})

    sources = (
        (SourceSystem.SAP, "SAP S/4 Material Document export", "CSV exported from A_MaterialDocumentItem OData"),
        (SourceSystem.UTILITY, "Utility portal electricity export", "CSV modeled on Green Button interval and bill data"),
        (SourceSystem.TRAVEL, "SAP Concur card/expense extract", "JSON export from corporate card and expense report APIs"),
    )
    for source_type, name, mode in sources:
        SourceSystem.objects.get_or_create(
            tenant=tenant,
            source_type=source_type,
            defaults={"name": name, "extraction_mode": mode},
        )
    return tenant


def seed_demo_records():
    tenant = bootstrap_demo_data()
    if IngestionBatch.objects.filter(tenant=tenant).exists():
        return tenant
    samples = (
        (SourceSystem.SAP, "sample_data/sap_material_documents.csv"),
        (SourceSystem.UTILITY, "sample_data/utility_electricity.csv"),
        (SourceSystem.TRAVEL, "sample_data/concur_travel_transactions.json"),
    )
    for source_type, relative_path in samples:
        path = Path(settings.BASE_DIR) / relative_path
        if path.exists():
            upload = ContentFile(path.read_bytes(), name=path.name)
            ingest_file(tenant, source_type, upload, imported_by="demo seed")
    return tenant


def parse_decimal(value):
    if value is None or value == "":
        raise ValueError("missing numeric value")
    try:
        cleaned = str(value).strip().replace(",", "")
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("invalid numeric value: %s" % value)


def parse_date(value):
    if not value:
        raise ValueError("missing date")
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    raise ValueError("unsupported date format: %s" % value)


def normalize_unit(unit, quantity):
    key = str(unit or "").strip().upper()
    if key not in UNIT_FACTORS:
        raise ValueError("unsupported unit: %s" % unit)
    normalized_unit, factor = UNIT_FACTORS[key]
    return normalized_unit, quantity * factor


def source_for(tenant, source_type):
    return SourceSystem.objects.get(tenant=tenant, source_type=source_type)


@transaction.atomic
def ingest_file(tenant, source_type, uploaded_file, imported_by="analyst"):
    source = source_for(tenant, source_type)
    try:
        content = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestionError("file must be UTF-8 encoded")
    rows = read_rows(source_type, content)
    if not rows:
        raise IngestionError("file did not contain any rows")
    batch = IngestionBatch.objects.create(
        tenant=tenant,
        source=source,
        filename=getattr(uploaded_file, "name", "upload"),
        imported_by=imported_by,
    )
    for index, row in enumerate(rows, start=1):
        process_row(batch, source_type, index, row)
    refresh_batch_counts(batch)
    return batch


def read_rows(source_type, content):
    if source_type == SourceSystem.TRAVEL:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            raise IngestionError("travel upload must be valid JSON")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("transactions"), list):
            return payload["transactions"]
        raise IngestionError("travel JSON must be a list or contain a transactions list")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise IngestionError("CSV upload is missing a header row")
    rows = []
    for row in reader:
        if None in row:
            raise IngestionError("CSV row has more values than headers")
        normalized = {}
        for key, value in row.items():
            normalized[SAP_HEADER_MAP.get(key, key)] = value
        rows.append(normalized)
    return rows


def process_row(batch, source_type, row_number, row):
    raw = RawRecord.objects.create(batch=batch, row_number=row_number, payload=row)
    try:
        activity = build_activity(batch.tenant, source_type, raw, row)
    except Exception as exc:
        raw.status = "failed"
        raw.errors = [str(exc)]
        raw.save(update_fields=["status", "errors"])
        return

    raw.status = "warning" if activity.suspicious_reasons else "accepted"
    raw.warnings = activity.suspicious_reasons
    raw.source_row_id = activity.source_reference
    raw.save(update_fields=["status", "warnings", "source_row_id"])
    AuditEvent.objects.create(activity=activity, action="ingested", after=activity_snapshot(activity))


def build_activity(tenant, source_type, raw, row):
    if source_type == SourceSystem.SAP:
        return build_sap_activity(tenant, raw, row)
    if source_type == SourceSystem.UTILITY:
        return build_utility_activity(tenant, raw, row)
    if source_type == SourceSystem.TRAVEL:
        return build_travel_activity(tenant, raw, row)
    raise ValueError("unsupported source type")


def build_sap_activity(tenant, raw, row):
    quantity = parse_decimal(row.get("quantity"))
    unit, normalized_quantity = normalize_unit(row.get("unit"), quantity)
    material = (row.get("material_description") or "").lower()
    fuel_type = "diesel" if "diesel" in material else "gasoline" if "gasoline" in material else "natural_gas"
    plant_code = row.get("plant")
    facility = Facility.objects.filter(tenant=tenant, code=plant_code).first()
    warnings = []
    if not facility:
        warnings.append("Unknown SAP plant code")
    if normalized_quantity > Decimal("50000"):
        warnings.append("Fuel quantity exceeds expected single-row threshold")
    activity_date = parse_date(row.get("posting_date"))
    return NormalizedActivity.objects.create(
        tenant=tenant,
        raw_record=raw,
        facility=facility,
        activity_type=fuel_type,
        scope=NormalizedActivity.SCOPE_1,
        activity_date=activity_date,
        quantity=quantity,
        unit=row.get("unit", ""),
        normalized_quantity=normalized_quantity,
        normalized_unit=unit,
        co2e_kg=normalized_quantity * EMISSION_FACTORS[fuel_type],
        source_reference=row.get("document") or "sap-row-%s" % raw.row_number,
        description=row.get("material_description", ""),
        suspicious_reasons=warnings,
    )


def build_utility_activity(tenant, raw, row):
    quantity = parse_decimal(row.get("usage_quantity"))
    unit, normalized_quantity = normalize_unit(row.get("usage_unit"), quantity)
    start = parse_date(row.get("period_start"))
    end = parse_date(row.get("period_end"))
    facility = Facility.objects.filter(tenant=tenant, code=row.get("facility_code")).first()
    warnings = []
    if not facility:
        warnings.append("Unknown utility facility code")
    if (end - start).days > 45:
        warnings.append("Billing period is longer than 45 days")
    demand_kw = row.get("demand_kw")
    if demand_kw and parse_decimal(demand_kw) > Decimal("1000"):
        warnings.append("Demand charge basis unusually high")
    return NormalizedActivity.objects.create(
        tenant=tenant,
        raw_record=raw,
        facility=facility,
        activity_type="electricity",
        scope=NormalizedActivity.SCOPE_2,
        activity_date=end,
        period_start=start,
        period_end=end,
        quantity=quantity,
        unit=row.get("usage_unit", ""),
        normalized_quantity=normalized_quantity,
        normalized_unit=unit,
        co2e_kg=normalized_quantity * EMISSION_FACTORS["electricity_us_grid"],
        source_reference=row.get("bill_id") or row.get("meter_id") or "utility-row-%s" % raw.row_number,
        description="%s tariff %s" % (row.get("meter_id", "meter"), row.get("tariff_code", "")),
        suspicious_reasons=warnings,
    )


def build_travel_activity(tenant, raw, row):
    category = (row.get("category") or "").lower()
    facility = Facility.objects.filter(tenant=tenant, code=row.get("home_facility_code")).first()
    warnings = []
    if category == "flight":
        origin = row.get("origin_airport")
        destination = row.get("destination_airport")
        quantity = parse_decimal(row.get("distance_miles")) if row.get("distance_miles") else airport_distance(origin, destination)
        unit, normalized_quantity = normalize_unit("mile", quantity)
        factor = EMISSION_FACTORS["flight"]
        description = "%s to %s" % (origin, destination)
        if not row.get("distance_miles"):
            warnings.append("Distance inferred from airport pair")
    elif category == "hotel":
        quantity = parse_decimal(row.get("nights"))
        unit, normalized_quantity = normalize_unit("night", quantity)
        factor = EMISSION_FACTORS["hotel_night"]
        description = row.get("merchant", "hotel stay")
    elif category in ("car", "ground"):
        quantity = parse_decimal(row.get("distance_miles"))
        unit, normalized_quantity = normalize_unit("mile", quantity)
        factor = EMISSION_FACTORS["rental_car"]
        description = row.get("merchant", "ground transport")
    else:
        raise ValueError("unsupported travel category: %s" % category)
    if not facility:
        warnings.append("Unknown employee home facility")
    return NormalizedActivity.objects.create(
        tenant=tenant,
        raw_record=raw,
        facility=facility,
        activity_type=category,
        scope=NormalizedActivity.SCOPE_3,
        activity_date=parse_date(row.get("transaction_date")),
        quantity=quantity,
        unit=unit,
        normalized_quantity=normalized_quantity,
        normalized_unit=unit,
        co2e_kg=normalized_quantity * factor,
        source_reference=row.get("transaction_id") or "travel-row-%s" % raw.row_number,
        description=description,
        suspicious_reasons=warnings,
    )


def airport_distance(origin, destination):
    pair = (origin, destination)
    reverse = (destination, origin)
    if pair in AIRPORT_DISTANCE_MILES:
        return AIRPORT_DISTANCE_MILES[pair]
    if reverse in AIRPORT_DISTANCE_MILES:
        return AIRPORT_DISTANCE_MILES[reverse]
    raise ValueError("distance missing and airport pair unknown")


def refresh_batch_counts(batch):
    raw_records = batch.raw_records.all()
    batch.total_rows = raw_records.count()
    batch.failed_rows = raw_records.filter(status="failed").count()
    batch.warning_rows = raw_records.filter(status="warning").count()
    batch.accepted_rows = raw_records.filter(status="accepted").count()
    batch.status = IngestionBatch.PROCESSED
    batch.save()


def activity_snapshot(activity):
    return {
        "id": activity.id,
        "review_status": activity.review_status,
        "co2e_kg": str(activity.co2e_kg),
        "normalized_quantity": str(activity.normalized_quantity),
        "suspicious_reasons": activity.suspicious_reasons,
    }
