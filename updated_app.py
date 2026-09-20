from email.mime.text import MIMEText
import smtplib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# Page Layout Configuration
st.set_page_config(
    page_title="Nifty, Sensex & Ratio Z-Score Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Multi-Asset Z-Score & Email Alert Tracker")
st.markdown(
    "Tracking individual index price trends, Z-Scores, **Min/Max extremes**,"
    " and sending automated **Email Notifications** upon custom threshold"
    " breaches."
)


# --- AUTOMATED EMAIL SENDER FUNCTION ---
def send_email_alert(subject, body):
  try:
    if "email" not in st.secrets:
      return  # Silently skip if email secrets aren't configured yet

    sender = st.secrets["email"]["sender"]
    password = st.secrets["email"]["password"]
    receiver = st.secrets["email"]["receiver"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)
    server.sendmail(sender, receiver, msg.as_string())
    server.quit()
  except Exception as e:
    st.error(f"Failed to send email notification: {e}")


# --- GENERAL Z-SCORE PLAYBOOK REFERENCE GUIDE ---
with st.expander(
    "📖 General Z-Score Scenario Reference Guide (Click to Expand)",
    expanded=False,
):
  st.markdown("""
    ### How to Interpret Z-Score Scenarios (General Rules)
    A Z-score measures how many standard deviations an asset price or ratio is away from its rolling historical mean ($Z = 0$).
    
    * **$Z > +2.0$ (Overbought / Extreme High):** 
      * *Individual Index:* Price is statistically overextended to the upside. High risk of mean-reversion pullback. **General Action:** Book profits, avoid fresh longs, or consider hedging.
      * *Ratio (Sensex/Nifty):* Sensex has massively outperformed Nifty. **General Action:** Short Sensex / Long Nifty pair trade.
    * **$+1.0 \le Z \le +2.0$ (Upper Band / Strong Momentum):**
      * *Individual Index:* Bullish trend, but approaching statistical stretching limits. **General Action:** Trailing stop-loss on longs; exercise caution adding fresh capital.
    * **$-1.0 < Z < +1.0$ (Normal / Equilibrium Range):**
      * *Individual Index / Ratio:* Market is operating cleanly within normal historical standard deviations. **General Action:** No aggressive directional changes required; follow core trend strategy.
    * **$-2.0 \le Z < -1.0$ (Lower Band / Weakness):**
      * *Individual Index:* Bearish pressure, approaching historical support bands. **General Action:** Watch for reversal confirmation signals.
    * **$Z < -2.0$ (Oversold / Extreme Low):**
      * *Individual Index:* Price is statistically oversold to the downside. High probability of an eventual snapback/bounce. **General Action:** Look for dip-buying / mean-reversion long opportunities (while minding stop-losses for structural trends).
      * *Ratio (Sensex/Nifty):* Nifty has massively outperformed Sensex. **General Action:** Long Sensex / Short Nifty pair trade.
    """)

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

# --- CUSTOM ALERT THRESHOLD INPUTS ---
st.sidebar.markdown("---")
st.sidebar.header("🚨 Custom Alert Thresholds")
st.sidebar.markdown(
    "Set your custom Z-score limits. Email notifications will trigger if"
    " current levels breach these bounds."
)

nifty_max_thresh = st.sidebar.number_input(
    "Nifty Max Z-Score Trigger", value=2.0, step=0.1
)
nifty_min_thresh = st.sidebar.number_input(
    "Nifty Min Z-Score Trigger", value=-2.0, step=0.1
)

sensex_max_thresh = st.sidebar.number_input(
    "Sensex Max Z-Score Trigger", value=2.0, step=0.1
)
sensex_min_thresh = st.sidebar.number_input(
    "Sensex Min Z-Score Trigger", value=-2.0, step=0.1
)

ratio_max_thresh = st.sidebar.number_input(
    "Ratio Max Z-Score Trigger", value=2.0, step=0.1
)
ratio_min_thresh = st.sidebar.number_input(
    "Ratio Min Z-Score Trigger", value=-2.0, step=0.1
)


