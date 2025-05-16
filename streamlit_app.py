import streamlit as st
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

CSV_FILE = "egat_realtime_power.csv"
REFRESH_INTERVAL_DEFAULT = 30
ANOMALY_SENSITIVITY_DEFAULT = 10
MAX_DISPLAY_POINTS = 100

st.set_page_config(
    page_title="EGAT Realtime Power Dashboard",
    layout="wide",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': 'EGAT Realtime Power Generation Dashboard v2.0'
    }
)

def detect_anomalies(data, contamination=0.1):
    """Detect anomalies in power generation data using Isolation Forest"""
    if len(data) < 10:
        return np.zeros(len(data), dtype=bool)
    
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data.values.reshape(-1, 1))
    
    iso_forest = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )   
    predictions = iso_forest.fit_predict(scaled_data)
    return predictions == -1

def load_data():
    """Load and preprocess the power generation data"""
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        df['scrape_time'] = pd.to_datetime(df['scrape_time'])
        return df.sort_values(by='scrape_time', ascending=False)
    return pd.DataFrame()

def create_sidebar():
    """Create and configure the sidebar controls"""
    st.sidebar.markdown("### 🎛️ Dashboard Controls")
    auto_refresh = st.sidebar.checkbox('Enable Auto-refresh', value=True)
    refresh_interval = st.sidebar.slider(
        'Refresh Interval (seconds)', 
        5, 60, 
        REFRESH_INTERVAL_DEFAULT
    )
    
    st.sidebar.markdown("### 🔍 Anomaly Detection")
    contamination = st.sidebar.slider(
        'Sensitivity (%)', 
        min_value=1, 
        max_value=20, 
        value=ANOMALY_SENSITIVITY_DEFAULT
    ) / 100
    
    st.sidebar.markdown("### 👤 User Information")
    st.sidebar.text(f"User: {os.getenv('USERNAME', 'WatcharananPha')}")
    st.sidebar.text(f"UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return auto_refresh, refresh_interval, contamination

def display_metrics(latest_data, anomaly_detected):
    """Display the main metrics dashboard"""
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "⚡ Power Output",
        f"{latest_data['current_value_MW']:,.1f} MW",
        delta=None
    )
    col2.metric(
        "🌡️ Temperature",
        f"{latest_data['temperature_C']:.1f}°C",
        delta=None
    )
    col3.metric(
        "🕒 Last Update",
        latest_data['display_time']
    )
    
    if anomaly_detected:
        col4.error("⚠️ Anomaly Detected!")
    else:
        col4.success("✅ Normal Operation")

def display_charts(chart_data, anomalies):
    """Display power and temperature charts"""
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("⚡ Power Generation (MW)")
        st.line_chart(
            data=chart_data.set_index('scrape_time')['current_value_MW'],
            use_container_width=True,
            height=300
        )
        
    with chart_col2:
        st.subheader("🌡️ Temperature (°C)")
        st.line_chart(
            data=chart_data.set_index('scrape_time')['temperature_C'],
            use_container_width=True,
            height=300,
            color='#FF4B4B'
        )

def display_statistics(anomalies, chart_data):
    """Display anomaly and system statistics"""
    st.markdown("---")
    st.subheader("📊 System Statistics")
    
    stats_cols = st.columns(4)
    
    total_anomalies = anomalies.sum()
    anomaly_rate = (total_anomalies / len(anomalies)) * 100
    
    stats_cols[0].metric(
        "Anomalies Detected",
        f"{int(total_anomalies)}"   
    )
    stats_cols[1].metric(
        "Anomaly Rate",
        f"{anomaly_rate:.1f}%"
    )
    stats_cols[2].metric(
        "Avg Power",
        f"{chart_data['current_value_MW'].mean():,.1f} MW"
    )
    stats_cols[3].metric(
        "Peak Power",
        f"{chart_data['current_value_MW'].max():,.1f} MW"
    )

def display_dashboard():
    """Main dashboard display function"""
    st.title("⚡ EGAT Realtime Power Generation Dashboard")
    
    auto_refresh, refresh_interval, contamination = create_sidebar()
    
    last_refresh = st.empty()
    data_container = st.container()
    charts_container = st.container()
    
    while True:
        df = load_data()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with data_container:
            if not df.empty:
                recent_data = df.head(MAX_DISPLAY_POINTS)
                anomalies = detect_anomalies(recent_data['current_value_MW'], contamination)
                
                display_metrics(df.iloc[0], anomalies[0])
                
                st.subheader("📝 Recent Data")
                df_display = recent_data.copy()
                df_display['Status'] = ['⚠️ Anomaly' if a else '✅ Normal' for a in anomalies]
                st.dataframe(
                    df_display[['scrape_time', 'display_time', 'current_value_MW', 
                               'temperature_C', 'Status']].head(10),
                    use_container_width=True
                )
            else:
                st.info("⏳ Waiting for data...")

        with charts_container:
            if not df.empty:
                chart_data = df.sort_values('scrape_time').tail(MAX_DISPLAY_POINTS)
                display_charts(chart_data, anomalies)
                display_statistics(anomalies, chart_data)

        last_refresh.text(f"Last refreshed: {current_time}")
        
        if not auto_refresh:
            break
            
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    display_dashboard()