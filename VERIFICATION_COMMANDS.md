# Verification Commands

## Prerequisites
1. Start all services:
   - API Gateway: `cd services/api-gateway && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - Application Service: `cd services/application-service && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002`
   - Frontend: `cd frontend && npm run dev`

2. Get an auth token (if needed for protected endpoints):
   ```bash
   # Login and get token from browser localStorage or API response
   ```

## Health Checks

### Gateway Health (Public)
```bash
curl -i http://localhost:8000/health
```
Expected: `200 OK` with JSON showing gateway and services status

### Application Service Health (Direct)
```bash
curl -i http://localhost:8002/health
```
Expected: `200 OK` with `{"status": "ok"}`

## Endpoints (Requires Auth Token)

### Get Applications (via Gateway)
```bash
# Replace YOUR_TOKEN with actual JWT token
curl -i -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/applications
```
Expected: `200 OK` with JSON array of applications (may be empty `[]`)

### Get Applications (Direct - for testing)
```bash
curl -i http://localhost:8002/applications/
```
Expected: `200 OK` with JSON array (may be empty `[]`)

### Get Metrics (via Gateway)
```bash
curl -i -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/metrics
```
Expected: `200 OK` with JSON metrics object

### Get Metrics (Direct - for testing)
```bash
curl -i http://localhost:8002/metrics/
```
Expected: `200 OK` with JSON metrics object

## CORS Testing (from Browser Console)

Open browser DevTools Console at `http://localhost:5173`:

```javascript
// Test CORS - should NOT show CORS error
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);

// Test with auth (replace YOUR_TOKEN)
fetch('http://localhost:8000/applications', {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
})
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);
```

## Checklist

- [ ] `/health` returns 200 OK
- [ ] `/applications` (via gateway) returns 200 OK (not 500, not redirect)
- [ ] `/metrics` (via gateway) returns 200 OK (not 404)
- [ ] No CORS errors in browser console
- [ ] No redirects in Network tab (status should be 200, not 301/302/307/308)
- [ ] Frontend dashboard loads without "Network Error"
- [ ] All requests go to `localhost:8000` (gateway), NOT `localhost:8002` directly

## Troubleshooting

### If `/applications` returns 500:
1. Check application-service logs for the actual error
2. Verify database is connected: Check `DATABASE_URL` in `.env`
3. Verify tables exist: Check if schema is initialized

### If CORS errors persist:
1. Check browser console for exact error message
2. Verify `CORS_ORIGINS` in gateway config includes `http://localhost:5173`
3. Clear browser cache and hard refresh (Ctrl+Shift+R)

### If redirects occur:
1. Check Network tab - status should be 200, not 301/302/307/308
2. Verify `redirect_slashes=False` in FastAPI app config
3. Check that routes accept both `/path` and `/path/`
