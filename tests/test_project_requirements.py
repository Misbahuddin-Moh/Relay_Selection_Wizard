import io
import unittest
from unittest.mock import patch

from pypdf import PdfWriter

from backend.project_requirements import Finding, extract_requirements, source_pages


class ProjectRequirementsTests(unittest.TestCase):
    def test_only_matching_excerpts_survive_and_blank_pages_are_reported(self):
        excerpt = "Provide a minimum of two three-phase VT banks on Transformer Primary."
        candidate = Finding(
            page=1, quote=excerpt, scope="Transformer Primary",
            requirement="Two three-phase VT banks", category="vt_banks",
            status="required", timing="purchase", minimum=2,
        )
        pages = {**source_pages(excerpt.encode(), "text/plain"), 2: ""}
        with patch("backend.project_requirements.request_findings", return_value=[
            candidate, candidate, candidate.model_copy(update={"page": 2}),
            candidate.model_copy(update={"quote": "Invented requirement"}),
        ]) as request:
            result = extract_requirements(pages)

        request.assert_called_once_with([{"page": 1, "text": excerpt}])
        self.assertEqual(result["findings"], [candidate])
        self.assertEqual(result["pages_processed"], 1)
        self.assertEqual(result["unreadable_pages"], [2])
        self.assertEqual(result["unverified_findings"], 2)

    def test_pdf_with_no_text_is_reported_without_calling_provider(self):
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        pdf = io.BytesIO()
        writer.write(pdf)
        with patch("backend.project_requirements.request_findings") as request:
            result = extract_requirements(source_pages(pdf.getvalue(), "application/pdf"))

        request.assert_not_called()
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["unreadable_pages"], [1])
