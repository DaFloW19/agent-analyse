"""
llm_analyst.py
Module pour l'intégration des appels LLM via OpenRouter (LiteLLM).
"""

import os
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()


def get_llm():
    """Retourne une instance LLM (OpenRouter via LiteLLM) pour l'Analyst."""
    try:
        from litellm import completion
        return completion
    except ImportError:
        print("⚠️ LiteLLM non installé. Exécute: uv add litellm")
        return None


@observe(name="analyst_llm_generation", as_type="generation")
def generate_kpi_explanation(kpi_name: str, value: float, trend: str = "stable") -> str:
    completion = get_llm()
    if not completion:
        return f"{kpi_name} est à {value:.2f} (tendance: {trend})"
    
    try:
        response = completion(
            model=os.getenv("MODEL_NAME", "openrouter/deepseek/deepseek-chat"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un analyste marketing. Explique ce KPI en 1-2 phrases, de manière claire et professionnelle."
                },
                {
                    "role": "user",
                    "content": f"KPI: {kpi_name}, valeur: {value:.2f}, tendance: {trend}. Explique."
                }
            ],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Erreur LLM (explication): {e}")
        return f"{kpi_name} est à {value:.2f} (tendance: {trend})"


@observe(name="analyst_llm_recommendation", as_type="generation")
def generate_optimization_recommendation(kpi_data: dict) -> str:
    completion = get_llm()
    if not completion:
        return "Aucune recommandation automatique disponible."
    
    cpl_val = kpi_data.get('cpl', {}).get('value')
    cpql_val = kpi_data.get('cpql', {}).get('value')
    conv_val = kpi_data.get('stage_conversion', {}).get('value')
    resp_val = kpi_data.get('response_rate', {}).get('value')
    
    prompt = f"""
    Analyse ces KPIs marketing :
    - CPL: {cpl_val if cpl_val is not None else 'N/A'}
    - CPQL: {cpql_val if cpql_val is not None else 'N/A'}
    - Taux de conversion: {conv_val if conv_val is not None else 'N/A'}%
    - Taux de réponse: {resp_val if resp_val is not None else 'N/A'}%
    
    Propose une recommandation concrète (1 phrase) pour améliorer la performance.
    """
    
    try:
        response = completion(
            model=os.getenv("MODEL_NAME", "openrouter/deepseek/deepseek-chat"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            messages=[
                {"role": "system", "content": "Tu es un expert en marketing digital. Donne une recommandation courte et actionnable."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=80
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Erreur LLM (recommandation): {e}")
        return "Vérifier les campagnes à faible performance."