import os
import json
import pandas as pd
from google.cloud import firestore
import streamlit as st
from datetime import datetime

# 🔐 Load credentials from Streamlit secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Initialize Firestore client
db = firestore.Client()

# 📡 Get list of stations that have at least one reading
@st.cache_data
def get_station_list():
    station_docs = db.collection("stations").list_documents()
    station_ids_with_data = []

    for station_doc in station_docs:
        readings = (
            db.collection("stations")
              .document(station_doc.id)
              .collection("readings")
              .limit(1)
              .stream()
        )
        if any(True for _ in readings):  # Has at least one document
            station_ids_with_data.append(station_doc.id)

    return sorted(station_ids_with_data)

# 📥 Load data for a specific station, sorted by timestamp
@st.cache_data
def load_station_data(station_id):
    try:
        docs = (
            db.collection("stations")
              .document(station_id)
              .collection("readings")
              .order_by("timestamp", direction=firestore.Query.ASCENDING)
              .stream()
        )

        records = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id

            # Convert Firestore timestamp to Python datetime
            if "timestamp" in data and hasattr(data["timestamp"], "to_datetime"):
                data["timestamp"] = data["timestamp"].to_datetime()

            records.append(data)

        return pd.DataFrame(records)

    except Exception as e:
        st.error(f"⚠️ Failed to load Firestore data: {e}")
        return pd.DataFrame()
