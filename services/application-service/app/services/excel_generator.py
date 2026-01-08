import pandas as pd
from app.db.models import Application
from typing import List
import io

class ExcelGenerator:
    @staticmethod
    def generate(applications: List[Application]) -> bytes:
        data = []
        for app in applications:
            data.append({
                "Company": app.company.name.title(),
                "Role": app.role.title,
                "Status": app.status,
                "Applied Count": app.applied_count,
                "Last Updated": app.last_email_date.replace(tzinfo=None) if app.last_email_date else None,
                "Ghosted": "Yes" if app.ghosted else "No",
                "Resume": app.resume.file_name if app.resume else "N/A"
            })
            
        df = pd.read_json(pd.Series(data).to_json(orient='records')) if data else pd.DataFrame()
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Applications')
            
        return output.getvalue()
