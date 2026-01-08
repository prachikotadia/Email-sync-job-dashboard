from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.repository import ApplicationRepository
from app.services.excel_generator import ExcelGenerator
from app.utils.db_session import get_db
from datetime import datetime

router = APIRouter()

@router.get("/excel")
def export_excel(db: Session = Depends(get_db)):
    repo = ApplicationRepository(db)
    apps = repo.get_applications(limit=10000) # Reasonable export limit
    
    excel_file = ExcelGenerator.generate(apps)
    
    filename = f"applications_export_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    
    return Response(
        content=excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
