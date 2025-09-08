import os
import json
import pandas as pd
from google.cloud import firestore
import streamlit as st
from datetime import datetime

# 🔐 Load credentials from Streamlit secrets
@st.cache_resource
def get_firestore_client():
    try:
        raw = st.secrets.get("gcp_service_account")
        service_account_info = json.loads(raw) if isinstance(raw, str) else dict(raw)
        key_path = "/tmp/service_account.json"
        with open(key_path, "w") as f:
            json.dump(service_account_info, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        return firestore.Client()
    except Exception as e:
        st.error(f"❌ Failed to initialize Firestore client: {e}")
        raise

# 🔌 Initialize Firestore client
db = get_firestore_client()

# 📡 Get list of stations that have at least one reading
@st.cache_data(ttl=60)
def get_station_list():
    try:
        station_ids_with_data = []
        for station_ref in db.collection("stations").list_documents(page_size=1000):
            readings_q = (
                db.collection("stations")
                  .document(station_ref.id)
                  .collection("readings")
                  .limit(1)
            )
            # Use stream() (no retry arg under the hood)
            has_one = next(iter(readings_q.stream()), None) is not None
            if has_one:
                station_ids_with_data.append(station_ref.id)

        return sorted(station_ids_with_data)
    except Exception as e:
        st.error(f"❌ Error loading station list: {e}")
        return []

# 📥 Load data for a specific station, sorted by timestamp
@st.cache_data(ttl=60)
def load_station_data(station_id: str) -> pd.DataFrame:
    try:
        readings_q = (
            db.collection("stations")
              .document(station_id)
              .collection("readings")
              .order_by("timestamp", direction=firestore.Query.ASCENDING)
        )

        records = []
        for doc in readings_q.stream():  # stream() is safe here
            data = doc.to_dict() or {}
            data["id"] = doc.id

            ts = data.get("timestamp")
            # Firestore usually returns a timezone-aware datetime already.
            if isinstance(ts, datetime):
                data["timestamp"] = ts
            else:
                # Fallback: try to coerce anything else
                data["timestamp"] = pd.to_datetime(ts, utc=True, errors="coerce")

            records.append(data)

        df = pd.DataFrame(records)
        if df.empty:
            st.info(f"ℹ️ No records found for station `{station_id}`.")
            return df

        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        return df

    except Exception as e:
        st.error(f"❌ Failed to load data for station `{station_id}`: {e}")
        return pd.DataFrame()
