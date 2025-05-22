import streamlit as st
from google.cloud import firestore
import pandas as pd

st.set_page_config(page_title="AWH Dashboard", layout="wide")
st.title("📊 AWH Dashboard – Station 1 Readings")

# Load Firestore data
@st.cache_resource
def load_data():
    db = firestore.Client()
    readings = db.collection("stations").document("station_1").collection("readings").stream()
    data = []
    for doc in readings:
        doc_data = doc.to_dict()
        doc_data["id"] = doc.id
        data.append(doc_data)
    return pd.DataFrame(data)

try:
    df = load_data()

    if df.empty:
        st.warning("No data found.")
    else:
        # Parse timestamp if exists
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Show table
        st.subheader("📋 Data Table")
        st.dataframe(df)

        # Plotting
        numeric_columns = df.select_dtypes(include='number').columns.tolist()
        if numeric_columns:
            st.subheader("📈 Chart View")
            x_axis = st.selectbox("X-axis", options=['timestamp'] + numeric_columns)
            y_axis = st.selectbox("Y-axis", options=numeric_columns)
            if x_axis in df.columns and y_axis in df.columns:
                chart_data = df.set_index(x_axis)[y_axis]
                st.line_chart(chart_data)

        # CSV Export
        st.subheader("📥 Download CSV")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "station_1_data.csv", "text/csv")

except Exception as e:
    st.error(f"Failed to load data: {e}")
