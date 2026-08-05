import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    print("📋 Tables dans agent_system_db :")
    for t in tables:
        print(f"  - {t}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Erreur : {e}")