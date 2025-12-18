import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import time
import re
from textblob import TextBlob

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Scanner Profissional de BDRs",
    layout="wide"
)

# =========================================================
# CHAVES DE API
# =========================================================
KEYS = {
    "BRAPI": "iExnKM1xcbQcYL3cNPhPQ3",
    "FINNHUB": "d4uouchr01qnm7pnasq0d4uouchr01qnm7pnasqg"
}

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("Parâmetros")

MIN_SCORE = st.sidebar.slider(
    "Score mínimo (destaque)",
    20, 100, 40, step=5
)

TOP_LIQUIDEZ = st.sidebar.slider(
    "Quantidade de BDRs analisadas",
    30, 300, 100, step=10
)

DIAS_EARNINGS = st.sidebar.slider(
    "Janela de Earnings (dias)",
    5, 30, 15
)

EXECUTAR = st.sidebar.button("Executar Scanner")

# =========================================================
# FUNÇÕES
# =========================================================
@st.cache_data(ttl=3600)
def obter_bdrs_brapi(top_n):
    url = f"https://brapi.dev/api/quote/list?token={KEYS['BRAPI']}"
    r = requests.get(url, timeout=15)
    df = pd.DataFrame(r.json().get("stocks", []))

    df = df[df["stock"].str.contains(r"(31|32|33|34|35|39)$", regex=True)]
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    return (
        df.sort_values("volume", ascending=False)
        .head(top_n)["stock"]
        .tolist()
    )

def converter_ticker_us(bdr):
    clean = bdr.replace(".SA", "")
    us = re.sub(r"\d+$", "", clean)

    mapa = {
        "BERK": "BRK-B",
        "COCA": "KO",
        "PGCO": "PG",
        "LILY": "LLY",
        "ROXO": "NU",
        "A1MD": "AMD"
    }
    return mapa.get(us, us)

def sentimento_finnhub(symbol):
    try:
        hoje = datetime.datetime.now()
        de = (hoje - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        ate = hoje.strftime("%Y-%m-%d")

        url = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={symbol}&from={de}&to={ate}&token={KEYS['FINNHUB']}"
        )

        r = requests.get(url, timeout=5)
        noticias = r.json()[:5]

        score = 0
        headlines = []

        for n in noticias:
            blob = TextBlob(n["headline"])
            score += blob.sentiment.polarity
            headlines.append(n["headline"])

        return score, headlines
    except:
        return 0, []

def analisar_bdr(bdr):
    us = converter_ticker_us(bdr)
    hoje = datetime.datetime.now()

    resultado = {
        "BDR": bdr,
        "Ticker US": us,
        "Score": 0,
        "Ação": "Neutro",
        "Eventos": ""
    }

    try:
        stock = yf.Ticker(us)

        # ===== EARNINGS =====
        try:
            cal = stock.calendar
            earn_date = None

            if isinstance(cal, pd.DataFrame) and not cal.empty:
                earn_date = cal.iloc[0, 0]

            if earn_date:
                earn_date = pd.to_datetime(earn_date).to_pydatetime()
                dias = (earn_date - hoje).days

                if 0 <= dias <= DIAS_EARNINGS:
                    resultado["Score"] += 50
                    resultado["Eventos"] += f"Earnings em {dias} dias | "

                    if dias <= 2:
                        resultado["Score"] += 20
        except:
            pass

        # ===== DIVIDENDOS =====
        try:
            info = stock.info
            ex_div = info.get("exDividendDate")

            if ex_div:
                dt = datetime.datetime.fromtimestamp(ex_div)
                dias = (dt - hoje).days
                if 0 <= dias <= 10:
                    resultado["Score"] += 30
                    resultado["Eventos"] += "Ex-Dividendo próximo | "
        except:
            pass

        # ===== SENTIMENTO =====
        sent, headlines = sentimento_finnhub(us)

        if sent > 0.5:
            resultado["Score"] += 20
            resultado["Eventos"] += "Notícias positivas | "
        elif sent < -0.5:
            resultado["Score"] -= 20
            resultado["Eventos"] += "Notícias negativas | "

        # ===== PREÇO =====
        hist = stock.history(period="1d")
        if not hist.empty:
            resultado["Preço US"] = round(hist["Close"].iloc[-1], 2)
        else:
            resultado["Preço US"] = None

        # ===== CLASSIFICAÇÃO =====
        if resultado["Score"] >= 70:
            resultado["Ação"] = "URGENTE"
        elif resultado["Score"] >= 50:
            resultado["Ação"] = "COMPRA / OBSERVAR"
        elif resultado["Score"] >= 30:
            resultado["Ação"] = "RADAR"

    except:
        pass

    return resultado

# =========================================================
# INTERFACE
# =========================================================
st.title("Scanner Profissional de BDRs")
st.caption("Eventos + Notícias + Dados | Execução diária")

if EXECUTAR:
    with st.spinner("Buscando BDRs mais líquidas..."):
        bdrs = obter_bdrs_brapi(TOP_LIQUIDEZ)

    rows = []
    progress = st.progress(0)

    for i, bdr in enumerate(bdrs):
        rows.append(analisar_bdr(bdr))
        progress.progress((i + 1) / len(bdrs))

    df = pd.DataFrame(rows)
    df = df[df["Score"] >= MIN_SCORE]
    df = df.sort_values("Score", ascending=False)

    if df.empty:
        st.warning("Nenhuma BDR encontrada com os critérios atuais.")
    else:
        st.success(f"{len(df)} BDRs encontradas")
        st.dataframe(df, use_container_width=True)
