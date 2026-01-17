# Frontend Service

**Port:** `3000`  
**Base URL:** `http://localhost:3000`  
**Service Name:** `frontend`

The Frontend Service is a React SPA served by Nginx. It provides the user interface for the JobPlusAI dashboard.

---

## Endpoints

### Health Check

#### `GET /health`

Returns the health status of the Frontend Service.

**Authentication:** None

**Response:**
```json
{
  "status": "ok",
  "service": "frontend",
  "static": true
}
```

**Example:**
```bash
curl http://localhost:3000/health
```

**Notes:**
- This is a static response (no dynamic checks).
- The frontend is a single-page application (SPA).

---

## Application Routes

The frontend is a React SPA with the following routes:

### Public Routes

- `/` - Redirects to `/dashboard` if authenticated, otherwise `/login`
- `/login` - Login page (Google OAuth or Guest Mode)

### Protected Routes (Require Authentication)

- `/dashboard` - Main dashboard with statistics and charts
- `/applications` - Applications list with filtering
- `/resumes` - Resume management and missing confirmations
- `/export` - Data export page
- `/settings` - User settings and logout

---

## API Proxy

The frontend proxies API requests to the API Gateway:

- `/api/*` → `http://api-gateway:8000/api/*`

**Example:**
```bash
# Frontend request
GET http://localhost:3000/api/health

# Proxied to
GET http://api-gateway:8000/api/health
```

---

## Guest Mode

The frontend supports a temporary Guest Mode for UI testing without backend authentication.

**Configuration:**
- Controlled by `src/config/features.js`: `GUEST_MODE_ENABLED`
- When enabled, users can click "Continue as Guest" on the login page.
- Guest users see mock data and cannot access Gmail sync.

**To disable:**
1. Set `GUEST_MODE_ENABLED: false` in `src/config/features.js`
2. Remove guest-related code (marked with `🚨 TEMPORARY GUEST MODE`)

---

## Build Configuration

**Build Args:**
- `VITE_API_URL` - API Gateway URL (default: `http://localhost:8000`)

**Build Command:**
```bash
npm run build
```

**Output:**
- Static files in `/app/dist`
- Served by Nginx at `/usr/share/nginx/html`

---

## Nginx Configuration

The frontend uses Nginx with:
- SPA fallback (`try_files $uri $uri/ /index.html`)
- Gzip compression
- Security headers
- API proxy to API Gateway
- Static asset caching (1 year)

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `VITE_API_URL` | API Gateway URL | No | `http://localhost:8000` |

---

## Notes

- The frontend is a static build (no server-side rendering).
- All API calls go through the API Gateway.
- Authentication is handled via JWT tokens stored in memory/sessionStorage.
- Guest Mode is temporary and should be removed after backend stabilization.

---

## Development

**Local Development:**
```bash
cd frontend
npm install
npm run dev
```

**Production Build:**
```bash
docker-compose build frontend
```

---

## Error Handling

- API errors are displayed in error banners.
- Network failures show user-friendly messages.
- Guest Mode prevents API calls and shows mock data.
