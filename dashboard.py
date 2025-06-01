import streamlit as st
import pandas as pd
from firestore_loader import get_station_list, load_station_data

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")

st.title("📊 AWH Station Monitoring Dashboard")

# 🔽 Get station list
stations = get_station_list()

if stations:
    selected_station = st.selectbox("Select Station", stations, index=0)

    # 📥 Load data for selected station
    df_raw = load_station_data(selected_station)

    if df_raw.empty:
        st.warning(f"No data found for station: {selected_station}")
    else:
        st.success(f"Showing data for: {selected_station}")

        # ⏱️ Show most recent update time
        latest_time = df_raw["timestamp"].max()
        st.markdown(f"**Last Updated:** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 🧮 Display table
        st.dataframe(df_raw.tail(100), use_container_width=True)

        # 📈 Display chart
        with st.expander("📈 Show Timeseries Charts"):
            for col in df_raw.columns:
                if col not in ["timestamp", "id"] and pd.api.types.is_numeric_dtype(df_raw[col]):
                    st.line_chart(df_raw.set_index("timestamp")[col])
else:
    st.warning("⚠️ No stations with data available.")
