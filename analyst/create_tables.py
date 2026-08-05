import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # Cela chargera .env dans le dossier courant (analyst)
DATABASE_URL = os.getenv("DATABASE_URL")

sql = """
CREATE TABLE IF NOT EXISTS leads (
    lead_id UUID PRIMARY KEY,
    client_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    source TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    industry_segment TEXT,
    qualification_score INTEGER,
    lead_stage TEXT DEFAULT 'new',
    last_action TEXT,
    last_action_at TIMESTAMPTZ,
    messages_sent INTEGER DEFAULT 0,
    meeting_date TIMESTAMPTZ,
    notes JSONB DEFAULT '[]'::jsonb,
    contract_value DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS ad_spend (
    id SERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    campaign_id TEXT,
    platform TEXT,
    spend DECIMAL(10,2),
    date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    lead_id UUID,
    booked_at TIMESTAMPTZ,
    showed_up BOOLEAN DEFAULT NULL,
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
);
"""

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("✅ Tables Phase B créées avec succès !")
except Exception as e:
    print(f"❌ Erreur : {e}")
finally:
    cur.close()
    conn.close()