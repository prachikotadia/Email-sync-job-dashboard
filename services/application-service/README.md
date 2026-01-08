# Application Service

The Source of Truth for job applications.

## Purpose
Manages company/role deduplication, application lifecycle status, and resume mappings.

## Database Schema
- **Companies**: Unique list of companies (normalized)
- **Roles**: Job titles per company
- **Applications**: Link between company/role + current status + meta logic (ghosted?)

## Local Dev

1. Install dependencies:
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

2. Run service:
   \`\`\`bash
   uvicorn app.main:app --reload --port 8002
   \`\`\`

## API Endpoints

- \`GET /health\`: Service check
- \`POST /ingest/processed-emails\`: Main input from Email AI Service
- \`GET /applications\`: List/filter applications
- \`GET /export/excel\`: Download Excel dump
