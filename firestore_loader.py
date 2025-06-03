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
        service_account_info = json.loads(st.secrets["gcp_service_account"])
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

# 🔁 Station name mapping (Firestore ID → UI name)
station_name_map = {
    "station_Dewstand@GreenHose_Polytechnic": "station_Dewstand@GreenHouse_Polytechnic"
}
# 🔁 Reverse mapping (UI name → Firestore ID)
reverse_station_name_map = {v: k for k, v in station_name_map.items()}

# 📡 Get list of stations that have at least one reading
@st.cache_data(ttl=60)
def get_station_list():
    try:
        station_docs = db.collection("stations").list_documents()
        station_ids_with_data = []

        for station_doc in station_docs:
            readings_ref = db.collection("stations").document(station_doc.id).collection("readings")
            if readings_ref.limit(1).get():
                display_id = station_name_map.get(station_doc.id, station_doc.id)
                station_ids_with_data.append(display_id)

        return sorted(station_ids_with_data)
    except Exception as e:
        st.error(f"❌ Error loading station list: {e}")
        return []

# 📥 Load data for a specific station, sorted by timestamp
@st.cache_data(ttl=60)
def load_station_data(station_id):
    try:
        firestore_id = reverse_station_name_map.get(station_id, station_id)

        readings_ref = (
            db.collection("stations")
              .document(firestore_id)
              .collection("readings")
              .order_by("timestamp", direction=firestore.Query.ASCENDING)
        )

        records = []
        for doc in readings_ref.stream():
            data = doc.to_dict()
            data["id"] = doc.id

            ts = data.get("timestamp")
            if hasattr(ts, "to_datetime"):
                data["timestamp"] = ts.to_datetime()
            elif isinstance(ts, datetime):
                data["timestamp"] = ts
            else:
                data["timestamp"] = None  # Optional: replace with datetime.utcnow()

            records.append(data)

        df = pd.DataFrame(records)

        if df.empty:
            st.info(f"ℹ️ No records found for station `{station_id}`.")
        else:
            df = df.dropna(subset=["timestamp"])
            df = df.sort_values("timestamp")

        return df

    except Exception as e:
        st.error(f"❌ Failed to load data for station `{station_id}`: {e}")
        return pd.DataFrame()
