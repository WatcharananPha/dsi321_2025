import streamlit as st
import pandas as pd
import numpy as np
import os
import time
from datetime import timezone
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import requests

ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "access_key")
SECRET_KEY = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "secret_key")
LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT_URL", "http://localhost:8001/")
REPO_NAME = "dataset"
BRANCH_NAME = "main"
TARGET_PARQUET_FILE_PATH = "egat_datascraping/egat_realtime_power_history.parquet"
lakefs_s3_path = f"s3a://{REPO_NAME}/{BRANCH_NAME}/{TARGET_PARQUET_FILE_PATH}"
storage_options = {
    "key": ACCESS_KEY,
    "secret": SECRET_KEY,
    "client_kwargs": {
        "endpoint_url": LAKEFS_ENDPOINT
    }
}

REFRESH_INTERVAL_DEFAULT = 30
ANOMALY_SENSITIVITY_DEFAULT = 10
MAX_DISPLAY_POINTS = 100
TIMESTAMP_COLUMN = 'scrape_timestamp_utc'
DISPLAY_TIME_COLUMN = 'display_time'
POWER_COLUMN = 'current_value_MW'
TEMP_COLUMN = 'temperature_C'

st.set_page_config(page_title="EGAT Realtime Power Dashboard (lakeFS)", layout="wide")

def detect_anomalies(data_series, contamination_factor=0.1):
    if data_series is None or data_series.empty or data_series.isnull().all():
        return np.array([False] * (len(data_series) if data_series is not None else 0))
    valid_data = data_series.dropna()
    if len(valid_data) < 2:
        return np.array([False] * len(data_series))
    scaled_data = StandardScaler().fit_transform(valid_data.values.reshape(-1, 1))
    predictions = IsolationForest(contamination=contamination_factor, random_state=42, n_estimators=100).fit_predict(scaled_data) == -1
    anomalies = np.array([False] * len(data_series))
    valid_indices = data_series.dropna().index
    for i, index in enumerate(valid_indices):
        original_pos = data_series.index.get_loc(index)
        if i < len(predictions):
            anomalies[original_pos] = predictions[i]
    return anomalies

@st.cache_data(ttl=REFRESH_INTERVAL_DEFAULT)
def load_data_from_lakefs(s3_path, storage_opts):
    df = pd.read_parquet(s3_path, storage_options=storage_opts)
    if pd.api.types.is_numeric_dtype(df[TIMESTAMP_COLUMN]):
        df[TIMESTAMP_COLUMN] = pd.to_datetime(df[TIMESTAMP_COLUMN], unit='us', errors='coerce')
    else:
        df[TIMESTAMP_COLUMN] = pd.to_datetime(df[TIMESTAMP_COLUMN], errors='coerce')
    df.dropna(subset=[TIMESTAMP_COLUMN], inplace=True)
    return df.sort_values(by=TIMESTAMP_COLUMN, ascending=False)

def create_sidebar():
    auto_refresh = st.sidebar.checkbox('Enable Auto-refresh', value=True)
    refresh_interval = st.sidebar.slider('Refresh Interval (s)', 5, 120, REFRESH_INTERVAL_DEFAULT)
    contamination_factor = st.sidebar.slider('Anomaly Sensitivity (%)', 1, 25, ANOMALY_SENSITIVITY_DEFAULT) / 100
    st.sidebar.caption(f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    return auto_refresh, refresh_interval, contamination_factor

def display_metrics(latest_data_row, anomaly_status):
    col1, col2, col3, col4 = st.columns(4)
    power = latest_data_row.get(POWER_COLUMN, "N/A")
    temp = latest_data_row.get(TEMP_COLUMN, "N/A")
    disp_time = latest_data_row.get(DISPLAY_TIME_COLUMN, "N/A")
    col1.metric("⚡ Power Output", f"{power:,.1f} MW" if pd.notna(power) else "N/A")
    col2.metric("🌡️ Temperature", f"{temp:.1f}°C" if pd.notna(temp) else "N/A")
    col3.metric("🕒 Source Time", str(disp_time))
    col4.error("⚠️ Anomaly" if anomaly_status else "✅ Normal")

def display_charts(chart_data):
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader(f"⚡ {POWER_COLUMN}")
        st.line_chart(chart_data.set_index(TIMESTAMP_COLUMN)[POWER_COLUMN], height=300)
    with chart_col2:
        st.subheader(f"🌡️ {TEMP_COLUMN}")
        st.line_chart(chart_data.set_index(TIMESTAMP_COLUMN)[TEMP_COLUMN], height=300)

def display_statistics(anomalies, chart_data):
    st.subheader("📊 Chart Data Statistics")
    cols = st.columns(4)
    total_anomalies = anomalies.sum()
    anomaly_rate = (total_anomalies / len(anomalies)) * 100 if len(anomalies) > 0 else 0
    avg_power = chart_data[POWER_COLUMN].mean()
    peak_power = chart_data[POWER_COLUMN].max()
    cols[0].metric("Anomalies", f"{int(total_anomalies)}")
    cols[1].metric("Anomaly Rate", f"{anomaly_rate:.1f}%")
    cols[2].metric("Avg Power", f"{avg_power:,.1f} MW")
    cols[3].metric("Peak Power", f"{peak_power:,.1f} MW")

def display_recent_data_table(df_all_data, anomalies):
    st.subheader("📝 Recent Data (Latest 10)")
    df_display = df_all_data.head(10).copy()
    df_display['Status'] = ['⚠️ Anomaly' if anom else '✅ Normal' for anom in anomalies[:len(df_display)]]
    cols = [TIMESTAMP_COLUMN, DISPLAY_TIME_COLUMN, POWER_COLUMN, TEMP_COLUMN, 'Status']
    existing_cols = [c for c in cols if c in df_display.columns]
    st.dataframe(df_display[existing_cols], hide_index=True)

def run_app():
    st.title("⚡ EGAT Realtime Power Generation Dashboard (via lakeFS)")
    auto_refresh, refresh_interval, contamination = create_sidebar()
    last_refresh_ph = st.empty()
    metrics_ph = st.container()
    table_ph = st.container()
    charts_stats_ph = st.container()

    df_all_data = load_data_from_lakefs(lakefs_s3_path, storage_options)
    latest_row = df_all_data.iloc[0] if not df_all_data.empty else {}
    chart_data = df_all_data.head(MAX_DISPLAY_POINTS).sort_values(TIMESTAMP_COLUMN, ascending=True)
    anomalies_chart = detect_anomalies(chart_data[POWER_COLUMN], contamination) if POWER_COLUMN in chart_data else np.array([])
    anomaly_latest = anomalies_chart[-1] if len(anomalies_chart) > 0 else False

    with metrics_ph:
        display_metrics(latest_row, anomaly_latest)
    with table_ph:
        display_recent_data_table(df_all_data, anomalies_chart)
    with charts_stats_ph:
        display_charts(chart_data)
        display_statistics(anomalies_chart, chart_data)

    last_refresh_ph.caption(f"Dashboard refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    run_app()