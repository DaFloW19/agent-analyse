import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from data_pull import get_all_kpi_data
from common.metrics import get_all_metrics

now = datetime.utcnow()
end = now.strftime("%Y-%m-%d")
start = (now - timedelta(days=7)).strftime("%Y-%m-%d")

data = get_all_kpi_data('client_test_123', start, end)
metrics = get_all_metrics(data)

print("📊 KPIs calculés :")
for name, kpi in metrics.items():
    if kpi['value'] is not None:
        print(f"  {name}: {kpi['value']:.2f}")
    else:
        print(f"  {name}: Pas de données")