# ==============================================================================
# SCANNER PROFISSIONAL DE BDRs – STREAMLIT
# Tendência + Momentum + Volume + Eventos + Notícias
# Script COMPLETO (base Claude) adaptado para app.py
# ============================================================================== 

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import time
import re
from textblob import TextBlob

# ===================== CONFIGURAÇÕES / CHAVES =====================
KEYS = {
    "BRAPI": "iExnKM1xcbQcYL3cNPhPQ3",
    "FINNHUB": "d4uouchr01qnm7pnasq0d4uouchr01qnm7pnasqg",
    "NEWSAPI": "ec7100fa90ef4e3f9a69a914050dd736"
}

CONFIG_DEFAULT = {
    "TOP_LIQUIDEZ": 40,
    "DIAS_EARNINGS": 15,
    "MIN_SCORE": 40
}

# ===================== FUNÇÕES AUXILIARES =====================

def obter_bdrs_brapi(top_n):
    try:
        url = f"https://brapi.dev/api/quote/list?token={KEYS['BRAPI']}"
        r = requests.get(url, timeout=15)
        df = pd.DataFrame(r.json().get('stocks', []))
        df = df[df['stock'].str.contains(r'(31|32|33|34|35|39)$', regex=True)]
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df = df.sort_values('volume', ascending=False).head(top_n)
        return df['stock'].tolist()
    except Exception:
        return []


def converter_ticker_us(bdr):
    clean = bdr.replace('.SA', '')
    us = re.sub(r'\d+$', '', clean)
    mapa = {
        'BERK': 'BRK-B', 'MCDC': 'MCD', 'COCA': 'KO', 'PGCO': 'PG',
        'ROXO': 'NU', 'A1MD': 'AMD', 'LILY': 'LLY', 'H1ON': 'HON'
    }
    return mapa.get(us, us)


def finnhub_sentiment(symbol):
    try:
        hoje = datetime.datetime.now()
        de = (hoje - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
        ate = hoje.strftime('%Y-%m-%d')
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={de}&to={ate}&token={KEYS['FINNHUB']}"
        r = requests.get(url, timeout=10)
        score = 0
        headlines = []
        if r.status_code == 200:
            for n in r.json()[:5]:
                blob = TextBlob(n.get('headline', ''))
                score += blob.sentiment.polarity
                headlines.append(n.get('headline', ''))
        return score, headlines
    except Exception:
        return 0, []


# ===================== CORE DO SCANNER =====================

def analisar_bdr(bdr, dias_earnings):
    us = converter_ticker_us(bdr)
    rep = {
        "BDR": bdr,
        "US": us,
        "Score": 0,
        "Eventos": [],
        "Ação": "Neutro"
    }

    try:
        stock = yf.Ticker(us)

        # -------- EARNINGS (peso 50 + urgência) --------
        try:
            cal = stock.calendar
            earn_date = None
            if isinstance(cal, dict) and 'Earnings Date' in cal:
                earn_date = cal['Earnings Date'][0]
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                if 'Earnings Date' in cal.index:
                    earn_date = cal.loc['Earnings Date'].iloc[0]

            if earn_date is not None:
                if earn_date.tzinfo:
                    earn_date = earn_date.tz_localize(None)
                dias = (earn_date - datetime.datetime.now()).days
                if 0 <= dias <= dias_earnings:
                    rep['Score'] += 50
                    rep['Eventos'].append(f"Balanço em {dias} dias")
                    if dias <= 2:
                        rep['Score'] += 20
                        rep['Eventos'].append("Alta volatilidade iminente")
        except Exception:
            pass

        # -------- DIVIDENDOS (peso 30) --------
        try:
            info = stock.info
            ex_div = info.get('exDividendDate')
            if ex_div:
                dt = datetime.datetime.fromtimestamp(ex_div)
                dias_div = (dt - datetime.datetime.now()).days
                if 0 <= dias_div <= 10:
                    rep['Score'] += 30
                    rep['Eventos'].append("Data Ex-Dividendo próxima")
        except Exception:
            pass

        # -------- NOTÍCIAS / SENTIMENTO (peso 20) --------
        sent, heads = finnhub_sentiment(us)
        if sent > 0.5:
            rep['Score'] += 20
            rep['Eventos'].append("Notícias positivas recentes")
        elif sent < -0.5:
            rep['Score'] -= 20
            rep['Eventos'].append("Notícias negativas recentes")

        for h in heads:
            if any(k in h.lower() for k in ['upgrade', 'buy', 'record', 'approval', 'merger']):
                rep['Score'] += 10
                rep['Eventos'].append("Notícia relevante detectada")
                break

        # -------- PREÇO --------
        hist = stock.history(period="1d")
        if not hist.empty:
            rep['Preço US'] = float(hist['Close'].iloc[-1])
        else:
            rep['Preço US'] = None

        # -------- AÇÃO FINAL --------
        if rep['Score'] >= 70:
            rep['Ação'] = "URGENTE"
        elif rep['Score'] >= 50:
            rep['Ação'] = "COMPRA / OBSERVAR"
        elif rep['Score'] >= 30:
            rep['Ação'] = "RADAR"

    except Exception:
        pass

    return rep


# ===================== INTERFACE STREAMLIT =====================

st.set_page_config(page_title="Scanner Profissional de BDRs", layout="wide")

st.title("Scanner Diário de BDRs")
st.caption("Eventos + Notícias + Score Fundamental | Execução diária")

with st.sidebar:
    st.header("Parâmetros")
    min_score = st.slider("Score mínimo", 30, 90, CONFIG_DEFAULT['MIN_SCORE'])
    qtd_bdrs = st.slider("Quantidade de BDRs analisadas", 20, 150, CONFIG_DEFAULT['TOP_LIQUIDEZ'])
    dias_earn = st.slider("Dias para Earnings", 5, 30, CONFIG_DEFAULT['DIAS_EARNINGS'])
    executar = st.button("Executar Scanner")

if executar:
    st.info("Buscando BDRs mais líquidas...")
    lista = obter_bdrs_brapi(qtd_bdrs)

    resultados = []
    progress = st.progress(0)

    for i, bdr in enumerate(lista):
        res = analisar_bdr(bdr, dias_earn)
        if res['Score'] >= min_score:
            resultados.append(res)
        progress.progress((i + 1) / len(lista))

    if resultados:
        df = pd.DataFrame(resultados).sort_values('Score', ascending=False)
        st.success(f"{len(df)} oportunidades encontradas")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Nenhum ativo passou nos filtros definidos")
