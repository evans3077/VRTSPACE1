"""SEO strategy report PDF generation via Playwright HTML rendering."""

from apps.tools.pdf_reports import _build_seo_report_html, _html_to_pdf_bytes


def build_seo_report_pdf(payload):
    html_content = _build_seo_report_html(payload)
    return _html_to_pdf_bytes(html_content)
