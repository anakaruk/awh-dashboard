import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Load credentials from secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Initialize Firestore client
db = firestore.Client()

# 🔍 List available stations
@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

# 📥 Load data for a selected station
@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# 🌐 Sidebar controls
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", get_station_list())

    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake Air Temp", value=False)

# 📊 Load and display data
df = load_station_data(selected_station)

st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning("No data found for this station.")
else:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 📋 Determine which columns to show
    selected_fields = ["timestamp"]
    if show_weight and "weight" in df.columns:
        selected_fields.append("weight")
    if show_power and "power" in df.columns:
        selected_fields.append("power")
    if show_temp and "temperature" in df.columns:
        selected_fields.append("temperature")

    # 🖥️ Display data table
    st.subheader("📋 Data Table")
    st.dataframe(df[selected_fields])

    # 💾 Download
    st.download_button(
        label="⬇️ Download CSV",
        data=df[selected_fields].to_csv(index=False),
        file_name=f"{selected_station}_data.csv",
        mime="text/csv"
    )
