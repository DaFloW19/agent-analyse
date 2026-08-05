"""
langfuse_client.py
Initialisation du client Langfuse pour l'observabilité.
"""

import os
from dotenv import load_dotenv

# Charger le .env depuis le dossier courant (analyst/)
load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

print(f"🔑 Public key: {public_key[:15] if public_key else '❌ MANQUANTE'}...")
print(f"🔐 Secret key: {secret_key[:15] if secret_key else '❌ MANQUANTE'}...")
print(f"🌐 Host: {host}")

if not public_key or not secret_key:
    print("❌ Clés Langfuse manquantes ! Vérifie ton fichier .env")
    LANG = None
else:
    try:
        from langfuse import Langfuse
        LANG = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        print("✅ Langfuse initialisé avec succès")
    except ImportError:
        print("⚠️ Langfuse non installé. Exécute: uv add langfuse")
        LANG = None
    except Exception as e:
        print(f"⚠️ Erreur Langfuse: {e}")
        LANG = None

def get_langfuse():
    """Retourne le client Langfuse."""
    return LANG