#!/usr/bin/env python3
"""
Test Supabase database connection and diagnose issues.
"""
import sys
import os
from urllib.parse import urlparse, unquote
import socket

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import get_settings

def test_dns(hostname):
    """Test DNS resolution."""
    print(f"\n[TEST] Testing DNS resolution for: {hostname}")
    try:
        # Try IPv4 first
        try:
            ipv4 = socket.gethostbyname(hostname)
            print(f"   [OK] IPv4: {ipv4}")
        except socket.gaierror:
            print(f"   [FAIL] IPv4: Failed")
        
        # Try all addresses
        try:
            addrs = socket.getaddrinfo(hostname, 5432, socket.AF_UNSPEC, socket.SOCK_STREAM)
            print(f"   [INFO] Found {len(addrs)} address(es):")
            for addr in addrs:
                print(f"      - {addr[4][0]} ({'IPv4' if addr[0] == socket.AF_INET else 'IPv6'})")
        except socket.gaierror as e:
            print(f"   [FAIL] DNS resolution failed: {e}")
            return False
        return True
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False

def test_port(hostname, port):
    """Test if port is reachable."""
    print(f"\n[TEST] Testing port {port} connectivity...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((hostname, port))
        sock.close()
        if result == 0:
            print(f"   [OK] Port {port} is reachable")
            return True
        else:
            print(f"   [FAIL] Port {port} is NOT reachable (connection refused)")
            return False
    except socket.gaierror:
        print(f"   [FAIL] Cannot resolve hostname")
        return False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False

def test_connection():
    """Test database connection."""
    print("=" * 60)
    print("SUPABASE CONNECTION DIAGNOSTIC")
    print("=" * 60)
    
    try:
        settings = get_settings()
        db_url = settings.AUTH_DATABASE_URL.strip()
        
        if not db_url:
            print("[FAIL] AUTH_DATABASE_URL is not set in .env file")
            return
        
        print(f"\n[INFO] Connection String (masked):")
        parsed = urlparse(db_url)
        if parsed.password:
            masked = db_url.replace(parsed.password, "***")
            print(f"   {masked}")
        else:
            print(f"   {db_url}")
        
        # Extract hostname
        hostname = parsed.hostname
        port = parsed.port or 5432
        
        if not hostname:
            print("[FAIL] Invalid connection string: no hostname found")
            return
        
        # Test DNS
        dns_ok = test_dns(hostname)
        
        # Test port
        if dns_ok:
            port_ok = test_port(hostname, port)
        else:
            port_ok = False
        
        # Test actual database connection
        print(f"\n[TEST] Testing database connection...")
        try:
            from app.db.session import init_db
            init_db()
            print("   [OK] Database connection successful!")
            print("\n" + "=" * 60)
            print("[SUCCESS] ALL TESTS PASSED - Connection is working!")
            print("=" * 60)
        except Exception as db_error:
            error_str = str(db_error).lower()
            print(f"   [FAIL] Database connection failed: {db_error}")
            
            if 'could not translate host name' in error_str or 'name or service not known' in error_str:
                print("\n" + "=" * 60)
                print("[ERROR] DNS RESOLUTION FAILED")
                print("=" * 60)
                print("\n[TIP] Most likely causes:")
                print("   1. Supabase project is PAUSED (free tier pauses after inactivity)")
                print("      -> Go to https://supabase.com/dashboard")
                print("      -> Check if project shows 'Paused' status")
                print("      -> Click 'Restore' to reactivate")
                print("\n   2. Network/DNS issue")
                print("      -> Try: ipconfig /flushdns")
                print("      -> Check internet connection")
                print("      -> Try different network (mobile hotspot)")
                print("\n   3. Firewall blocking connection")
                print("      -> Try Connection Pooler (port 6543)")
                print("      -> See TROUBLESHOOTING.md for details")
            else:
                print("\n" + "=" * 60)
                print("[ERROR] CONNECTION ERROR")
                print("=" * 60)
                print(f"\nError: {db_error}")
                print("\nSee TROUBLESHOOTING.md for solutions")
            
    except Exception as e:
        print(f"\n[ERROR] Error running diagnostic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
