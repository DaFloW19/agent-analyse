"""
anomaly_detector.py
Surveille les taux de conversion et alerte en cas de chute > 50%.
"""

import sys
import os

# Ajouter le chemin du projet pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Charger le fichier .env AVANT d'importer les autres modules
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(current_dir, '.env'))

# Maintenant on peut importer les modules du projet
from datetime import datetime, timedelta
from data_pull import get_all_kpi_data
from common.metrics import stage_conversion_rate

ANOMALY_THRESHOLD_PCT = 50  # 50% de baisse pour déclencher une alerte
MIN_DENOMINATOR = 20        # Volume minimum pour déclencher une alerte


def get_utc_now():
    """Retourne la date/heure UTC actuelle (compatible Python 3.10+)."""
    try:
        # Python 3.11+
        from datetime import timezone
        return datetime.now(timezone.UTC)
    except AttributeError:
        # Python 3.10 et inférieur
        return datetime.utcnow()


def check_anomalies(client_id: str):
    """
    Vérifie les anomalies sur les taux de conversion.
    
    Args:
        client_id: Identifiant du client à analyser.
    
    Returns:
        str ou None: Message d'alerte si anomalie, None sinon.
    """
    try:
        now = get_utc_now()
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        
        prev_end_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        prev_start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        
        # Récupérer les données
        data = get_all_kpi_data(client_id, start_date, end_date)
        prev_data = get_all_kpi_data(client_id, prev_start_date, prev_end_date)
        
        # Vérifier qu'on a bien des données
        if not data or not prev_data:
            print("⚠️ Données insuffisantes pour détecter des anomalies.")
            return None
        
        # Calculer les taux de conversion
        current_rate = stage_conversion_rate(data["prev_stage_leads"], data["curr_stage_leads"])
        prev_rate = stage_conversion_rate(prev_data["prev_stage_leads"], prev_data["curr_stage_leads"])
        
        # Vérifier si on peut faire la comparaison
        if prev_rate["value"] is None or current_rate["value"] is None:
            print("ℹ️ Données insuffisantes pour le taux de conversion.")
            return None
        
        # Vérifier le volume minimum
        if prev_rate["denominator"] < MIN_DENOMINATOR or current_rate["denominator"] < MIN_DENOMINATOR:
            print(f"ℹ️ Volume insuffisant pour détecter une anomalie : "
                  f"précédent={prev_rate['denominator']}, actuel={current_rate['denominator']}")
            return None
        
        # Calculer la chute
        drop = ((prev_rate["value"] - current_rate["value"]) / prev_rate["value"]) * 100
        
        if drop > ANOMALY_THRESHOLD_PCT:
            alert_msg = (
                f"🚨 ANOMALIE : Taux de conversion en chute de {drop:.1f}% !\n"
                f"Taux actuel : {current_rate['value']:.1f}% (basé sur {current_rate['denominator']})\n"
                f"Taux précédent : {prev_rate['value']:.1f}% (basé sur {prev_rate['denominator']})"
            )
            print(alert_msg)
            # TODO: Envoyer sur Telegram
            return alert_msg
        
        print("✅ Aucune anomalie détectée.")
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la détection d'anomalies : {e}")
        return None


if __name__ == "__main__":
    check_anomalies("client_test_123")