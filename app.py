import streamlit as st

def check_password():
    def password_entered():
        if st.session_state["password"] == "1212":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.stop()

    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        st.stop()

check_password()

import streamlit as st
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import plotly.graph_objects as go
import yfinance as yf
import os

# ====================
# CONFIG
# ====================
EXTREME_ORDER = 40
DATA_PATH = r"C:\Users\motos\OneDrive\Documents\Trading_System\HeartbeatDetectionEngineBlog\data\historical"

# Ratios based on your <7-10-12> specification
RATIO_BLUE = 7
RATIO_RED = 10
RATIO_YELLOW = 12

# ====================
# STREAMLIT SETUP
# ====================
st.set_page_config(page_title="Heartbeat Cycle Detection", layout="wide")

st.markdown("""
<style>
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
.stTabs [data-baseweb="tab-list"] {gap: 24px;}
.stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; font-size: 16px;}
</style>
""", unsafe_allow_html=True)

# ====================
# DATA LOADER
# ====================
@st.cache_data(show_spinner=False)
def load_data(ticker):
    os.makedirs(DATA_PATH, exist_ok=True)
    file_path = os.path.join(DATA_PATH, f"{ticker.upper()}.csv")
    download_new = True

    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            if all(col in df.columns for col in ["Date", "Open", "High", "Low", "Close"]):
                download_new = False
        except:
            download_new = True

    if download_new:
        try:
            df_raw = yf.download(ticker, period="max", interval="1d", progress=False, auto_adjust=True)
            if df_raw.empty: return None
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = df_raw.columns.get_level_values(0)
            df = df_raw.reset_index()
            df.rename(columns={df.columns[0]: "Date"}, inplace=True)
            df = df[["Date", "Open", "High", "Low", "Close"]]
            df.to_csv(file_path, index=False)
        except:
            return None

    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close"]).sort_values("Date").set_index("Date")
    return df

# ====================
# HELPERS
# ====================
def get_time_label(days):
    weeks = days / 5 if days > 0 else 0
    months = days / 21 if days > 0 else 0
    return f"{int(days)}d | {weeks:.1f}w | {months:.1f}m"

def calculate_zones(anchor_idx, blue_len):
    red_len = int(blue_len * (RATIO_RED / RATIO_BLUE))
    yellow_len = int(blue_len * (RATIO_YELLOW / RATIO_BLUE))
    
    return [
        {"name": "Blue Zone", "color": "blue", "len": blue_len},
        {"name": "Red Zone", "color": "red", "len": red_len},
        {"name": "Yellow Zone", "color": "yellow", "len": yellow_len}
    ]

# ====================
# PLOTTING
# ====================
def draw_chart(df, extremes, anchor_idx, blue_len, mode, log_scale, invert_scale):
    fig = go.Figure()

    # Main Price
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    ))

    # Anchor Points
    fig.add_trace(go.Scatter(
        x=df.index[extremes], y=df["Close"].iloc[extremes],
        mode="markers", marker=dict(size=10, color="purple", symbol="diamond-tall"),
        name="Detected Extremes"
    ))

    zones_meta = calculate_zones(anchor_idx, blue_len)
    current_start_idx = anchor_idx
    current_start_date = df.index[anchor_idx]
    
    y_pos = df["High"].max() * 1.05 # Position labels above price

    for zone in zones_meta:
        color = zone["color"]
        length = zone["len"]

        if mode == "Market Days":
            start_idx = current_start_idx
            end_idx = start_idx + length
            
            # Boundary check
            if start_idx >= len(df): continue
            plot_end_idx = min(end_idx, len(df) - 1)
            
            x0, x1 = df.index[start_idx], df.index[plot_end_idx]
            label = f"<b>{zone['name']}</b><br>{get_time_label(length)}"
            
            current_start_idx = end_idx # Move to next zone
        else:
            # Calendar Days logic
            start_date = current_start_date
            end_date = start_date + pd.Timedelta(days=length)
            
            x0, x1 = start_date, end_date
            label = f"<b>{zone['name']}</b><br>{get_time_label(length)}"
            
            current_start_date = end_date # Move to next zone

        # Add Shading
        fig.add_vrect(
            x0=x0, x1=x1, fillcolor=color, opacity=0.12, 
            line_width=2, line_color=color, line_dash="dot"
        )

        # Add Data Label
        fig.add_annotation(
            x=x0, y=1.02, yref="paper", text=label,
            showarrow=False, xanchor="left", yanchor="bottom",
            font=dict(color=color, size=12), bgcolor="rgba(255,255,255,0.8)"
        )

    # Layout Updates
    fig.update_layout(
        height=800,
        template="plotly_white",
        xaxis=dict(rangeslider=dict(visible=False), title="Date"),
        yaxis=dict(title="Price", side="right", type="log" if log_scale else "linear", autorange="reversed" if invert_scale else True),
        margin=dict(l=10, r=10, t=80, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

# ====================
# MAIN APP
# ====================
st.title("Heartbeat Cycle Detection Engine")

with st.sidebar:
    st.header("Settings")
    ticker = st.text_input("Ticker Symbol", "AAPL").upper()
    
    blue_len = st.slider("Base (Blue) Length", 10, 3000, 70, step=5)
    
    st.divider()
    log_scale = st.checkbox("Enable Log Scale", value=True)
    invert_scale = st.checkbox("Invert Y-Axis")
    st.info(f"Ratios: Blue={RATIO_BLUE}, Red={RATIO_RED}, Yellow={RATIO_YELLOW}")

if ticker:
    df = load_data(ticker)
    
    if df is not None:
        # Extreme detection
        price_data = df["Close"].values
        highs = argrelextrema(price_data, np.greater_equal, order=EXTREME_ORDER)[0]
        lows = argrelextrema(price_data, np.less_equal, order=EXTREME_ORDER)[0]
        extremes = np.sort(np.unique(np.concatenate((highs, lows))))
        
        # Select Anchor
        extreme_dates = {str(df.index[i].date()): i for i in extremes}
        anchor_date = st.sidebar.selectbox("Select Start Anchor", list(extreme_dates.keys()), index=len(extreme_dates)-1)
        anchor_idx = extreme_dates[anchor_date]

        tab1, tab2 = st.tabs(["📊 Market Day Analysis", "📅 Calendar Day Analysis"])
        
        with tab1:
            draw_chart(df, extremes, anchor_idx, blue_len, "Market Days", log_scale, invert_scale)
            
        with tab2:
            draw_chart(df, extremes, anchor_idx, blue_len, "Calendar Days", log_scale, invert_scale)
    else:
        st.error("Could not retrieve data. Please check the ticker symbol.")
