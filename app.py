# ================================================================
# app.py
# SCANNER DIÁRIO DE BDRs - STREAMLIT CLOUD
# Tendência + Momentum + Volume | 100+ BDRs
# ================================================================

import streamlit as st
import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from tqdm import tqdm
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ================================================================
# CONFIGURAÇÕES GERAIS
# ================================================================
LOOKBACK_DAYS = 180
MIN_SCORE_DEFAULT = 60

BRAPI_API_TOKEN = os.getenv("BRAPI_API_TOKEN")

if not BRAPI_API_TOKEN:
    st.error("API token da BRAPI não configurado. Configure em Settings > Secrets.")
    st.stop()

# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================
@st.cache_data(ttl=3600)
def get_top_bdrs(limit=120):
    url = f"https://brapi.dev/api/quote/list?token={BRAPI_API_TOKEN}"
    r = requests.get(url, timeout=30)
    data = r.json().get('stocks', [])

    df = pd.DataFrame(data)
    df = df[df['stock'].str.endswith(('34', '35'))]
    df['us'] = df['stock'].str[:-2]
    df = df.sort_values('volume', ascending=False)

    return df['us'].head(limit).tolist()


@st.cache_data(ttl=3600)
def download_data(ticker):
    df = yf.download(ticker, period=f"{LOOKBACK_DAYS}d", progress=False)
    if df.empty or len(df) < 80:
        return None
    return df


def add_indicators(df):
    df = df.copy()

    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()

    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['VOL_MA'] = df['Volume'].rolling(20).mean()

    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low'] - df['Close'].shift()).abs()
    ], axis=1)
    df['ATR'] = tr.max(axis=1).rolling(14).mean()

    return df


def score_asset(df):
    last = df.iloc[-1]
    score = 0
    reasons = []

    slope = df['EMA21'].diff(5).iloc[-1]

    if last['Close'] > last['EMA21'] > last['EMA50'] and slope > 0:
        score += 40
        reasons.append('Tendência de alta')

    if 40 <= last['RSI'] <= 65:
        score += 20
        reasons.append('RSI saudável')

    if last['Volume'] > last['VOL_MA']:
        score += 15
        reasons.append('Volume acima da média')

    if last['Close'] > df['Close'].rolling(20).max().iloc[-2]:
        score += 15
        reasons.append('Breakout 20d')

    return score, reasons, last

# ================================================================
# INTERFACE STREAMLIT
# ================================================================
st.set_page_config(page_title="Scanner Diário de BDRs", layout="wide")

st.title("Scanner Diário de BDRs")
st.caption("Tendência + Momentum + Volume | Execução diária")

col1, col2 = st.columns(2)

with col1:
    min_score = st.slider("Score mínimo", 40, 90, MIN_SCORE_DEFAULT, 5)

with col2:
    max_bdrs = st.slider("Quantidade de BDRs analisadas", 50, 150, 120, 10)

run = st.button("Executar Scanner")

# ================================================================
# EXECUÇÃO
# ================================================================
if run:
    st.info("Buscando BDRs mais líquidas...")
    tickers = get_top_bdrs(limit=max_bdrs)

    results = []
    progress = st.progress(0)

    for i, t in enumerate(tickers):
        df = download_data(t)
        if df is None:
            progress.progress((i + 1) / len(tickers))
            continue

        df = add_indicators(df)
        score, reasons, last = score_asset(df)

        if score >= min_score:
            results.append({
                'Ticker': t,
                'Preço': round(last['Close'], 2),
                'Score': score,
                'RSI': round(last['RSI'], 1),
                'ATR': round(last['ATR'], 2),
                'Motivos': ', '.join(reasons)
            })

        progress.progress((i + 1) / len(tickers))

    if results:
        df_res = pd.DataFrame(results).sort_values('Score', ascending=False)
        st.success(f"{len(df_res)} ativos encontrados")
        st.dataframe(df_res, use_container_width=True)

        csv = df_res.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar CSV", csv, "scanner_bdrs_diario.csv", "text/csv")
    else:
        st.warning("Nenhum ativo atingiu o score mínimo hoje.")

st.caption(f"Última execução: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
