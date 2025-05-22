import streamlit as st
import pandas as pd

def render_controls(station_list):
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", station_list)

    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake Air Temp", value=False)

    return selected_station, show_weight, show_power, show_temp


def render_data_section(df, station_id, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_id}")

    if df.empty:
        st.warning("No data found.")
        return

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    if selected_fields:
        for field in selected_fields:
            st.subheader(f"📊 `{field}` Data")

            col1, col2 = st.columns([1, 3], gap="large")

            with col1:
                st.markdown("#### 📋 Table")
                st.dataframe(df[["timestamp", field]], use_container_width=True)

                st.download_button(
                    label=f"⬇️ Download `{field}` CSV",
                    data=df[["timestamp", field]].to_csv(index=False),
                    file_name=f"{station_id}_{field}.csv",
                    mime="text/csv"
                )

            with col2:
                st.markdown("#### 📈 Plot")
                df_sorted = df.sort_values("timestamp")
                st.line_chart(df_sorted.set_index("timestamp")[field])
    else:
        st.info("☝️ Please select at least one data type from the sidebar to view and plot.")

