# ==========================================================
# SCANNER DIÁRIO DE BDRs
# Tendência + Momentum + Volume
# Streamlit Cloud - VERSÃO BLINDADA
# ==========================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ----------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------------
st.set_page_config(
    page_title="Scanner Diário de BDRs",
    layout="wide"
)

st.title("Scanner Diário de BDRs")
st.caption("Tendência + Momentum + Volume | Execução diária")

# ----------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------
BRAPI_API_TOKEN = st.secrets["BRAPI_API_TOKEN"]
BRAPI_LIST_URL = "https://brapi.dev/api/quote/list"

# ----------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------
st.sidebar.header("Parâmetros")

min_score = st.sidebar.slider(
    "Score mínimo", 20, 90, 40, 5
)

max_bdrs = st.sidebar.slider(
    "Quantidade de BDRs analisadas", 50, 150, 100, 10
)

run_button = st.sidebar.button("Executar Scanner")

# ----------------------------------------------------------
# FUNÇÕES
# ----------------------------------------------------------
@st.cache_data(ttl=3600)
def get_bdrs():
    r = requests.get(
        BRAPI_LIST_URL,
        params={"token": BRAPI_API_TOKEN},
        timeout=30
    )
    data = r.json().get("stocks", [])

    bdrs = [
        item["stock"][:-2]
        for item in data
        if item.get("stock", "").endswith(("34", "35"))
    ]

    return list(set(bdrs))


@st.cache_data(ttl=3600)
def get_price_data(ticker):
    try:
        df = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True
        )
    except Exception:
        return None

    if not isinstance(df, pd.DataFrame):
        return None

    if df.empty or len(df) < 60:
        return None

    # Indicadores
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["Volume_MA"] = df["Volume"].rolling(20).mean()

    df = df.dropna()

    if df.empty or len(df) < 10:
        return None

    return df


def score_asset(df):
    # 🔒 Blindagem absoluta
    if not isinstance(df, pd.DataFrame):
        return 0, [], None

    if df.empty or len(df) < 60:
        return 0, [], None

    last = df.iloc[-1]

    try:
        close = float(last["Close"])
        ema21 = float(last["EMA21"])
        ema50 = float(last["EMA50"])
        rsi = float(last["RSI"])
        volume = float(last["Volume"])
        vol_ma = float(last["Volume_MA"])
    except Exception:
        return 0, [], None

    slope = df["EMA21"].iloc[-5:].diff().mean()

    score = 0
    reasons = []

    # Tendência
    if close > ema21 and ema21 > ema50 and slope > 0:
        score += 40
        reasons.append("Tendência de alta (EMA21 > EMA50)")
    elif close < ema21:
        score -= 20

    # Momentum
    if rsi < 35:
        score += 20
        reasons.append("RSI em sobrevenda")
    elif rsi > 70:
        score -= 20

    # Volume
    if volume > vol_ma:
        score += 20
        reasons.append("Volume acima da média")

    return score, reasons, last


# ----------------------------------------------------------
# EXECUÇÃO DO SCANNER
# ----------------------------------------------------------
if run_button:
    st.info("Buscando BDRs mais líquidas...")

    bdrs = get_bdrs()[:max_bdrs]

    results = []
    progress = st.progress(0)

    total = len(bdrs)

    for i, ticker in enumerate(bdrs):
        progress.progress((i + 1) / total)

        df = get_price_data(ticker)
        if df is None:
            continue

        score, reasons, last = score_asset(df)
        if last is None:
            continue

        if score >= min_score:
            results.append({
                "BDR": ticker,
                "Score": score,
                "Preço": round(float(last["Close"]), 2),
                "RSI": round(float(last["RSI"]), 1),
                "Volume": int(last["Volume"]),
                "Motivos": " | ".join(reasons)
            })

    progress.empty()

    if results:
        df_results = pd.DataFrame(results).sort_values(
            by="Score", ascending=False
        )
        st.success(f"{len(df_results)} BDRs encontradas")
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("Nenhuma BDR atingiu o score mínimo hoje.")
        
