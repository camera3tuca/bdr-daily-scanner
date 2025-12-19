# ===================================================================
# SCANNER PROFISSIONAL DE NOTÍCIAS BDR
# Tendência + Eventos + Qualidade + Urgência
# Estilo Plataforma Paga | Streamlit Cloud
# ===================================================================

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta

# =========================
# CONFIGURAÇÕES (CHAVES)
# =========================
FINNHUB_API_KEY = "d4uouchr01qnm7pnasq0d4uouchr01qnm7pnasqg"
NEWS_API_KEY = "ec7100fa90ef4e3f9a69a914050dd736"
BRAPI_API_TOKEN = "iExnKM1xcbQcYL3cNPhPQ3"

# =========================
# PARÂMETROS OTIMIZADOS
# =========================
PARAMS = {
    "stop_loss": 0.03,
    "take_profit": 0.15,
    "hold_days": 5,
    "min_score": 20,

    "earnings_scores": {
        "0_3": 60,
        "4_7": 55,
        "8_14": 50,
        "15_30": 45,
        "31_45": 35
    },
    "dividend_scores": {
        "0_1": 50,
        "2_5": 45,
        "6_10": 40,
        "11_20": 35,
        "21_30": 30
    }
}

TRUSTED_SOURCES = [
    "reuters", "bloomberg", "cnbc", "marketwatch",
    "wsj", "financial times", "barrons", "yahoo finance"
]

# =========================
# FUNÇÕES AUXILIARES
# =========================
@st.cache_data(ttl=86400)
def load_bdr_mapping():
    url = f"https://brapi.dev/api/quote/list?token={BRAPI_API_TOKEN}"
    r = requests.get(url, timeout=30)
    data = r.json().get("stocks", [])
    mapping = {}
    for s in data:
        t = s.get("stock", "")
        if t.endswith(("34", "35")):
            mapping[t[:-2]] = t
    return mapping

def get_news_finnhub(ticker):
    d1 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    d2 = datetime.now().strftime("%Y-%m-%d")
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={d1}&to={d2}&token={FINNHUB_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def get_yahoo_data(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        cal = t.calendar
        earnings_date = None
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            earnings_date = cal.iloc[0, 0]
        return {
            "news": t.news or [],
            "earnings_date": earnings_date,
            "ex_div": info.get("exDividendDate"),
            "div_yield": info.get("dividendYield")
        }
    except:
        return {"news": [], "earnings_date": None, "ex_div": None, "div_yield": None}

def assess_quality(news):
    title = (news.get("headline") or news.get("title") or "").lower()
    source = (news.get("source") or news.get("publisher") or "").lower()
    url = (news.get("url") or "").lower()

    score = 0
    reasons = []

    if any(s in source or s in url for s in TRUSTED_SOURCES):
        score += 20
        reasons.append("Fonte confiável")

    if any(w in title for w in ["announces", "reports", "confirms"]):
        score += 15
        reasons.append("Evento confirmado")

    if any(w in title for w in ["rumor", "may", "could", "might"]):
        score -= 10
        reasons.append("Possível rumor")

    return score, reasons

def classify_events(news, yahoo):
    text = f"{news.get('headline','')} {news.get('summary','')}".lower()
    events = []
    score = 0

    patterns = {
        "earnings": ["earnings", "results"],
        "guidance": ["guidance", "outlook"],
        "dividend": ["dividend"],
        "merger": ["merger", "acquisition"],
        "product": ["launch", "unveil"]
    }

    for etype, kws in patterns.items():
        if any(k in text for k in kws):
            events.append(f"{etype.title()} anunciado")
            score += 30

    ed = yahoo.get("earnings_date")
    if isinstance(ed, (datetime, pd.Timestamp)):
        days = (ed - datetime.now()).days
        if -2 <= days <= 45:
            if days <= 3:
                boost = PARAMS["earnings_scores"]["0_3"]
            elif days <= 7:
                boost = PARAMS["earnings_scores"]["4_7"]
            elif days <= 14:
                boost = PARAMS["earnings_scores"]["8_14"]
            elif days <= 30:
                boost = PARAMS["earnings_scores"]["15_30"]
            else:
                boost = PARAMS["earnings_scores"]["31_45"]
            events.append(f"📅 Earnings em {days}d")
            score += boost

    ex = yahoo.get("ex_div")
    dy = yahoo.get("div_yield")
    if ex and dy:
        d = (datetime.fromtimestamp(ex) - datetime.now()).days
        if -2 <= d <= 30:
            events.append(f"💰 Ex-Div em {d}d")
            score += 40

    return events, score

def priority(score):
    if score >= 70:
        return "🔴 URGENTE"
    if score >= 50:
        return "🟠 ALTA"
    if score >= 30:
        return "🟡 MÉDIA"
    return "⚪ BAIXA"

def recommendation(score):
    if score >= 70:
        return "🔴 COMPRAR AGORA"
    if score >= 50:
        return "🟠 MONITORAR ENTRADA"
    return "🟡 OBSERVAR"

# =========================
# INTERFACE STREAMLIT
# =========================
st.set_page_config("Scanner Diário de BDRs", layout="wide")
st.title("📊 Scanner Profissional de Notícias BDR")
st.caption("Tendência + Eventos + Qualidade + Urgência")

min_score = st.slider("Score mínimo", 20, 90, 40)
max_assets = st.slider("Quantidade de BDRs analisadas", 50, 150, 100)

st.info("🔍 Buscando BDRs via Brapi...")
bdr_map = load_bdr_mapping()
tickers = list(bdr_map.keys())[:max_assets]
st.success(f"✅ {len(bdr_map)} BDRs mapeados")

results = []
progress = st.progress(0.0)

for i, tk in enumerate(tickers, 1):
    progress.progress(i / len(tickers))
    yahoo = get_yahoo_data(tk)
    news_all = get_news_finnhub(tk) + yahoo["news"]

    for n in news_all[:5]:
        q_score, q_reasons = assess_quality(n)
        ev, ev_score = classify_events(n, yahoo)
        final = ev_score + q_score

        if ev and final >= min_score:
            results.append({
                "Ticker": tk,
                "BDR": bdr_map.get(tk, "N/A"),
                "Score": final,
                "Prioridade": priority(final),
                "Eventos": " | ".join(ev),
                "Qualidade": ", ".join(q_reasons) or "Padrão",
                "Ação": recommendation(final),
                "Notícia": n.get("headline") or n.get("title")
            })
    time.sleep(0.2)

df = pd.DataFrame(results).sort_values("Score", ascending=False)

st.subheader("🎯 Oportunidades Detectadas")
st.dataframe(df, use_container_width=True)

urgent = df[df["Prioridade"].str.contains("🔴")]
if not urgent.empty:
    st.error("🚨 ALERTAS URGENTES")
    st.table(urgent[["Ticker", "Score", "Eventos", "Ação"]])

with open("tracking.json", "w") as f:
    json.dump(results, f, indent=2)

st.success("✅ Sistema completo ativo")
