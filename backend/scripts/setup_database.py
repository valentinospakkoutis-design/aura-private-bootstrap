"""
Database setup script
Creates database tables if they don't exist
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.connection import init_db, check_db_connection

def main():
    print("[*] AURA Database Setup")
    print("=" * 50)
    
    # Check connection
    print("[*] Checking database connection...")
    if not check_db_connection():
        print("[-] Database connection failed!")
        print("[!] Please ensure PostgreSQL is running and DATABASE_URL is set correctly")
        print("[!] Default: postgresql://postgres:postgres@localhost:5432/aura_db")
        return False
    
    print("[+] Database connection successful")
    
    # Initialize tables
    print("[*] Initializing database tables...")
    try:
        init_db()
        print("[+] Database tables created successfully!")
        return True
    except Exception as e:
        print(f"[-] Error creating tables: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

