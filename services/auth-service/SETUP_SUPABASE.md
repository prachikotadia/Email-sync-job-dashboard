# Supabase Database Setup Guide

## Current Configuration

Your auth-service is now configured to use Supabase PostgreSQL database.

## Connection Details

The connection URL format is:
```
postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

## Getting Your Supabase Connection String

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **Database**
3. Find the **Connection string** section
4. Select **URI** format
5. Copy the connection string

## Important: URL Encoding

If your password contains special characters, they must be URL-encoded:

| Character | Encoded |
|-----------|---------|
| `%` | `%25` |
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `#` | `%23` |
| `?` | `%3F` |
| `&` | `%26` |
| ` ` (space) | `%20` |

### Quick Encoding Helper

You can encode your password using Python:

```python
from urllib.parse import quote_plus

password = "your-password-with-special-chars%"
encoded = quote_plus(password)
print(f"Encoded: {encoded}")

# Use in connection string:
# postgresql://postgres:{encoded}@host:port/db
```

Or use this PowerShell command:
```powershell
cd services\auth-service
.\venv\Scripts\python.exe -c "from urllib.parse import quote_plus; print(quote_plus('YOUR_PASSWORD'))"
```

## Updating .env File

Edit `services/auth-service/.env`:

```env
AUTH_DATABASE_URL=postgresql://postgres:ENCODED_PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

**Critical:** The entire URL must be on a **single line** with no line breaks!

## Verifying Connection

Test the connection:

```powershell
cd services\auth-service
.\venv\Scripts\Activate.ps1
python -c "from app.db.session import init_db; init_db(); print('✅ Connection successful!')"
```

## Database Tables

The service automatically creates these tables on startup:

1. **users** - User accounts with email, password hash, and role
2. **refresh_tokens** - Refresh token storage with expiration and revocation

## Troubleshooting

### Connection Failed

**Error:** `could not connect to server`

**Solutions:**
- Verify Supabase project is active
- Check the host URL is correct
- Ensure your IP is not blocked (check Supabase network settings)
- Verify port 5432 is accessible

### Authentication Failed

**Error:** `password authentication failed`

**Solutions:**
- Verify password is correct
- Ensure password is URL-encoded if it contains special characters
- Check username is `postgres` (default for Supabase)

### Invalid URL Format

**Error:** `ValueError: invalid literal for int()`

**Solutions:**
- Ensure URL is on a single line (no line breaks)
- Check password is properly URL-encoded
- Verify URL format: `postgresql://user:password@host:port/database`

### Module Not Found

**Error:** `ModuleNotFoundError: No module named 'psycopg2'`

**Solution:**
```bash
pip install psycopg2-binary
```

This should already be in `requirements.txt` and installed automatically.

## Security Best Practices

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Use environment variables in production** - Don't hardcode credentials
3. **Rotate passwords regularly** - Update Supabase password periodically
4. **Use connection pooling** - Already configured with `pool_pre_ping=True`
5. **Enable SSL** - Supabase uses SSL by default in production

## Current Status

✅ **Supabase connection configured**
✅ **Password properly URL-encoded** (`%` → `%25`)
✅ **Database tables auto-created on startup**
✅ **Connection tested and working**

You can now start the auth-service and it will connect to Supabase automatically!
