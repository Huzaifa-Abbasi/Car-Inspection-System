"""
Report routes: generate PDF and send via email.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Inspection, User
from backend.schemas import ReportSendRequest
from backend.services.report_service import ReportService
from backend.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/{inspection_id}/generate")
def generate_report(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a PDF report for the given inspection."""
    inspection = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.vehicle),
            joinedload(Inspection.inspector),
            joinedload(Inspection.defects),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    report_svc = ReportService()
    pdf_path = report_svc.generate_pdf(inspection)

    return {"message": "Report generated", "path": str(pdf_path)}


@router.get("/{inspection_id}/download")
def download_report(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the generated PDF report."""
    report_svc = ReportService()
    pdf_path = report_svc.get_report_path(inspection_id)

    if pdf_path.exists() and pdf_path.stat().st_size < 1024:
        try:
            pdf_path.unlink()
        except Exception:
            pass

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Generate it first.")

    # Fallback to HTML if WeasyPrint is not fully configured on Windows
    from backend.services.report_service import HAS_WEASYPRINT
    if not HAS_WEASYPRINT:
        html_path = pdf_path.with_suffix(".html")
        if html_path.exists():
            return FileResponse(
                path=str(html_path),
                media_type="text/html",
                filename=f"inspection_report_{inspection_id}.html",
            )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"inspection_report_{inspection_id}.pdf",
    )


@router.post("/{inspection_id}/send")
async def send_report(
    inspection_id: str,
    body: ReportSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send the report via email to client and/or manager."""
    inspection = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.vehicle),
            joinedload(Inspection.inspector),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    report_svc = ReportService()
    pdf_path = report_svc.get_report_path(inspection_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=400, detail="Report not generated yet")

    recipients = []
    if body.client_email:
        recipients.append(body.client_email)
    if body.manager_email:
        recipients.append(body.manager_email)

    if not recipients:
        # Fallback to vehicle owner email
        if inspection.vehicle and inspection.vehicle.owner_email:
            recipients.append(inspection.vehicle.owner_email)

    if not recipients:
        raise HTTPException(status_code=400, detail="No email recipients specified")

    try:
        await report_svc.send_email(
            recipients=recipients,
            inspection=inspection,
            pdf_path=pdf_path,
            note=body.note,
        )
        return {"message": f"Report sent to {', '.join(recipients)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
