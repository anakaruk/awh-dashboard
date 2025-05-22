import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Load credentials
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Firestore client
db = firestore.Client()

@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# 🎛️ Sidebar
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", get_station_list())
    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake Air Temp", value=False)

# 📊 Load data
df = load_station_data(selected_station)

st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning("No data found.")
else:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Select field to display (just one at a time)
    selected_fields = []
    if show_weight and "weight" in df.columns:
        selected_fields.append("weight")
    if show_power and "power" in df.columns:
        selected_fields.append("power")
    if show_temp and "temperature" in df.columns:
        selected_fields.append("temperature")

    if selected_fields:
        for field in selected_fields:
            st.subheader(f"📋 Data Table: `{field}`")
            st.dataframe(df[["timestamp", field]])

            st.subheader(f"📈 Plotting `{field}` over time")
            plot_df = df.set_index("timestamp")
            st.line_chart(plot_df[field])

            st.download_button(
                label=f"⬇️ Download `{field}` as CSV",
                data=df[["timestamp", field]].to_csv(index=False),
                file_name=f"{selected_station}_{field}.csv",
                mime="text/csv"
            )
    else:
        st.info("☝️ Please select at least one data type to display and plot.")
