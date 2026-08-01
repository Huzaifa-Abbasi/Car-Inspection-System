"""
Report generation and email delivery service.

Uses Jinja2 templates + WeasyPrint for PDF generation,
with xhtml2pdf as a pure-Python fallback for frozen exe builds,
and ReportLab as an absolute last resort.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader

from backend.config import settings
from backend.models import Inspection

# Try to import WeasyPrint — it may not be installed or fully configured (e.g. missing GTK on Windows)
HAS_WEASYPRINT = False
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

# Try to import xhtml2pdf — pure Python fallback, works in PyInstaller bundles
HAS_XHTML2PDF = False
try:
    from xhtml2pdf import pisa
    HAS_XHTML2PDF = True
except (ImportError, OSError):
    HAS_XHTML2PDF = False

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
        Wraps all logic in a top-level try/except to prevent crashes from
        killing the server (e.g., GTK segfaults, missing relationships).
        """
        pdf_path = self.get_report_path(inspection.id)

        try:
            return self._generate_pdf_internal(inspection, pdf_path)
        except Exception as err:
            print(f"[ReportService] CRITICAL — generate_pdf failed: {err}")
            import traceback
            traceback.print_exc()
            # Create an emergency fallback PDF so the route doesn't 500
            self._create_emergency_pdf(pdf_path, inspection, str(err))
            return pdf_path

    def _generate_pdf_internal(self, inspection: Inspection, pdf_path: Path) -> Path:
        """Internal PDF generation with full fallback chain."""
        # Safely access relationships — they may be None if not loaded
        try:
            all_defects = list(inspection.defects) if inspection.defects else []
        except Exception:
            all_defects = []

        confirmed_defects = [d for d in all_defects if getattr(d, 'status', None) != "rejected"]
        rejected_defects = [d for d in all_defects if getattr(d, 'status', None) == "rejected"]

        # Format defect snapshot URIs and web relative paths for robust rendering
        for d in confirmed_defects:
            snapshot = getattr(d, 'snapshot_path', None)
            if snapshot:
                path_str = str(snapshot).replace("\\", "/")
                if path_str.startswith("uploads/"):
                    clean_rel = path_str[len("uploads/"):]
                elif path_str.startswith("/uploads/"):
                    clean_rel = path_str[len("/uploads/"):]
                else:
                    clean_rel = path_str

                d.web_snapshot_path = f"/uploads/{clean_rel}"

                full_p = settings.UPLOADS_DIR.parent / "uploads" / clean_rel
                if not full_p.exists():
                    full_p = settings.UPLOADS_DIR.parent / path_str
                if not full_p.exists():
                    full_p = settings.UPLOADS_DIR / clean_rel

                if full_p.exists():
                    d.snapshot_uri = full_p.as_uri()
                else:
                    d.snapshot_uri = d.web_snapshot_path
            else:
                d.web_snapshot_path = None
                d.snapshot_uri = None

        # Severity counts
        severity_counts = {"severe": 0, "moderate": 0, "minor": 0}
        for d in confirmed_defects:
            sev = getattr(d, 'severity', None)
            if sev in severity_counts:
                severity_counts[sev] += 1

        html_path = pdf_path.with_suffix(".html")

        project_root_uri = settings.PROJECT_ROOT.as_uri()
        uploads_base_uri = settings.UPLOADS_DIR.parent.as_uri()

        # Safely get vehicle and inspector (may be None)
        vehicle = None
        inspector = None
        try:
            vehicle = inspection.vehicle
        except Exception:
            pass
        try:
            inspector = inspection.inspector
        except Exception:
            pass

        # Render HTML template
        template = self._jinja_env.get_template("report_template.html")
        html_content = template.render(
            company_name=settings.COMPANY_NAME,
            company_tagline=settings.COMPANY_TAGLINE,
            inspection=inspection,
            vehicle=vehicle,
            inspector=inspector,
            defects=confirmed_defects,
            rejected_defects=rejected_defects,
            severity_counts=severity_counts,
            total_confirmed=len(confirmed_defects),
            total_rejected=len(rejected_defects),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            uploads_base=uploads_base_uri,
        )

        # Save HTML template output as reference preview
        try:
            html_path.write_text(html_content, encoding="utf-8")
        except Exception as err:
            print(f"[ReportService] Error saving HTML fallback: {err}")

        is_frozen = getattr(sys, "frozen", False)
        pdf_success = False

        # ── Attempt 1: WeasyPrint CLI Subprocess (Only in non-frozen dev/terminal mode) ────
        if HAS_WEASYPRINT and not is_frozen:
            try:
                import subprocess
                cmd = [sys.executable, "-m", "weasyprint", str(html_path), str(pdf_path)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
                if pdf_path.exists() and pdf_path.stat().st_size > 1024:
                    with open(pdf_path, "rb") as f:
                        if f.read(5).startswith(b"%PDF-"):
                            pdf_success = True
                            print("[ReportService] PDF generated via WeasyPrint CLI subprocess")
            except Exception as err:
                print(f"[ReportService] WeasyPrint CLI subprocess failed: {err}")

            if not pdf_success:
                try:
                    WeasyprintHTML(string=html_content, base_url=project_root_uri).write_pdf(str(pdf_path))
                    if pdf_path.exists() and pdf_path.stat().st_size > 1024:
                        with open(pdf_path, "rb") as f:
                            if f.read(5).startswith(b"%PDF-"):
                                pdf_success = True
                                print("[ReportService] PDF generated via in-process WeasyPrint")
                except Exception as err:
                    print(f"[ReportService] In-process WeasyPrint rendering failed: {err}")

        # ── Attempt 2: xhtml2pdf (pure Python, works in frozen exe) ──
        if not pdf_success and HAS_XHTML2PDF:
            try:
                pdf_success = self._generate_pdf_xhtml2pdf(
                    html_content=html_content,
                    pdf_path=pdf_path,
                )
                if pdf_success:
                    print("[ReportService] PDF generated via xhtml2pdf")
            except Exception as err:
                print(f"[ReportService] xhtml2pdf rendering failed: {err}")

        # ── Attempt 3: ReportLab (absolute last resort) ──────────────
        if not pdf_success:
            try:
                pdf_success = self._generate_pdf_reportlab(
                    inspection=inspection,
                    pdf_path=pdf_path,
                    confirmed_defects=confirmed_defects,
                    severity_counts=severity_counts,
                )
                if pdf_success:
                    print("[ReportService] PDF generated via ReportLab (fallback)")
            except Exception as err:
                print(f"[ReportService] ReportLab rendering failed: {err}")

        # ── Emergency: create a minimal PDF if all renderers failed ───
        if not pdf_success:
            self._create_emergency_pdf(pdf_path, inspection, "All PDF renderers failed")

        return pdf_path

    def _create_emergency_pdf(self, pdf_path: Path, inspection, error_msg: str):
        """Create a minimal valid PDF so the download endpoint doesn't crash."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"<b>{settings.COMPANY_NAME}</b>", styles['Title']),
                Spacer(1, 12),
                Paragraph("Vehicle Inspection Report", styles['Heading2']),
                Spacer(1, 12),
                Paragraph(
                    f"Inspection ID: {getattr(inspection, 'id', 'N/A')}",
                    styles['Normal'],
                ),
                Spacer(1, 8),
                Paragraph(
                    "No defects were detected during this inspection."
                    if not error_msg.startswith("All")
                    else f"Report generation encountered an error: {error_msg}",
                    styles['Normal'],
                ),
                Spacer(1, 12),
                Paragraph(
                    f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                    styles['Normal'],
                ),
            ]
            doc.build(story)
            print(f"[ReportService] Emergency fallback PDF created at {pdf_path}")
        except Exception as e:
            print(f"[ReportService] Even emergency PDF failed: {e}")
            # Write a minimal raw PDF as absolute last resort
            try:
                pdf_path.write_bytes(
                    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
                    b"xref\n0 4\n0000000000 65535 f \n"
                    b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
                    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
                )
            except Exception:
                pass

    def _generate_pdf_xhtml2pdf(
        self,
        html_content: str,
        pdf_path: Path,
    ) -> bool:
        """Generate PDF from the rendered HTML using xhtml2pdf (pure Python).

        Uses the same HTML template as WeasyPrint, ensuring visual consistency
        between terminal and frozen exe environments.
        """
        try:
            with open(pdf_path, "wb") as pdf_file:
                pisa_status = pisa.CreatePDF(
                    html_content,
                    dest=pdf_file,
                    encoding="utf-8",
                )

            if pisa_status.err:
                print(f"[ReportService] xhtml2pdf reported {pisa_status.err} error(s)")
                return False

            # Validate the generated PDF
            if pdf_path.exists() and pdf_path.stat().st_size > 1024:
                with open(pdf_path, "rb") as f:
                    if f.read(5).startswith(b"%PDF-"):
                        return True

            return False
        except Exception as e:
            print(f"[ReportService] xhtml2pdf rendering failed: {e}")
            return False

    def _generate_pdf_reportlab(
        self,
        inspection: Inspection,
        pdf_path: Path,
        confirmed_defects: list,
        severity_counts: dict,
    ) -> bool:
        """Fallback PDF generator using ReportLab matching the exact visual design of report_template.html."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=letter,
                leftMargin=36,
                rightMargin=36,
                topMargin=36,
                bottomMargin=36,
            )
            story = []
            styles = getSampleStyleSheet()

            # Helper for section headers with 2px cyan solid underline
            def add_section_header(title_text):
                p = Paragraph(f'<font color="#1a1a3e" size=13><b>{title_text}</b></font>', styles['Normal'])
                t = Table([[p], ['']], colWidths=[540], rowHeights=[20, 2])
                t.setStyle(TableStyle([
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#00E5FF')),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]))
                return t

            # Dark Header Banner Card
            hdr_data = [
                [Paragraph('<font color="#00E5FF" size=22><b>AutoScan Pro</b></font>', styles['Normal'])],
                [Paragraph('<font color="#aab" size=10>Professional Vehicle Inspection System</font>', styles['Normal'])],
                [Paragraph('<font color="#ffffff" size=13><b>🔍 VEHICLE INSPECTION REPORT</b></font>', styles['Normal'])],
            ]
            hdr_table = Table(hdr_data, colWidths=[540])
            hdr_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0a0a1a')),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 20),
                ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ]))
            story.append(hdr_table)
            story.append(Spacer(1, 16))

            # 1. Vehicle Information Section
            story.append(add_section_header('Vehicle Information'))
            story.append(Spacer(1, 8))

            vehicle = inspection.vehicle
            v_data = [
                [Paragraph('<font color="#555555"><b>Make:</b></font>', styles['Normal']), Paragraph(vehicle.make if vehicle and vehicle.make else "N/A", styles['Normal']), Paragraph('<font color="#555555"><b>Model:</b></font>', styles['Normal']), Paragraph(vehicle.model if vehicle and vehicle.model else "N/A", styles['Normal'])],
                [Paragraph('<font color="#555555"><b>Year:</b></font>', styles['Normal']), Paragraph(str(vehicle.year) if vehicle and vehicle.year else "N/A", styles['Normal']), Paragraph('<font color="#555555"><b>Color:</b></font>', styles['Normal']), Paragraph(vehicle.color if vehicle and vehicle.color else "N/A", styles['Normal'])],
                [Paragraph('<font color="#555555"><b>License Plate:</b></font>', styles['Normal']), Paragraph(vehicle.license_plate if vehicle and vehicle.license_plate else "N/A", styles['Normal']), Paragraph('<font color="#555555"><b>VIN:</b></font>', styles['Normal']), Paragraph(vehicle.vin if vehicle and vehicle.vin else "N/A", styles['Normal'])],
                [Paragraph('<font color="#555555"><b>Mileage:</b></font>', styles['Normal']), Paragraph(f"{vehicle.mileage:,} km" if vehicle and vehicle.mileage else "N/A km", styles['Normal']), Paragraph('<font color="#555555"><b>Owner:</b></font>', styles['Normal']), Paragraph(vehicle.owner_name if vehicle and vehicle.owner_name else "N/A", styles['Normal'])],
            ]
            v_table = Table(v_data, colWidths=[100, 170, 100, 170])
            v_table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(v_table)
            story.append(Spacer(1, 14))

            # 2. Inspection Details Section
            story.append(add_section_header('Inspection Details'))
            story.append(Spacer(1, 8))

            i_data = [
                [Paragraph('<font color="#555555"><b>Inspection ID:</b></font>', styles['Normal']), Paragraph(f"{inspection.id[:12]}...", styles['Normal']), Paragraph('<font color="#555555"><b>Inspector:</b></font>', styles['Normal']), Paragraph(inspection.inspector.name if inspection and inspection.inspector else "N/A", styles['Normal'])],
                [Paragraph('<font color="#555555"><b>Date:</b></font>', styles['Normal']), Paragraph(inspection.started_at.strftime('%B %d, %Y') if inspection and inspection.started_at else "N/A", styles['Normal']), Paragraph('<font color="#555555"><b>Status:</b></font>', styles['Normal']), Paragraph((inspection.status or 'N/A').capitalize(), styles['Normal'])],
            ]
            i_table = Table(i_data, colWidths=[100, 170, 100, 170])
            i_table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(i_table)
            story.append(Spacer(1, 14))

            # 3. Defect Summary Section
            story.append(add_section_header('Defect Summary'))
            story.append(Spacer(1, 8))

            total_confirmed = len(confirmed_defects)
            all_defects = inspection.defects or []
            rejected_defects = [d for d in all_defects if d.status == "rejected"]
            total_rejected = len(rejected_defects)

            if total_confirmed > 0:
                b1 = Paragraph(f'<font color="#ffffff"><b>🔴 Severe: {severity_counts.get("severe", 0)}</b></font>', styles['Normal'])
                b2 = Paragraph(f'<font color="#ffffff"><b>🟠 Moderate: {severity_counts.get("moderate", 0)}</b></font>', styles['Normal'])
                b3 = Paragraph(f'<font color="#333333"><b>🟡 Minor: {severity_counts.get("minor", 0)}</b></font>', styles['Normal'])

                badges_table = Table([[b1, b2, b3]], colWidths=[130, 130, 130], rowHeights=[26])
                badges_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#dc3545')),
                    ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#ff8c00')),
                    ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffc107')),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                story.append(badges_table)
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"<b>Total Confirmed Defects:</b> {total_confirmed} &nbsp;|&nbsp; <b>Rejected:</b> {total_rejected}", styles['Normal']))
            else:
                story.append(Paragraph('<font color="#28a745" size=12><b>✅ No defects found — Vehicle passed inspection</b></font>', styles['Normal']))

            story.append(Spacer(1, 14))

            # 4. Detailed Findings Table
            if confirmed_defects:
                story.append(add_section_header('Detailed Findings'))
                story.append(Spacer(1, 8))
                table_data = [["#", "Fault Type", "Severity", "Confidence", "Status", "Notes"]]
                for idx, d in enumerate(confirmed_defects, 1):
                    sev_col = '#dc3545' if d.severity == 'severe' else '#ff8c00' if d.severity == 'moderate' else '#c8a000'
                    table_data.append([
                        str(idx),
                        (d.fault_type or '').replace('-', ' ').title(),
                        Paragraph(f'<font color="{sev_col}"><b>{(d.severity or "Moderate").capitalize()}</b></font>', styles['Normal']),
                        f"{round((d.confidence or 0) * 100)}%",
                        (d.status or '').capitalize(),
                        d.notes or "—"
                    ])
                d_table = Table(table_data, colWidths=[25, 120, 80, 75, 70, 170])
                d_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a3e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                ]))
                story.append(d_table)

                # Defect photos grid
                story.append(Spacer(1, 14))
                story.append(add_section_header('Defect Photos'))
                story.append(Spacer(1, 8))
                for d in confirmed_defects:
                    if d.snapshot_path:
                        path_str = str(d.snapshot_path).replace("\\", "/")
                        if path_str.startswith("uploads/"):
                            clean_rel = path_str[len("uploads/"):]
                        elif path_str.startswith("/uploads/"):
                            clean_rel = path_str[len("/uploads/"):]
                        else:
                            clean_rel = path_str
                        full_img_p = settings.UPLOADS_DIR.parent / "uploads" / clean_rel
                        if not full_img_p.exists():
                            full_img_p = settings.UPLOADS_DIR / clean_rel

                        if full_img_p.exists():
                            try:
                                img = Image(str(full_img_p), width=240, height=140)
                                story.append(img)
                                story.append(Paragraph(
                                    f"<b>{(d.fault_type or '').replace('-', ' ').title()}</b> — Severity: {(d.severity or '').capitalize()} | Confidence: {round((d.confidence or 0)*100)}%",
                                    styles['Normal']
                                ))
                                story.append(Spacer(1, 8))
                            except Exception as img_err:
                                print(f"[ReportLab] Error loading image {full_img_p}: {img_err}")

            if inspection.notes:
                story.append(Spacer(1, 14))
                story.append(add_section_header('Inspector Notes'))
                story.append(Spacer(1, 6))
                story.append(Paragraph(inspection.notes, styles['Normal']))

            story.append(Spacer(1, 20))
            gen_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            footer_style = ParagraphStyle(
                'DocFooter',
                parent=styles['Normal'],
                fontSize=8,
                leading=11,
                textColor=colors.HexColor('#888888'),
                alignment=1,  # Center alignment
            )
            story.append(Paragraph(f"Report generated by {settings.COMPANY_NAME} on {gen_time}<br/>This report is auto-generated and is for informational purposes only.", footer_style))

            doc.build(story)
            return pdf_path.exists() and pdf_path.stat().st_size > 1024
        except Exception as e:
            print(f"[ReportService] ReportLab rendering failed: {e}")
            return False

    async def send_email(
        self,
        recipients: list[str],
        inspection: Inspection,
        pdf_path: Path,
        note: str | None = None,
        sender_email: str | None = None,
        sender_password: str | None = None,
    ) -> dict:
        """Send the report PDF as an email attachment."""
        # Resolve credentials
        smtp_user = sender_email or settings.SMTP_USER
        smtp_password = sender_password or settings.SMTP_PASSWORD

        # Check if placeholders or empty
        is_placeholder = (
            not smtp_user
            or not smtp_password
            or "your-email@gmail.com" in smtp_user
            or "your-app-password" in smtp_password
        )

        vehicle = inspection.vehicle
        vehicle_name = f"{vehicle.make} {vehicle.model}" if vehicle else "Unknown Vehicle"

        # Email body
        body_text = f"""Dear Sir/Madam,

Please find attached the vehicle inspection report for:

Vehicle: {vehicle_name}
License Plate: {vehicle.license_plate or 'N/A'}
Inspection Date: {inspection.started_at.strftime('%Y-%m-%d') if inspection.started_at else 'N/A'}
Inspector: {inspection.inspector.name if inspection.inspector else 'N/A'}
"""
        if note:
            body_text += f"\nAdditional Note: {note}\n"

        body_text += f"""
This report was generated by {settings.COMPANY_NAME}.

Best regards,
{settings.COMPANY_NAME}
{settings.COMPANY_TAGLINE}
"""

        if not HAS_SMTP or is_placeholder:
            # Fallback to local simulation
            sent_emails_dir = settings.REPORTS_DIR / "sent_emails"
            sent_emails_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sim_file = sent_emails_dir / f"simulated_email_{timestamp}_{inspection.id}.txt"
            
            sim_content = f"--- SIMULATED EMAIL ---\n"
            sim_content += f"From: {smtp_user or 'no-reply@autoscan.pro'}\n"
            sim_content += f"To: {', '.join(recipients)}\n"
            sim_content += f"Subject: Vehicle Inspection Report — {vehicle_name}\n"
            sim_content += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            sim_content += f"Attachment: {pdf_path.name if pdf_path.exists() else 'None'}\n"
            sim_content += f"-----------------------\n\n"
            sim_content += body_text
            
            sim_file.write_text(sim_content, encoding="utf-8")
            
            # Also copy the PDF there for complete simulation
            if pdf_path.exists():
                import shutil
                pdf_copy = sent_emails_dir / f"simulated_attachment_{timestamp}_{pdf_path.name}"
                shutil.copy2(pdf_path, pdf_copy)

            print(f"[INFO] SMTP credentials missing/placeholder or aiosmtplib not installed. "
                  f"Saved simulated email to {sim_file}")
            
            return {
                "success": True,
                "method": "simulated",
                "saved_path": str(sim_file)
            }

        # Otherwise build MIME message and send via SMTP
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"Vehicle Inspection Report — {vehicle_name}"
        msg.attach(MIMEText(body_text, "plain"))

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

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=smtp_user,
                password=smtp_password,
                start_tls=True,
            )
            return {
                "success": True,
                "method": "smtp"
            }
        except Exception as e:
            print(f"[ERROR] SMTP send failed: {str(e)}")
            raise e
