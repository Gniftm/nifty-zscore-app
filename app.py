import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Layout Configuration
st.set_page_config(
    page_title="Nifty & Sensex Historical Z-Score Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Historical & Real-Time Z-Score Tracker: Nifty 50 & Sensex")
st.markdown(
    "This app pulls **historical data** across your chosen timeframe, computes"
    " the rolling moving average and standard deviation, and tracks the"
    " historical **Z-Score** to spot market extremes."
)

# Sidebar Controls for Customization
st.sidebar.header("Configuration Parameters")
window = st.sidebar.slider(
    "Rolling Window (Trading Days)",
    min_value=10,
    max_value=200,
    value=50,
    step=5,
    help="Number of days used to calculate the historical mean and standard deviation.",
)
history_period = st.sidebar.selectbox(
    "Historical Data Scope", ["6mo", "1y", "2y", "5y", "10y"], index=2
)


# Function to fetch historical data with caching
@st.cache_data(ttl=300)
def fetch_index_data(ticker, period):
  df = yf.download(ticker, period=period, interval="1d", progress=False)
  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
  return df


# Dictionary of Tickers
indices = {"Nifty 50": "^NSEI", "BSE Sensex": "^BSESN"}

col1, col2 = st.columns(2)
columns_list = [col1, col2]

for i, (name, symbol) in enumerate(indices.items()):
  with columns_list[i]:
    st.subheader(f"📈 {name}")

    with st.spinner(f"Fetching historical data for {name}..."):
      df = fetch_index_data(symbol, history_period)

      if df.empty or "Close" not in df.columns:
        st.error(f"Could not retrieve historical data for {name}.")
        continue

      # Ensure data is clean and series format
      close_prices = df["Close"].squeeze()

      # Calculate Rolling Mean, Standard Deviation, and Z-Score
      rolling_mean = close_prices.rolling(window=window).mean()
      rolling_std = close_prices.rolling(window=window).std()
      z_score = (close_prices - rolling_mean) / rolling_std

      df["Z_Score"] = z_score
      df = df.dropna(subset=["Z_Score"])  # Drop initial NaN rows from rolling window

      latest_price = float(close_prices.iloc[-1])
      latest_z = float(df["Z_Score"].iloc[-1])
      prev_price = float(close_prices.iloc[-2])
      pct_change = ((latest_price - prev_price) / prev_price) * 100

      # Display Current Price & Live Z-Score Metrics
      m_col1, m_col2 = st.columns(2)
      m_col1.metric(
          "Current Price",
          value=f"{latest_price:,.2f}",
          delta=f"{pct_change:.2f}%",
      )
      m_col2.metric("Current Z-Score", value=f"{latest_z:.2f}")

      # Conditional Market Condition Status
      if latest_z > 2.0:
        st.warning(
            "⚠️ **Status: Overbought** (Z-Score > +2.0 standard deviations)"
        )
      elif latest_z < -2.0:
        st.info("ℹ️ **Status: Oversold** (Z-Score < -2.0 standard deviations)")
      else:
        st.success("✅ **Status: Normal Range** (Within ±2.0 standard deviations)")

      # Historical Z-Score Summary Statistics Box
      hist_max_z = float(df["Z_Score"].max())
      hist_min_z = float(df["Z_Score"].min())
      hist_mean_z = float(df["Z_Score"].mean())

      st.markdown("**Historical Z-Score Stats (Selected Period):**")
      stat_col1, stat_col2, stat_col3 = st.columns(3)
      stat_col1.metric("Max Z", f"{hist_max_z:.2f}")
      stat_col2.metric("Min Z", f"{hist_min_z:.2f}")
      stat_col3.metric("Avg Z", f"{hist_mean_z:.2f}")

      # Render Full Historical Z-Score Line Chart
      st.markdown("**Historical Z-Score Trend Line:**")
      st.line_chart(df[["Z_Score"]], height=280)

# Footer Note
st.markdown("---")
st.caption(
    "Data source: Yahoo Finance. The Z-Score reflects historical deviation"
    " from the moving average over the selected timeline scope."
)