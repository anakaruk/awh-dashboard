import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Set credentials
service_account_info = json.loads(st.secrets["gcp_service_account"])
with open("/tmp/service_account.json", "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/service_account.json"

# Firestore client
db = firestore.Client()

# 🚀 Get available stations dynamically
def get_stations():
    return [doc.id for doc in db.collection("stations").list_documents()]

station_list = get_stations()

# 🚦 Station selector
selected_station = st.selectbox("Select a Station", station_list)

# 🧠 Load data for selected station
@st.cache_data(show_spinner=False)
def load_data(station_id):
    readings = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in readings])

df = load_data(selected_station)

# 🖥️ UI
st.title(f"📊 AWH Dashboard – {selected_station} Readings")

if df.empty:
    st.warning(f"No data found for `{selected_station}`.")
else:
    st.dataframe(df)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        st.line_chart(df.set_index("timestamp").select_dtypes(include="number"))
