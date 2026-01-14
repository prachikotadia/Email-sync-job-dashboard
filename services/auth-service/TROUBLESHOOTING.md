# Supabase Connection Troubleshooting

## Error: "could not translate host name"

This error means your computer cannot resolve the Supabase database hostname to an IP address.

## Common Causes & Solutions

### 1. **Supabase Project is Paused** (Most Common)

Free tier Supabase projects automatically pause after 7 days of inactivity.

**Solution:**
1. Go to https://supabase.com/dashboard
2. Find your project
3. If it shows "Paused", click **"Restore"** or **"Resume"**
4. Wait 1-2 minutes for the database to come online
5. Try connecting again

### 2. **Incorrect Connection String**

**Verify your connection string:**
1. Go to Supabase Dashboard → Your Project
2. Click **Settings** → **Database**
3. Scroll to **Connection string** section
4. Select **URI** format (not Session mode)
5. Copy the entire string
6. Make sure special characters in password are URL-encoded:
   - `%` → `%25`
   - `@` → `%40`
   - `:` → `%3A`
   - `/` → `%2F`

**Example:**
```
postgresql://postgres:your%25password@db.xxxxx.supabase.co:5432/postgres
```

### 3. **Use Connection Pooler (Alternative)**

If direct connection fails, try the connection pooler:

1. In Supabase Dashboard → Settings → Database
2. Find **Connection Pooling** section
3. Use the **Transaction** mode connection string
4. It uses port **6543** instead of 5432
5. Update your `.env`:
   ```
   AUTH_DATABASE_URL=postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:6543/postgres?pgbouncer=true
   ```

### 4. **Network/DNS Issues**

**Windows:**
```powershell
# Flush DNS cache
ipconfig /flushdns

# Test DNS resolution
nslookup db.svlayowjwzbtbpcsjvpe.supabase.co

# Test connectivity
Test-NetConnection -ComputerName db.svlayowjwzbtbpcsjvpe.supabase.co -Port 5432
```

**If DNS fails:**
- Check your internet connection
- Try a different network (mobile hotspot)
- Check if corporate firewall blocks Supabase
- Try using a VPN

### 5. **Firewall Blocking Port 5432**

Some networks/firewalls block PostgreSQL port 5432.

**Solution:**
- Use Connection Pooler (port 6543) - see solution #3
- Or configure firewall to allow port 5432

### 6. **Temporary Workaround: Use SQLite**

For local development, you can use SQLite temporarily:

1. Edit `services/auth-service/.env`:
   ```
   AUTH_DATABASE_URL=sqlite:///./auth.db
   ```

2. Restart the auth-service

**Note:** SQLite is for local dev only. For production, use PostgreSQL/Supabase.

## Testing Your Connection

Test the connection directly:

```powershell
cd services\auth-service
.\venv\Scripts\Activate.ps1
python -c "from app.db.session import init_db; init_db(); print('✅ Connection successful!')"
```

## Getting Help

If none of these solutions work:
1. Check Supabase status: https://status.supabase.com
2. Check Supabase Discord/Community for outages
3. Verify your Supabase project settings
4. Try creating a new Supabase project and migrating
