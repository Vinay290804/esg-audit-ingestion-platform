from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import IngestionBatch, NormalizedActivity, RawRecord, SourceSystem
from .services import bootstrap_demo_data, ingest_file


class IngestionTests(TestCase):
    def setUp(self):
        self.tenant = bootstrap_demo_data()

    def upload_sample(self, source_type, filename):
        path = Path(__file__).resolve().parent.parent / "sample_data" / filename
        return ingest_file(self.tenant, source_type, ContentFile(path.read_bytes(), name=filename))

    def test_sap_ingestion_handles_german_headers_and_flags_unknown_plant(self):
        batch = self.upload_sample(SourceSystem.SAP, "sap_material_documents.csv")

        self.assertEqual(batch.total_rows, 4)
        self.assertEqual(NormalizedActivity.objects.filter(scope=NormalizedActivity.SCOPE_1).count(), 4)
        self.assertIn("Unknown SAP plant code", flatten_flags())

    def test_utility_ingestion_flags_billing_period_and_demand(self):
        batch = self.upload_sample(SourceSystem.UTILITY, "utility_electricity.csv")

        self.assertEqual(batch.total_rows, 4)
        self.assertIn("Billing period is longer than 45 days", flatten_flags())
        self.assertIn("Demand charge basis unusually high", flatten_flags())

    def test_travel_ingestion_infers_flight_distance(self):
        self.upload_sample(SourceSystem.TRAVEL, "concur_travel_transactions.json")

        self.assertEqual(IngestionBatch.objects.count(), 1)
        self.assertEqual(RawRecord.objects.filter(status="failed").count(), 0)
        self.assertIn("Distance inferred from airport pair", flatten_flags())

    def test_upload_view_returns_400_for_invalid_travel_json(self):
        response = self.client.post(
            "/api/upload/",
            {
                "source_type": SourceSystem.TRAVEL,
                "file": SimpleUploadedFile("bad.json", b"{not json", content_type="application/json"),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid JSON", response.json()["error"])

    def test_review_view_returns_400_for_invalid_json_body(self):
        self.upload_sample(SourceSystem.SAP, "sap_material_documents.csv")
        activity = NormalizedActivity.objects.first()

        response = self.client.post(
            "/api/activities/%s/review/" % activity.id,
            data="{not json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "request body must be valid JSON")


def flatten_flags():
    flags = []
    for activity in NormalizedActivity.objects.all():
        flags.extend(activity.suspicious_reasons)
    return flags