# Function to fetch data for both tickers efficiently
@st.cache_data(ttl=300)
def fetch_market_data(period):
  tickers = ["^NSEI", "^BSESN"]
  df = yf.download(tickers, period=period, interval="1d", progress=False)

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

  market_df = pd.DataFrame(
      {"Nifty": nifty_close, "Sensex": sensex_close}
  ).dropna()

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

    if "Nifty" in name:
      custom_max = nifty_max_thresh
      custom_min = nifty_min_thresh
    else:
      custom_max = sensex_max_thresh
      custom_min = sensex_min_thresh

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

    # --- CUSTOM NOTIFICATION TRIGGER & EMAIL DISPATCH ---
    if latest_z >= custom_max:
      alert_msg = (
          f"🚨 CUSTOM THRESHOLD BREACH ALERT ({name}): Current Z-Score"
          f" ({latest_z:.2f}) has exceeded your custom max limit of"
          f" +{custom_max:.2f}!"
      )
      st.error(alert_msg)
      send_email_alert(
          f"🚨 Z-Score Max Breach Alert: {name}",
          f"Hello,\n\n{alert_msg}\nCurrent Price: {latest_price:,.2f}\n\nCheck"
          " your Streamlit Dashboard for full details.",
      )
    elif latest_z <= custom_min:
      alert_msg = (
          f"🚨 CUSTOM THRESHOLD BREACH ALERT ({name}): Current Z-Score"
          f" ({latest_z:.2f}) has fallen below your custom min limit of"
          f" {custom_min:.2f}!"
      )
      st.error(alert_msg)
      send_email_alert(
          f"🚨 Z-Score Min Breach Alert: {name}",
          f"Hello,\n\n{alert_msg}\nCurrent Price: {latest_price:,.2f}\n\nCheck"
          " your Streamlit Dashboard for full details.",
      )

    if latest_z > 2.0:
      st.warning(
          f"⚠️ **Real-Time Dynamic Status for {name}: OVERBOUGHT (Z ="
          f" {latest_z:.2f} > +2.0)**\n\n* **Action Guidance:** Statistically"
          " stretched to the upside. Consider **booking profits** on existing"
          " longs."
      )
    elif latest_z < -2.0:
      st.info(
          f"💡 **Real-Time Dynamic Status for {name}: OVERSOLD (Z ="
          f" {latest_z:.2f} < -2.0)**\n\n* **Action Guidance:** Statistically"
          " stretched to the downside. Consider looking for **long entry"
          " opportunities**."
      )
    else:
      st.success(
          f"✅ **Real-Time Dynamic Status for {name}: NORMAL RANGE (Z ="
          f" {latest_z:.2f})**\n\n* **Action Guidance:** Price is operating"
          " within normal statistical bands."
      )

    # Charts
    col_c1, col_c2 = st.columns(2)
    with col_c1:
      st.markdown(f"**Historical Price Chart ({name}):**")
      st.line_chart(temp_df[["Close"]], height=250)
    with col_c2:
      st.markdown(f"**Historical Z-Score Trend ({name}):**")
      st.line_chart(temp_df[["Z_Score"]], height=250)

    st.markdown(f"**🔗 Combined Price & Z-Score Chart ({name}):**")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=temp_df.index,
            y=temp_df["Close"],
            name="Price",
            line=dict(color="#1f77b4", width=2),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=temp_df.index,
            y=temp_df["Z_Score"],
            name="Z-Score",
            line=dict(color="#ff7f0e", width=1.5, dash="dot"),
        ),
        secondary_y=True,
    )
    fig.add_hline(
        y=custom_max,
        line_dash="dash",
        line_color="purple",
        annotation_text=f"Custom Max (+{custom_max})",
        secondary_y=True,
    )
    fig.add_hline(
        y=custom_min,
        line_dash="dash",
        line_color="brown",
        annotation_text=f"Custom Min ({custom_min})",
        secondary_y=True,
    )
    fig.add_hline(
        y=0.0, line_dash="solid", line_color="gray", secondary_y=True
    )
    fig.update_yaxes(title_text=f"{name} Price", secondary_y=False)
    fig.update_yaxes(
        title_text="Z-Score", secondary_y=True, range=[-4.5, 4.5]
    )
    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

  # --- RATIO ANALYSIS SECTION ---
  st.markdown("---")
  st.subheader("⚖️ Sensex / Nifty 50 Ratio Analysis")
  st.markdown(
      "Calculated as **Sensex Price ÷ Nifty 50 Price**. Visualizing both the"
      " absolute raw ratio movement and its statistical Z-score extremes."
  )

  ratio_series = market_df["Sensex"] / market_df["Nifty"]
  ratio_mean = ratio_series.rolling(window=window).mean()
  ratio_std = ratio_series.rolling(window=window).std()
  ratio_z = (ratio_series - ratio_mean) / ratio_std

  ratio_df = pd.DataFrame(
      {"Ratio": ratio_series, "Ratio_Z_Score": ratio_z}
  ).dropna()

  if not ratio_df.empty:
    latest_ratio = float(ratio_df["Ratio"].iloc[-1])
    prev_ratio = float(ratio_series.iloc[-2])
    ratio_pct_change = ((latest_ratio - prev_ratio) / prev_ratio) * 100
    latest_ratio_z = float(ratio_df["Ratio_Z_Score"].iloc[-1])

    max_ratio_z = float(ratio_df["Ratio_Z_Score"].max())
    min_ratio_z = float(ratio_df["Ratio_Z_Score"].min())
    avg_ratio_z = float(ratio_df["Ratio_Z_Score"].mean())
    max_ratio_val = float(ratio_df["Ratio"].max())
    min_ratio_val = float(ratio_df["Ratio"].min())

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

    st.markdown("**Ratio Z-Score Range Stats (Selected Scope):**")
    rz_col1, rz_col2, rz_col3 = st.columns(3)
    rz_col1.metric("Max Ratio Z", f"{max_ratio_z:.2f}")
    rz_col2.metric("Min Ratio Z", f"{min_ratio_z:.2f}")
    rz_col3.metric("Avg Ratio Z", f"{avg_ratio_z:.2f}")

    st.markdown("**Absolute Ratio Value Range Stats (Selected Scope):**")
    rv_col1, rv_col2 = st.columns(2)
    rv_col1.metric("Max Ratio Value", f"{max_ratio_val:.4f}")
    rv_col2.metric("Min Ratio Value", f"{min_ratio_val:.4f}")

    # --- CUSTOM RATIO NOTIFICATION TRIGGER & EMAIL DISPATCH ---
    if latest_ratio_z >= ratio_max_thresh:
      alert_msg = (
          f"🚨 CUSTOM THRESHOLD BREACH ALERT (Sensex/Nifty Ratio): Ratio Z-Score"
          f" ({latest_ratio_z:.2f}) has exceeded your custom max limit of"
          f" +{ratio_max_thresh:.2f}!"
      )
      st.error(alert_msg)
      send_email_alert(
          "🚨 Z-Score Max Breach Alert: Sensex/Nifty Ratio",
          f"Hello,\n\n{alert_msg}\nRecommended Action: Consider Short Sensex /"
          " Long Nifty.\n\nCheck your Streamlit Dashboard for full details.",
      )
    elif latest_ratio_z <= ratio_min_thresh:
      alert_msg = (
          f"🚨 CUSTOM THRESHOLD BREACH ALERT (Sensex/Nifty Ratio): Ratio Z-Score"
          f" ({latest_ratio_z:.2f}) has fallen below your custom min limit of"
          f" {ratio_min_thresh:.2f}!"
      )
      st.error(alert_msg)
      send_email_alert(
          "🚨 Z-Score Min Breach Alert: Sensex/Nifty Ratio",
          f"Hello,\n\n{alert_msg}\nRecommended Action: Consider Long Sensex /"
          " Short Nifty.\n\nCheck your Streamlit Dashboard for full details.",
      )

    if latest_ratio_z > 2.0:
      st.warning(
          f"⚠️ **Real-Time Dynamic Status for Ratio: SENSEX OVERVALUED RELATIVE"
          f" TO NIFTY (Z = {latest_ratio_z:.2f} > +2.0)**\n\n* **Action Guidance"
          " (Pair Trade):** Short Sensex / Long Nifty."
      )
    elif latest_ratio_z < -2.0:
      st.info(
          f"💡 **Real-Time Dynamic Status for Ratio: SENSEX UNDERVALUED RELATIVE"
          f" TO NIFTY (Z = {latest_ratio_z:.2f} < -2.0)**\n\n* **Action Guidance"
          " (Pair Trade):** Long Sensex / Short Nifty."
      )
    else:
      st.success(
          f"✅ **Real-Time Dynamic Status for Ratio: NORMAL SPREAD BAND (Z ="
          f" {latest_ratio_z:.2f})**\n\n* **Action Guidance (Pair Trade):**"
          " Remain flat."
      )

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