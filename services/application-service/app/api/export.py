from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.repositories import ApplicationRepository
from app.services.excel_generator import ExcelGenerator
from app.db.supabase import get_db
from datetime import datetime

router = APIRouter()

@router.get("/excel")
def export_excel(db: Session = Depends(get_db)):
    repo = ApplicationRepository(db)
    apps = repo.list_applications(limit=10000)
    # ...
    
    excel_file = ExcelGenerator.generate(apps)
    
    filename = f"applications_export_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    
    return Response(
        content=excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
