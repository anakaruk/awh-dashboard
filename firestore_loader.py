import os
import json
import pandas as pd
from google.cloud import firestore
import streamlit as st

# 🔐 Load credentials from Streamlit secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Initialize Firestore client
db = firestore.Client()

# 📡 Get list of stations
@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

# 📥 Load data for a specific station
@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

