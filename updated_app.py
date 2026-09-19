import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Layout Configuration
st.set_page_config(
    page_title="Nifty, Sensex & Ratio Z-Score Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Multi-Asset Z-Score & Price Tracker: Nifty, Sensex & Ratio")
st.markdown(
    "Tracking individual index price trends, Z-Scores, **Min/Max extremes**,"
    " and the **Sensex vs. Nifty 50 Ratio** across selected historical scopes."
)

# Sidebar Controls for Customization
st.sidebar.header("Configuration Parameters")
window = st.sidebar.slider(
    "Rolling Window (Trading Days)",
    min_value=5,
    max_value=200,
    value=50,
    step=5,
    help=(
        "Number of days used to calculate the historical mean and standard"
        " deviation. (Note: For 1mo/3mo scopes, ensure window is smaller than"
        " total available trading days, e.g., 10-20 days)."
    ),
)
history_period = st.sidebar.selectbox(
    "Historical Data Scope",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"],
    index=3,  # Defaults to 1y
)


# Function to fetch data for both tickers efficiently
@st.cache_data(ttl=300)
def fetch_market_data(period):
  tickers = ["^NSEI", "^BSESN"]
  df = yf.download(tickers, period=period, interval="1d", progress=False)

  # Handle multi-index columns from yfinance
  if isinstance(df.columns, pd.MultiIndex):
    close_df = df["Close"]
  else:
    close_df = df

  return close_df


# Fetch data
with st.spinner("Fetching market data from Yahoo Finance..."):
  close_data = fetch_market_data(history_period)

if (
    close_data.empty
    or "^NSEI" not in close_data.columns
    or "^BSESN" not in close_data.columns
):
  st.error(
      "Could not retrieve data for Nifty 50 or Sensex. Try selecting a longer"
      " historical scope if the window size is too large."
  )
else:
  nifty_close = close_data["^NSEI"].dropna()
  sensex_close = close_data["^BSESN"].dropna()

  # Align dataframes by common dates
  market_df = pd.DataFrame(
      {"Nifty": nifty_close, "Sensex": sensex_close}
  ).dropna()

  # Check if data length is sufficient for the rolling window
  if len(market_df) <= window:
    st.warning(
        f"⚠️ Warning: Selected rolling window ({window} days) is larger than or"
        f" equal to the available data points ({len(market_df)} days) for"
        f" '{history_period}'. Please lower the rolling window in the sidebar or"
        " choose a longer historical scope."
    )

  # --- INDIVIDUAL INDICES SECTION ---
  indices_dict = {"Nifty 50": market_df["Nifty"], "BSE Sensex": market_df["Sensex"]}

  for name, close_prices in indices_dict.items():
    st.markdown("---")
    st.subheader(f"📈 {name} Analysis")

    rolling_mean = close_prices.rolling(window=window).mean()
    rolling_std = close_prices.rolling(window=window).std()
    z_score = (close_prices - rolling_mean) / rolling_std

    temp_df = pd.DataFrame(
        {"Close": close_prices, "Z_Score": z_score}
    ).dropna()

    if temp_df.empty:
      st.error(
          f"Not enough data points to compute Z-Score for {name} with the"
          " current window size."
      )
      continue

    latest_price = float(temp_df["Close"].iloc[-1])
    latest_z = float(temp_df["Z_Score"].iloc[-1])
    prev_price = float(temp_df["Close"].iloc[-2])
    pct_change = ((latest_price - prev_price) / prev_price) * 100

    # Metrics Display
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_col1.metric(
        "Current Price",
        value=f"{latest_price:,.2f}",
        delta=f"{pct_change:.2f}%",
    )
    m_col2.metric("Current Z-Score", value=f"{latest_z:.2f}")
    m_col3.metric("Max Z (Selected Scope)", f"{float(temp_df['Z_Score'].max()):.2f}")
    m_col4.metric("Min Z (Selected Scope)", f"{float(temp_df['Z_Score'].min()):.2f}")
    m_col5.metric("Avg Z (Selected Scope)", f"{float(temp_df['Z_Score'].mean()):.2f}")

    if latest_z > 2.0:
      st.warning(f"⚠️ **{name} Status: Overbought** (Z > +2.0)")
    elif latest_z < -2.0:
      st.info(f"ℹ️ **{name} Status: Oversold** (Z < -2.0)")
    else:
      st.success(f"✅ **{name} Status: Normal Range**")

    # Clean Independent Charts (Prevents axis-scaling distortion)
    st.markdown(f"**1. Historical Price Chart ({name}):**")
    st.line_chart(temp_df[["Close"]], height=280)

    st.markdown(f"**2. Historical Z-Score Trend Line ({name}):**")
    st.line_chart(temp_df[["Z_Score"]], height=250)

  # --- RATIO ANALYSIS SECTION (Sensex vs Nifty 50) ---
  st.markdown("---")
  st.subheader("⚖️ Sensex / Nifty 50 Ratio Analysis")
  st.markdown(
      "Calculated as **Sensex Price ÷ Nifty 50 Price**. Visualizing both the"
      " absolute raw ratio movement and its statistical Z-score."
  )

  # Compute Ratio Series and Moving Average
  ratio_series = market_df["Sensex"] / market_df["Nifty"]
  ratio_mean = ratio_series.rolling(window=window).mean()
  ratio_std = ratio_series.rolling(window=window).std()
  ratio_z = (ratio_series - ratio_mean) / ratio_std

  ratio_df = pd.DataFrame(
      {
          "Ratio": ratio_series,
          "Ratio_Z_Score": ratio_z,
      }
  ).dropna()

  if not ratio_df.empty:
    latest_ratio = float(ratio_df["Ratio"].iloc[-1])
    prev_ratio = float(ratio_series.iloc[-2])
    ratio_pct_change = ((latest_ratio - prev_ratio) / prev_ratio) * 100
    latest_ratio_z = float(ratio_df["Ratio_Z_Score"].iloc[-1])

    r_col1, r_col2, r_col3 = st.columns(3)
    r_col1.metric(
        "Current Ratio (Sensex/Nifty)",
        value=f"{latest_ratio:.4f}",
        delta=f"{ratio_pct_change:.4f}%",
    )
    r_col2.metric("Ratio Z-Score", value=f"{latest_ratio_z:.2f}")
    r_col3.metric(
        "Historical Avg Ratio", value=f"{float(ratio_mean.iloc[-1]):.4f}"
    )

    if latest_ratio_z > 2.0:
      st.warning(
          "⚠️ **Ratio Status: Sensex is historically overvalued relative to"
          " Nifty** (Z > +2.0)"
      )
    elif latest_ratio_z < -2.0:
      st.info(
          "ℹ️ **Ratio Status: Sensex is historically undervalued relative to"
          " Nifty** (Z < -2.0)"
      )
    else:
      st.success("✅ **Ratio Status: Within Normal Band**")

    # Clean Independent Ratio Charts
    st.markdown("**1. Historical Raw Ratio Chart (Sensex / Nifty 50):**")
    st.line_chart(ratio_df[["Ratio"]], height=280)

    st.markdown("**2. Historical Ratio Z-Score Trend Line:**")
    st.line_chart(ratio_df[["Ratio_Z_Score"]], height=250)

# Footer Note
st.markdown("---")
st.caption(
    "Data source: Yahoo Finance. Charts display rolling window indicators"
    " across the selected timeframe."
)