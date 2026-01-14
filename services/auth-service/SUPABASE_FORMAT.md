# Supabase Database Hostname Format

## Why "db." prefix?

The `db.` prefix in `db.svlayowjwzbtbpcsjvpe.supabase.co` is **correct** and is Supabase's standard format for direct PostgreSQL database connections.

### Supabase Hostname Formats

1. **Direct Connection (Port 5432)**
   ```
   db.{project-ref}.supabase.co
   ```
   - Example: `db.svlayowjwzbtbpcsjvpe.supabase.co`
   - Used for: Direct PostgreSQL connections
   - Port: `5432`

2. **Connection Pooler (Port 6543)**
   ```
   aws-{X}-{region}.pooler.supabase.com
   ```
   - Example: `aws-0-us-east-1.pooler.supabase.com`
   - Used for: Connection pooling (better for serverless/server applications)
   - Port: `6543`
   - Add `?pgbouncer=true` to connection string

### Your Current Connection String

```
postgresql://postgres:PASSWORD@db.svlayowjwzbtbpcsjvpe.supabase.co:5432/postgres
```

This is the **correct format** for direct connections.

### If Direct Connection Fails

If you get DNS resolution errors with `db.xxx.supabase.co`, try the **Connection Pooler** instead:

1. Go to Supabase Dashboard → Settings → Database
2. Find **Connection Pooling** section
3. Select **Transaction** mode
4. Copy the connection string (it will have a different hostname format)
5. Update your `.env`:
   ```
   AUTH_DATABASE_URL=postgresql://postgres:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true
   ```

### Why DNS Might Fail

Even though the format is correct, DNS resolution can fail if:
- Supabase project is **paused** (most common)
- Network/DNS issues
- Firewall blocking port 5432

### Quick Check

To verify your Supabase project is active:
1. Go to https://supabase.com/dashboard
2. Check if project shows "Paused"
3. If paused, click "Restore"

The `db.` prefix is **not a typo** - it's Supabase's standard naming convention! ✅
