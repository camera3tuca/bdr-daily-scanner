# ===================================================================
# SCANNER DIÁRIO DE BDRs - TENDÊNCIA + MOMENTUM + VOLUME
# VERSÃO STREAMLIT CLOUD (GitHub)
# Interface Web | Execução diária | 100+ BDRs
# Google Colab | 100+ BDRs | Sinais para o pregão atual
# ===================================================================

# =========================
# CÉLULA 1 - INSTALAÇÃO
# =========================
!pip install yfinance pandas numpy matplotlib requests tqdm -q

# =========================
# CÉLULA 2 - IMPORTS
# =========================
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import requests
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# =========================
# CÉLULA 3 - CONFIGURAÇÕES
# =========================
BRAPI_API_TOKEN = "iExnKM1xcbQcYL3cNPhPQ3"
LOOKBACK_DAYS = 180

# =========================
# CÉLULA 4 - CLASSE DO SCANNER
# =========================
class BDRDailyScanner:

    def __init__(self, brapi_key):
        self.brapi_key = brapi_key
        self.cache = {}

    # =========================
    # BUSCA AUTOMÁTICA DE 100+ BDRs
    # =========================
    def get_top_bdrs(self, limit=120):
        url = f"https://brapi.dev/api/quote/list?token={self.brapi_key}"
        stocks = requests.get(url, timeout=30).json().get('stocks', [])
        df = pd.DataFrame(stocks)
        df = df[df['stock'].str.endswith(('34','35'))]
        df['us'] = df['stock'].str[:-2]
        df = df.sort_values('volume', ascending=False)
        return df['us'].head(limit).tolist()

    # =========================
    def get_data(self, ticker):
        if ticker in self.cache:
            return self.cache[ticker]

        df = yf.download(ticker, period=f"{LOOKBACK_DAYS}d", progress=False)
        if df.empty or len(df) < 80:
            return None

        df = self.indicators(df)
        self.cache[ticker] = df
        return df

    # =========================
    def indicators(self, df):
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

    # =========================
    def score_today(self, df):
        last = df.iloc[-1]
        prev = df.iloc[-6]
        score = 0
        reasons = []

        # Tendência forte
        slope = df['EMA21'].diff(5).iloc[-1]
        if last['Close'] > last['EMA21'] > last['EMA50'] and slope > 0:
            score += 40
            reasons.append('Tendência de alta')

        # RSI saudável
        if 40 <= last['RSI'] <= 65:
            score += 20
            reasons.append('RSI em zona de força')

        # Volume crescente
        if last['Volume'] > last['VOL_MA']:
            score += 15
            reasons.append('Volume acima da média')

        # Breakout curto
        if last['Close'] > df['Close'].rolling(20).max().iloc[-2]:
            score += 15
            reasons.append('Breakout de 20 dias')

        return score, reasons

    # =========================
    def scan(self, min_score=60):
        tickers = self.get_top_bdrs()
        results = []

        print(f"🔎 Escaneando {len(tickers)} BDRs...")

        for t in tqdm(tickers):
            df = self.get_data(t)
            if df is None:
                continue

            score, reasons = self.score_today(df)

            if score >= min_score:
                last = df.iloc[-1]
                results.append({
                    'Ticker': t,
                    'Preço': round(last['Close'], 2),
                    'Score': score,
                    'RSI': round(last['RSI'], 1),
                    'ATR': round(last['ATR'], 2),
                    'Motivos': ', '.join(reasons)
                })

        return pd.DataFrame(results).sort_values('Score', ascending=False)

# =========================
# CÉLULA 5 - EXECUÇÃO DO SCANNER
# =========================

scanner = BDRDailyScanner(BRAPI_API_TOKEN)

signals = scanner.scan(min_score=60)

print("\n📌 SINAIS PARA O DIA:")
display(signals)

# Exporta para CSV
signals.to_csv('scanner_bdrs_diario.csv', index=False)
print("\nArquivo salvo: scanner_bdrs_diario.csv")
