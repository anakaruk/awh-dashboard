def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    available_fields = [col for col in selected_fields if col in df_sorted.columns and col != "timestamp"]

    for field in available_fields:
        st.subheader(f"📊 `{field}` Overview")
        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download `{field}` CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Scatter Plot")

            # Force numeric and drop NaNs just for plotting
            df_sorted[field] = pd.to_numeric(df_sorted[field], errors='coerce')
            plot_data = df_sorted[["Time", "Date", field]].dropna()

            if plot_data.empty:
                st.warning(f"⚠️ No data available to plot for `{field}`.")
                continue

            y_axis = alt.Y(
                field,
                title=field,
                scale=alt.Scale(domain=[0, 50]) if field == "harvesting_efficiency" else alt.Undefined
            )

            chart = alt.Chart(plot_data).mark_circle(size=60).encode(
                x=alt.X("Time:N", title="Time"),
                y=y_axis,
                tooltip=["Date", "Time", field]
            ).properties(width="container", height=300)

            st.altair_chart(chart, use_container_width=True)
