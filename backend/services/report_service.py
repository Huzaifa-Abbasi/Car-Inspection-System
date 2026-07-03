"""
Report generation and email delivery service.

Uses Jinja2 templates + WeasyPrint for PDF generation,
and aiosmtplib for email sending.
"""

from pathlib import Path
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader

from backend.config import settings
from backend.models import Inspection

# Try to import WeasyPrint — it may not be installed or fully configured (e.g. missing GTK on Windows)
import os
import sys

if sys.platform == "win32":
    # Common installation paths for GTK on Windows (MSYS2 or gvsbuild)
    _gtk_paths = [
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\ucrt64\bin",
        r"C:\gvsbuild\release\bin",
    ]
    for _path in _gtk_paths:
        if os.path.exists(_path):
            try:
                os.add_dll_directory(_path)
            except Exception:
                pass

try:
    from weasyprint import HTML as WeasyprintHTML
    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False

# Try to import aiosmtplib for email
try:
    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    HAS_SMTP = True
except ImportError:
    HAS_SMTP = False


class ReportService:
    """Generate PDF reports and send them via email."""

    def __init__(self):
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(settings.TEMPLATES_DIR)),
            autoescape=True,
        )

    def get_report_path(self, inspection_id: str) -> Path:
        """Get the file path where a report PDF is stored."""
        settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        return settings.REPORTS_DIR / f"report_{inspection_id}.pdf"

    def generate_pdf(self, inspection: Inspection) -> Path:
        """
        Generate a branded PDF report for the given inspection.

        Returns the path to the generated PDF file.
        """
        # Separate confirmed vs rejected defects
        all_defects = inspection.defects or []
        confirmed_defects = [d for d in all_defects if d.status != "rejected"]
        rejected_defects = [d for d in all_defects if d.status == "rejected"]

        # Severity counts
        severity_counts = {"severe": 0, "moderate": 0, "minor": 0}
        for d in confirmed_defects:
            if d.severity in severity_counts:
                severity_counts[d.severity] += 1

        # Render HTML template
        template = self._jinja_env.get_template("report_template.html")
        html_content = template.render(
            company_name=settings.COMPANY_NAME,
            company_tagline=settings.COMPANY_TAGLINE,
            inspection=inspection,
            vehicle=inspection.vehicle,
            inspector=inspection.inspector,
            defects=confirmed_defects,
            rejected_defects=rejected_defects,
            severity_counts=severity_counts,
            total_confirmed=len(confirmed_defects),
            total_rejected=len(rejected_defects),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            uploads_base=str(settings.UPLOADS_DIR.parent),
        )

        pdf_path = self.get_report_path(inspection.id)

        if HAS_WEASYPRINT:
            WeasyprintHTML(string=html_content).write_pdf(str(pdf_path))
        else:
            # Fallback: save as HTML if WeasyPrint is not installed
            html_path = pdf_path.with_suffix(".html")
            html_path.write_text(html_content, encoding="utf-8")
            # Create a minimal PDF-like placeholder
            pdf_path.write_text(
                "WeasyPrint not installed. Report saved as HTML at: "
                + str(html_path),
                encoding="utf-8",
            )

        return pdf_path

    async def send_email(
        self,
        recipients: list[str],
        inspection: Inspection,
        pdf_path: Path,
        note: str | None = None,
    ):
        """Send the report PDF as an email attachment."""
        if not HAS_SMTP:
            raise RuntimeError("aiosmtplib is not installed")

        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            raise RuntimeError(
                "SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD in .env"
            )

        vehicle = inspection.vehicle
        vehicle_name = f"{vehicle.make} {vehicle.model}" if vehicle else "Unknown Vehicle"

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"Vehicle Inspection Report — {vehicle_name}"

        # Email body
        body = f"""
Dear Sir/Madam,

Please find attached the vehicle inspection report for:

Vehicle: {vehicle_name}
License Plate: {vehicle.license_plate or 'N/A'}
Inspection Date: {inspection.started_at.strftime('%Y-%m-%d') if inspection.started_at else 'N/A'}
Inspector: {inspection.inspector.name if inspection.inspector else 'N/A'}
"""
        if note:
            body += f"\nAdditional Note: {note}\n"

        body += f"""
This report was generated by {settings.COMPANY_NAME}.

Best regards,
{settings.COMPANY_NAME}
{settings.COMPANY_TAGLINE}
"""
        msg.attach(MIMEText(body, "plain"))

        # Attach PDF
        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"inspection_report_{inspection.id}.pdf",
                )
                msg.attach(attachment)

        # Send
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
