import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pull import get_db_connection

try:
    conn = get_db_connection()
    print("✅ Connexion réussie !")
    conn.close()
except Exception as e:
    print(f"❌ Erreur : {e}")