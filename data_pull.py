"""
data_pull.py
Lecture des données depuis PostgreSQL pour les métriques.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path

# Charger .env depuis le dossier analyst/
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / 'analyst' / '.env'
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(f"❌ DATABASE_URL non définie. Fichier .env cherché dans : {ENV_PATH}")



def get_db_connection():
    """Retourne une connexion à la base de données."""
    return psycopg2.connect(DATABASE_URL)


def get_ad_spend(client_id: str, start_date: str, end_date: str) -> float:
    """Retourne le total des dépenses publicitaires pour un client sur une période."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(spend), 0) 
        FROM ad_spend 
        WHERE client_id = %s AND date BETWEEN %s AND %s
    """, (client_id, start_date, end_date))
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return float(result)


def get_total_form_submissions(client_id: str, start_date: str, end_date: str) -> int:
    """Compte les leads créés dans la période (tous les leads)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM leads 
        WHERE client_id = %s AND created_at::date BETWEEN %s::date AND %s::date
    """, (client_id, start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_leads_with_score_ge(client_id: str, min_score: int, start_date: str, end_date: str) -> int:
    """Compte les leads avec un score >= min_score sur la période."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM leads 
        WHERE client_id = %s 
        AND qualification_score >= %s
        AND created_at::date BETWEEN %s::date AND %s::date
    """, (client_id, min_score, start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_appointments_booked(client_id: str, start_date: str, end_date: str) -> int:
    """Compte les rendez-vous pris sur la période."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM bookings b
        JOIN leads l ON b.lead_id = l.lead_id
        WHERE l.client_id = %s 
        AND b.booked_at::date BETWEEN %s::date AND %s::date
    """, (client_id, start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_closed_won_value(client_id: str, start_date: str, end_date: str) -> float:
    """Total des valeurs des deals closed_won sur la période."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(contract_value), 0) 
        FROM leads 
        WHERE client_id = %s 
        AND lead_stage = 'closed_won'
        AND created_at::date BETWEEN %s::date AND %s::date
    """, (client_id, start_date, end_date))
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return float(result)


def get_stage_counts(client_id: str, stage: str, start_date: str, end_date: str) -> int:
    """Compte les leads dans une étape donnée sur une période."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM leads 
        WHERE client_id = %s 
        AND lead_stage = %s
        AND created_at::date BETWEEN %s::date AND %s::date
    """, (client_id, stage, start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_all_kpi_data(client_id: str, start_date: str, end_date: str) -> dict:
    """
    Récupère toutes les données nécessaires pour les KPIs en une seule fois.
    """
    ad_spend = get_ad_spend(client_id, start_date, end_date)
    submissions = get_total_form_submissions(client_id, start_date, end_date)
    leads_ge_31 = get_leads_with_score_ge(client_id, 31, start_date, end_date)
    leads_ge_61 = get_leads_with_score_ge(client_id, 61, start_date, end_date)
    appointments = get_appointments_booked(client_id, start_date, end_date)
    closed_value = get_closed_won_value(client_id, start_date, end_date)
    
    # Pour les métriques de conversion
    new_leads = get_stage_counts(client_id, 'new', start_date, end_date)
    mql_leads = get_stage_counts(client_id, 'mql', start_date, end_date)
    
    # Simulé pour l'instant (à remplacer par de vraies données plus tard)
    total_minutes_contact = 120.0
    contacts_count = 8
    replied_first_contacts = 5
    total_first_contacts = 10
    showed_up = 4
    total_meetings = 5
    
    return {
        "ad_spend": ad_spend,
        "submissions": submissions,
        "leads_ge_31": leads_ge_31,
        "leads_ge_61": leads_ge_61,
        "appointments": appointments,
        "closed_won_value": closed_value,
        "prev_stage_leads": new_leads,
        "curr_stage_leads": mql_leads,
        "total_minutes_contact": total_minutes_contact,
        "contacts_count": contacts_count,
        "replied_first_contacts": replied_first_contacts,
        "total_first_contacts": total_first_contacts,
        "showed_up": showed_up,
        "total_meetings": total_meetings
    }