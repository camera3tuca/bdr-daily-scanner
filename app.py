import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Scanner Profissional de BDRs", layout="wide")

BDRS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX","AMD","INTC",
    "JPM","BAC","WFC","GS","MS","JNJ","PFE","MRK","ABBV","LLY",
    "KO","PEP","MCD","NKE","DIS","V","MA","PYPL","ADBE","CRM",
    "ORCL","IBM","CSCO","QCOM","AVGO","BA","GE","CAT","DE","MMM",
    "XOM","CVX","SLB","COP","BP","WMT","COST","TGT","HD","LOW"
] * 6  # ~300

PERIOD = "1y"
INTERVAL = "1d"

# =========================
# INDICADORES
# =========================
def calc_indicators(df):
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["Vol_Mean"] = df["Volume"].rolling(20).mean()
    df["Max20"] = df["High"].rolling(20).max()

    return df.dropna()

# =========================
# SCORE ENGINE
# =========================
def score_asset(df):
    if len(df) < 210:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    scores = {
        "Tendência": 0,
        "Momentum": 0,
        "Volume": 0,
        "Breakout": 0
    }

    if last.Close > last.EMA21 > last.EMA50 > last.EMA200:
        scores["Tendência"] = 30

    if 55 <= last.RSI <= 70 and last.RSI > prev.RSI:
        scores["Momentum"] = 25

    if last.Volume > last.Vol_Mean:
        scores["Volume"] = 20

    if last.Close > prev.Max20 and last.Volume > last.Vol_Mean:
        scores["Breakout"] = 25

    total = sum(scores.values())

    return {
        "Preço": round(last.Close, 2),
        "RSI": round(last.RSI, 1),
        "Volume": int(last.Volume),
        "Score": total,
        **scores
    }

# =========================
# GRÁFICO
# =========================
def plot_chart(df, ticker):
    fig = go.Figure()
    fig.add_candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"]
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA21"], name="EMA21"))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA50"], name="EMA50"))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA200"], name="EMA200"))

    fig.update_layout(
        title=f"{ticker} – Gráfico Técnico",
        height=550,
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================
# INTERFACE
# =========================
st.title("Scanner Profissional de BDRs")
st.caption("Ranking + Estratégias | Execução diária")

with st.sidebar:
    score_min = st.slider("Score mínimo (destaque)", 20, 90, 40)
    qtd = st.slider("Quantidade de BDRs analisadas", 50, 300, 150)
    run = st.button("Executar Scanner")

# =========================
# EXECUÇÃO
# =========================
if run:
    st.info("Processando BDRs...")
    rows = []
    cache = {}

    for ticker in BDRS[:qtd]:
        try:
            df = yf.download(ticker, period=PERIOD, interval=INTERVAL, progress=False)
            if df.empty:
                continue

            df = calc_indicators(df)
            result = score_asset(df)
            if result is None:
                continue

            rows.append({"BDR": ticker, **result})
            cache[ticker] = df

        except Exception:
            continue

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)

    if df_all.empty:
        st.warning("Sem dados suficientes no momento.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Ranking Geral", "Tendência", "Breakout", "Momentum"]
        )

        with tab1:
            st.dataframe(df_all.head(20), use_container_width=True)

        with tab2:
            st.dataframe(df_all[df_all["Tendência"] > 0], use_container_width=True)

        with tab3:
            st.dataframe(df_all[df_all["Breakout"] > 0], use_container_width=True)

        with tab4:
            st.dataframe(df_all[df_all["Momentum"] > 0], use_container_width=True)

        destaque = df_all[df_all["Score"] >= score_min]

        if not destaque.empty:
            st.success(f"{len(destaque)} BDRs com score ≥ {score_min}")

        selected = st.selectbox("Selecionar BDR para gráfico", df_all["BDR"])
        plot_chart(cache[selected], selected)
    
