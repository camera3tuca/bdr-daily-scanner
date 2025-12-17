import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# =========================
# CONFIGURAÇÕES
# =========================
st.set_page_config(page_title="Scanner Profissional de BDRs", layout="wide")

BDRS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "NFLX", "AMD", "INTC",
    "JPM", "BAC", "WFC", "GS", "MS",
    "JNJ", "PFE", "MRK", "ABBV", "LLY",
    "KO", "PEP", "MCD", "NKE", "DIS",
    "V", "MA", "PYPL", "ADBE", "CRM",
    "ORCL", "IBM", "CSCO", "QCOM", "AVGO",
    "BA", "GE", "CAT", "DE", "MMM",
    "XOM", "CVX", "SLB", "COP", "BP",
    "WMT", "COST", "TGT", "HD", "LOW",
] * 6  # ≈300 ativos

PERIOD = "1y"
INTERVAL = "1d"

# =========================
# INDICADORES
# =========================
def indicators(df):
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
    df["Max50"] = df["High"].rolling(50).max()

    return df.dropna()

# =========================
# SCORE ENGINE PROFISSIONAL
# =========================
def score_asset(df):
    if df.empty or len(df) < 210:
        return 0, [], None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    reasons = []

    # ---- Tendência (0–30)
    if last.Close > last.EMA21 > last.EMA50 > last.EMA200:
        score += 30
        reasons.append("Tendência forte (EMAs alinhadas)")

    # ---- Momentum (0–25)
    if 55 <= last.RSI <= 70 and last.RSI > prev.RSI:
        score += 25
        reasons.append("Momentum saudável (RSI)")

    # ---- Volume Inteligente (0–20)
    if last.Volume > last.Vol_Mean:
        score += 20
        reasons.append("Volume acima da média")

    # ---- Breakout (0–25)
    if last.Close > prev.Max20 and last.Volume > last.Vol_Mean:
        score += 25
        reasons.append("Breakout confirmado")

    return score, reasons, last

# =========================
# GRÁFICO PROFISSIONAL
# =========================
def plot_chart(df, ticker):
    fig = go.Figure()

    fig.add_candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Preço"
    )

    fig.add_trace(go.Scatter(x=df.index, y=df["EMA21"], name="EMA21"))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA50"], name="EMA50"))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA200"], name="EMA200"))

    fig.update_layout(
        title=f"{ticker} - Gráfico Técnico",
        height=600,
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# INTERFACE
# =========================
st.title("Scanner Profissional de BDRs")
st.caption("Ranking + Tendência + Momentum + Volume + Breakout | Execução diária")

with st.sidebar:
    score_min = st.slider("Score mínimo", 20, 90, 40)
    qtd = st.slider("Quantidade de BDRs analisadas", 50, 300, 150)
    run = st.button("Executar Scanner")

# =========================
# EXECUÇÃO
# =========================
if run:
    st.info("Buscando BDRs mais líquidas...")

    results = []
    data_cache = {}

    for ticker in BDRS[:qtd]:
        try:
            df = yf.download(ticker, period=PERIOD, interval=INTERVAL, progress=False)
            if df.empty:
                continue

            df = indicators(df)
            score, reasons, last = score_asset(df)

            if last is None or score < score_min:
                continue

            results.append({
                "BDR": ticker,
                "Score": score,
                "Preço": round(last.Close, 2),
                "RSI": round(last.RSI, 1),
                "Volume": int(last.Volume),
                "Motivos": " | ".join(reasons)
            })

            data_cache[ticker] = df

        except Exception:
            continue

    if not results:
        st.warning("Nenhuma BDR encontrada com os critérios atuais.")
    else:
        df_res = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.success(f"{len(df_res)} BDRs encontradas")

        st.dataframe(df_res, use_container_width=True)

        selected = st.selectbox("Selecionar BDR para gráfico", df_res["BDR"])
        plot_chart(data_cache[selected], selected)
        
