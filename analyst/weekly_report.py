"""
weekly_report.py
Génère un rapport d'optimisation hebdomadaire avec des actions concrètes.
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
from common.metrics import cpl, cpql, stage_conversion_rate, response_rate
from llm_analyst import generate_optimization_recommendation


def get_utc_now():
    try:
        from datetime import timezone
        return datetime.now(timezone.UTC)
    except AttributeError:
        return datetime.utcnow()


def generate_weekly_optimization(client_id: str) -> str:
    """Génère un rapport d'optimisation avec des actions concrètes."""
    now = get_utc_now()
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    data = get_all_kpi_data(client_id, start_date, end_date)
    
    cpl_result = cpl(data["ad_spend"], data["submissions"])
    cpql_result = cpql(data["ad_spend"], data["leads_ge_61"])
    
    # Calcul des taux supplémentaires
    stage_conv = stage_conversion_rate(data["prev_stage_leads"], data["curr_stage_leads"])
    resp_rate = response_rate(data["replied_first_contacts"], data["total_first_contacts"])
    
    recommendations = []
    
    if cpl_result["value"] is not None and cpl_result["value"] > 100:
        recommendations.append("🔴 Réduire le budget sur les campagnes à faible performance (CPL > 100€)")
    
    if data["submissions"] < 50:
        recommendations.append("🔵 Augmenter le budget des campagnes à fort CTR pour générer plus de leads")
    
    if data["appointments"] < 5:
        recommendations.append("🟠 Améliorer le processus de prise de rendez-vous")
    
    if not recommendations:
        recommendations.append("✅ Aucune action urgente recommandée cette semaine.")
    
    report = f"📋 *Rapport d'optimisation - Semaine du {start_date}*\n\n"
    report += f"💰 Dépenses totales : {data['ad_spend']:.2f} €\n"
    report += f"📥 Leads générés : {data['submissions']}\n"
    if cpl_result["value"] is not None:
        report += f"📊 CPL moyen : {cpl_result['value']:.2f} €\n"
    if cpql_result["value"] is not None:
        report += f"🎯 CPQL : {cpql_result['value']:.2f} €\n"
    report += "\n---\n*Recommandations :*\n"
    report += "\n".join(f"- {r}" for r in recommendations)
    
    # Ajouter une recommandation LLM
    metrics_data = {
        "cpl": {"value": cpl_result["value"]},
        "cpql": {"value": cpql_result["value"]},
        "stage_conversion": {"value": stage_conv["value"]},
        "response_rate": {"value": resp_rate["value"]}
    }
    llm_recommendation = generate_optimization_recommendation(metrics_data)
    if llm_recommendation:
        report += f"\n🤖 *Recommandation LLM* : {llm_recommendation}\n"
    
    return report


if __name__ == "__main__":
    print(generate_weekly_optimization("client_test_123"))