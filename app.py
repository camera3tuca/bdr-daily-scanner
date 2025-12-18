import streamlit as st
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import time
import json

# ============================
# CONFIGURAÇÃO DA PÁGINA
# ============================
st.set_page_config(
    page_title="Scanner Profissional de BDRs",
    layout="wide"
)

st.title("Scanner Profissional de BDRs")
st.caption("Eventos + Notícias + Dados | Execução diária")

# ============================
# CHAVES (USE SECRETS NO STREAMLIT CLOUD)
# ============================
FINNHUB_API_KEY = st.secrets.get("FINNHUB_API_KEY", "")
BRAPI_API_TOKEN = st.secrets.get("BRAPI_API_TOKEN", "")

# ============================
# PARÂMETROS (SIDEBAR)
# ============================
st.sidebar.header("Parâmetros")

MIN_SCORE = st.sidebar.slider("Score mínimo", 20, 80, 20)
MAX_BDRS = st.sidebar.slider("Quantidade de ativos", 20, 300, 100)
EARNINGS_WINDOW = st.sidebar.slider("Janela de Earnings (dias)", 10, 60, 45)

RUN = st.sidebar.button("Executar Scanner")

# ============================
# CLASSE PRINCIPAL
# ============================
class AdvancedNewsTracker:

    def __init__(self):
        self.params = {
            'min_score': MIN_SCORE,
            'earnings_window': EARNINGS_WINDOW,
            'earnings_0_3': 60,
            'earnings_4_7': 55,
            'earnings_8_14': 50,
            'earnings_15_30': 45,
            'earnings_31_45': 35,
        }

    def get_bdrs_brapi(self):
        url = f"https://brapi.dev/api/quote/list?token={BRAPI_API_TOKEN}"
        r = requests.get(url, timeout=20)
        df = pd.DataFrame(r.json().get("stocks", []))
        df = df[df["stock"].str.endswith(("34", "35"))]
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        return df.sort_values("volume", ascending=False).head(MAX_BDRS)

    def convert_us(self, bdr):
        return bdr[:-2]

    def get_finnhub_news(self, ticker):
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        url = (
            f"https://finnhub.io/api/v1/company-news?"
            f"symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else []

    def analyze(self, ticker, bdr):
        score = 0
        events = []

        stock = yf.Ticker(ticker)

        # ===== EARNINGS CONFIRMADO =====
        try:
            cal = stock.calendar
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                dt = cal.iloc[0, 0]
                days = (dt.to_pydatetime() - datetime.now()).days

                if 0 <= days <= self.params["earnings_window"]:
                    if days <= 3:
                        pts = self.params["earnings_0_3"]
                    elif days <= 7:
                        pts = self.params["earnings_4_7"]
                    elif days <= 14:
                        pts = self.params["earnings_8_14"]
                    elif days <= 30:
                        pts = self.params["earnings_15_30"]
                    else:
                        pts = self.params["earnings_31_45"]

                    score += pts
                    events.append(f"Earnings em {days} dias")
        except:
            pass

        # ===== NOTÍCIAS =====
        news = self.get_finnhub_news(ticker)
        if news:
            score += 20
            events.append("Notícias recentes relevantes")

        if score >= self.params["min_score"]:
            price = stock.history(period="1d")["Close"].iloc[-1]
            return {
                "BDR": bdr,
                "Ticker US": ticker,
                "Score": score,
                "Eventos": " | ".join(events),
                "Preço US": round(price, 2)
            }

        return None

# ============================
# EXECUÇÃO
# ============================
if RUN:

    with st.spinner("Buscando BDRs mais líquidas..."):
        bot = AdvancedNewsTracker()
        df_bdrs = bot.get_bdrs_brapi()

    results = []

    progress = st.progress(0)
    for i, row in df_bdrs.iterrows():
        progress.progress((len(results)+1)/len(df_bdrs))
        us = bot.convert_us(row["stock"])
        r = bot.analyze(us, row["stock"])
        if r:
            results.append(r)
        time.sleep(0.2)

    st.success(f"{len(results)} oportunidades encontradas")

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Nenhuma oportunidade encontrada com os filtros atuais.")
