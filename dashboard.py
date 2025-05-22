import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Credentials
service_account_info = json.loads(st.secrets["gcp_service_account"])
with open("/tmp/service_account.json", "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/service_account.json"

db = firestore.Client()

@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# 🔹 Sidebar layout
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Station", get_station_list())
    show_date = st.checkbox("🗓️ Date/time", value=False)
    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake air temp", value=False)

df = load_station_data(selected_station)

st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning("No data found.")
else:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        col1, col2, col3 = st.columns([1, 1, 2])

        # ⏱️ Date filters (for future filtering logic)
        with col1:
            st.subheader("Date/Time")
            start_date = st.date_input("Start", df["timestamp"].min().date())
            end_date = st.date_input("End", df["timestamp"].max().date())

        # 📊 Select data to plot
        with col2:
            st.subheader("Select Data")
            available_metrics = []
            if show_weight and "weight" in df.columns:
                available_metrics.append("weight")
            if show_power and "power" in df.columns:
                available_metrics.append("power")
            if show_temp and "temperature" in df.columns:
                available_metrics.append("temperature")

            y_axis = st.selectbox("Y-axis data", available_metrics if available_metrics else ["None"])

            # 🧾 Show table of timestamp + selected column
            st.subheader("📋 Data Table")
            if y_axis != "None" and y_axis in df.columns:
                table_df = df[["timestamp", y_axis]]
                st.dataframe(table_df)
            else:
                st.info("Please select a variable to view its data.")

        # 📈 Plot area
        with col3:
            st.subheader("📈 Plot")
            if y_axis != "None" and y_axis in df.columns:
                st.markdown(f"**Plotting:** `{y_axis}` over time")
                plot_df = df.set_index("timestamp")
                st.line_chart(plot_df[y_axis])
            else:
                st.info("No data selected to plot.")
