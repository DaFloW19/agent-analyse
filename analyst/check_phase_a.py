import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

print("🔍 Vérification Phase A - Base agent_system_db")
print("-" * 40)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Vérifier que la table existe
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'agent_logs'
    """)
    if cur.fetchone()[0] == 1:
        print("✅ Table 'agent_logs' existe")
    else:
        print("❌ Table 'agent_logs' manquante !")
        exit()
    
    # Compter les logs
    cur.execute("""
        SELECT agent_name, COUNT(*) FROM agent_logs 
        GROUP BY agent_name ORDER BY agent_name
    """)
    rows = cur.fetchall()
    
    if rows:
        print("\n📊 Logs par agent :")
        for agent, count in rows:
            print(f"  - {agent}: {count} log(s)")
        total = sum(r[1] for r in rows)
        print(f"\n📈 Total : {total} logs")
        print("\n✅ Phase A validée !")
    else:
        print("\n⚠️ Aucun log trouvé !")
        print("   Exécute : uv run python generate_test_logs.py")
        print("   Puis    : uv run python ingest_logs.py")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erreur : {e}")
    print("   Vérifie que PostgreSQL tourne et que .env est correct")