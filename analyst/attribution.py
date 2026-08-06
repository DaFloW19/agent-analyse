"""
attribution.py
Attribution des leads par source (campagne, ad set, asset).
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(current_dir, '.env'))

from datetime import datetime, timedelta
from data_pull import get_all_kpi_data
from common.metrics import cpl


def get_utc_now():
    try:
        from datetime import timezone
        return datetime.now(timezone.UTC)
    except AttributeError:
        return datetime.utcnow()


def get_attribution_breakdown(client_id: str, start_date: str, end_date: str):
    """
    Retourne la répartition des leads par source.
    Pour l'instant, données simulées - à remplacer par de vraies données plus tard.
    """
    # Simulation de données d'attribution
    return {
        "campaigns": {
            "Campagne Meta - Retargeting": {"leads": 45, "spend": 850.50},
            "Campagne Google - Search": {"leads": 32, "spend": 620.00},
            "Campagne Meta - Prospection": {"leads": 28, "spend": 410.25},
            "Campagne Google - Display": {"leads": 15, "spend": 250.00},
        },
        "ad_sets": {
            "Ad Set - Lookalike": {"leads": 38, "spend": 680.00},
            "Ad Set - Intérêts": {"leads": 22, "spend": 420.50},
            "Ad Set - Retargeting 30j": {"leads": 25, "spend": 430.25},
            "Ad Set - Broad": {"leads": 35, "spend": 600.00},
        },
        "assets": {
            "Asset Vidéo V1": {"leads": 32, "spend": 550.00},
            "Asset Image V2": {"leads": 28, "spend": 480.00},
            "Asset Carrousel": {"leads": 20, "spend": 380.00},
            "Asset Vidéo V2": {"leads": 40, "spend": 720.50},
        }
    }


def get_top_performers(attribution_data):
    """
    Identifie le meilleur et le moins bon performeur pour chaque niveau.
    
    Args:
        attribution_data: Dictionnaire avec les données d'attribution
    
    Returns:
        dict: Meilleur et pire performeur par niveau
    """
    results = {}
    
    for level, items in attribution_data.items():
        best = None
        worst = None
        best_cpl = float('inf')
        worst_cpl = 0
        
        for name, data in items.items():
            if data["spend"] > 0 and data["leads"] > 0:
                current_cpl = data["spend"] / data["leads"]
                if current_cpl < best_cpl:
                    best_cpl = current_cpl
                    best = (name, current_cpl, data["leads"], data["spend"])
                if current_cpl > worst_cpl:
                    worst_cpl = current_cpl
                    worst = (name, current_cpl, data["leads"], data["spend"])
        
        results[level] = {
            "best": best,
            "worst": worst
        }
    
    return results


def format_attribution_report(attribution_data, top_performers):
    """Formate un rapport d'attribution lisible."""
    report = "📊 *Rapport d'attribution par source*\n\n"
    
    for level, items in attribution_data.items():
        report += f"┌─── *{level.capitalize()}* ───\n"
        
        for name, data in items.items():
            if data["spend"] > 0 and data["leads"] > 0:
                cpl_val = data["spend"] / data["leads"]
                report += f"│ {name}: {data['leads']} leads | {data['spend']:.2f}€ | CPL: {cpl_val:.2f}€\n"
            else:
                report += f"│ {name}: pas de données\n"
        
        # Ajouter les meilleurs et pires performers
        top = top_performers.get(level, {})
        if top.get("best"):
            best_name, best_cpl, best_leads, best_spend = top["best"]
            report += f"└── 🏆 Meilleur: {best_name} (CPL: {best_cpl:.2f}€, {best_leads} leads)\n"
        if top.get("worst"):
            worst_name, worst_cpl, worst_leads, worst_spend = top["worst"]
            report += f"    📉 Pire: {worst_name} (CPL: {worst_cpl:.2f}€, {worst_leads} leads)\n"
        report += "\n"
    
    return report


if __name__ == "__main__":
    now = get_utc_now()
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    data = get_attribution_breakdown("client_test_123", start_date, end_date)
    top = get_top_performers(data)
    report = format_attribution_report(data, top)
    print(report)