import streamlit as st
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import time
import re
from textblob import TextBlob
from deep_translator import GoogleTranslator

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Scanner Diário de BDRs", page_icon="🚀", layout="wide")

# --- SEGREDOS (Carregados do Streamlit Cloud ou Padrão) ---
FINNHUB_KEY = st.secrets.get("FINNHUB_API_KEY", "d4uouchr01qnm7pnasq0d4uouchr01qnm7pnasqg")
NEWS_KEY = st.secrets.get("NEWS_API_KEY", "ec7100fa90ef4e3f9a69a914050dd736")
BRAPI_TOKEN = st.secrets.get("BRAPI_API_TOKEN", "iExnKM1xcbQcYL3cNPhPQ3")

# --- CLASSE MONITOR ---
class SwingTradeMonitor:
    def __init__(self):
        self.translator = GoogleTranslator(source='auto', target='pt')
        self.ticker_map = self._carregar_mapa_bdr_us()
        
    def _carregar_mapa_bdr_us(self):
        # Mapeamento manual para garantir precisão
        return {
            'AAPL': 'AAPL34', 'MSFT': 'MSFT34', 'GOOGL': 'GOGL34', 'AMZN': 'AMZO34', 
            'NVDA': 'NVDC34', 'TSLA': 'TSLA34', 'META': 'FBOK34', 'NFLX': 'NFLX34',
            'AMD': 'A1MD34', 'INTC': 'ITLC34', 'JPM': 'JPMC34', 'BAC': 'BOAC34',
            'WMT': 'WALM34', 'KO': 'COCA34', 'PEP': 'PEPB34', 'JNJ': 'JNJB34',
            'DIS': 'DISB34', 'PFE': 'PFIZ34', 'XOM': 'EXXO34', 'CVX': 'CHVX34',
            'PG': 'PGCO34', 'V': 'VISA34', 'MA': 'MSCD34', 'MCD': 'MCDC34',
            'ABBV': 'ABBV34', 'MRK': 'MRCK34', 'CRM': 'SACM34', 'ORCL': 'ORCL34',
            'AVGO': 'AVGO34', 'CSCO': 'CSCO34', 'ACN': 'ACNB34', 'ADBE': 'ADBE34',
            'QCOM': 'QCOM34', 'TXN': 'TEXA34', 'HON': 'HONB34', 'UNH': 'UNHH34'
        }

    def traduzir(self, texto):
        """Traduz texto para PT-BR com cache simples para não travar"""
        if not texto or len(texto) < 3: return texto
        try:
            return self.translator.translate(texto)
        except:
            return texto # Retorna original se falhar

    def obter_bdrs_brapi(self, limite=50):
        try:
            url = f"https://brapi.dev/api/quote/list?token={BRAPI_TOKEN}"
            r = requests.get(url, timeout=10)
            data = r.json().get('stocks', [])
            df = pd.DataFrame(data)
            df = df[df['stock'].str.contains(r'(31|32|33|34|35|39)$')]
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            # Retorna lista de BDRs ordenados por volume
            return df.sort_values('volume', ascending=False).head(limite)['stock'].tolist()
        except:
            # Fallback se Brapi falhar: usa o mapa manual
            return list(self.ticker_map.values())

    def converter_para_us(self, bdr):
        """Tenta reverter BDR para Ticker US"""
        bdr_clean = bdr.replace('.SA', '')
        # Tenta achar no mapa reverso
        for us, br in self.ticker_map.items():
            if br == bdr_clean: return us
        # Tenta regra geral
        return re.sub(r'\d+$', '', bdr_clean)

    def get_yahoo_data(self, ticker_us):
        """Busca dados fundamentais (Earnings/Dividendos)"""
        try:
            stock = yf.Ticker(ticker_us)
            
            # Tenta pegar dados rápidos
            try: cal = stock.calendar; earn_date = cal.get('Earnings Date', [None])[0] if cal else None
            except: earn_date = None
            
            try: info = stock.info; ex_div = info.get('exDividendDate'); div_yield = info.get('dividendYield')
            except: ex_div, div_yield = None, None
            
            # Pega histórico para tendência
            hist = stock.history(period='1mo')
            trend = "Lateral"
            if len(hist) > 20:
                sma20 = hist['Close'].mean()
                atual = hist['Close'].iloc[-1]
                trend = "Alta 📈" if atual > sma20 else "Baixa 📉"
            
            return {
                'earnings': earn_date,
                'ex_div': ex_div,
                'yield': div_yield,
                'trend': trend,
                'price': hist['Close'].iloc[-1] if not hist.empty else 0
            }
        except:
            return None

    def get_news(self, ticker_us):
        """Busca notícias recentes no Finnhub"""
        try:
            # Pega notícias dos últimos 3 dias
            hj = datetime.now().strftime('%Y-%m-%d')
            inicio = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/company-news?symbol={ticker_us}&from={inicio}&to={hj}&token={FINNHUB_KEY}'
            r = requests.get(url, timeout=5)
            return r.json() if r.status_code == 200 else []
        except: return []

    def analisar_ativo(self, bdr):
        ticker_us = self.converter_para_us(bdr)
        if not ticker_us: return None
        
        y_data = self.get_yahoo_data(ticker_us)
        if not y_data: return None
        
        noticias = self.get_news(ticker_us)
        
        score = 0
        eventos = []
        manchete_top = ""
        link_top = ""
        
        # 1. Análise de Earnings (50 pts)
        if y_data['earnings']:
            dias = (pd.to_datetime(y_data['earnings']).replace(tzinfo=None) - datetime.now()).days
            if 0 <= dias <= 15:
                score += 50
                urgencia = "🔥 AMANHÃ" if dias <= 1 else f"em {dias}d"
                eventos.append(f"Balanço {urgencia}")
        
        # 2. Análise de Dividendos (30 pts)
        if y_data['ex_div']:
            dias = (datetime.fromtimestamp(y_data['ex_div']) - datetime.now()).days
            if 0 <= dias <= 10:
                score += 30
                yield_fmt = f"{(y_data['yield']*100):.1f}%" if y_data['yield'] else "?"
                eventos.append(f"Data Com (Div) em {dias}d (Y: {yield_fmt})")

        # 3. Análise de Notícias (até 20 pts)
        # Analisa até 15 notícias (pedido do usuário)
        for n in noticias[:15]:
            texto = f"{n['headline']} {n['summary']}".lower()
            
            # Palavras-chave positivas
            if any(x in texto for x in ['upgrade', 'buy', 'record', 'growth', 'dividend', 'soar', 'jump']):
                blob = TextBlob(texto)
                if blob.sentiment.polarity > 0.1:
                    score += 5
                    if not manchete_top:
                        manchete_top = n['headline']
                        link_top = n['url']
            
            if score >= 60: break # Teto de score por notícias

        # Definição de Ação
        if score >= 60: acao = "COMPRAR AGORA 🔴"
        elif score >= 40: acao = "MONITORAR 🟠"
        elif score >= 20: acao = "RADAR 🟡"
        else: return None # Filtra o que não é interessante

        # Traduz a manchete se houver
        if manchete_top:
            manchete_top = self.traduzir(manchete_top)

        return {
            "BDR": bdr,
            "US": ticker_us,
            "Preço (US)": y_data['price'],
            "Tendência": y_data['trend'],
            "Score": min(score, 100), # Teto 100
            "Ação": acao,
            "Motivo": ", ".join(eventos) if eventos else "Fluxo de Notícias Positivo",
            "Manchete": manchete_top,
            "Link": link_top
        }

# --- INTERFACE STREAMLIT ---

st.title("🇧🇷 Scanner Pro de BDRs: Oportunidades de Compra")
st.markdown("""
Monitora **Eventos Corporativos** (Balanços, Dividendos) e **Notícias Otimistas** traduzidas para o português.
Foca apenas no que está quente para Swing Trade.
""")

col1, col2 = st.columns(2)
qtd_bdrs = col1.slider("Quantidade de BDRs para analisar:", 10, 80, 40)
score_min = col2.slider("Score Mínimo (Sensibilidade):", 10, 50, 20)

if st.button("🔍 Iniciar Varredura de Mercado", type="primary"):
    monitor = SwingTradeMonitor()
    
    # 1. Obter Lista
    status = st.empty()
    status.info("Obtendo lista atualizada da B3...")
    bdrs = monitor.obter_bdrs_brapi(qtd_bdrs)
    
    # 2. Loop de Análise
    resultados = []
    progresso = st.progress(0)
    
    for i, bdr in enumerate(bdrs):
        pct = (i+1)/len(bdrs)
        progresso.progress(pct)
        status.text(f"Analisando {bdr} ({i+1}/{len(bdrs)})... Traduzindo notícias...")
        
        try:
            res = monitor.analisar_ativo(bdr)
            if res and res['Score'] >= score_min:
                resultados.append(res)
        except Exception as e:
            continue
            
    progresso.empty()
    status.empty()
    
    # 3. Exibição dos Resultados
    if resultados:
        df = pd.DataFrame(resultados)
        
        # Ordenação inteligente
        df = df.sort_values(['Score', 'Preço (US)'], ascending=[False, False])
        
        st.success(f"✅ {len(df)} Oportunidades Encontradas!")
        
        # Configuração da Tabela Profissional
        st.data_editor(
            df,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Fonte", display_text="Ler Notícia"
                ),
                "Score": st.column_config.ProgressColumn(
                    "Força (0-100)",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "Preço (US)": st.column_config.NumberColumn(
                    "Preço (US$)",
                    format="$ %.2f"
                ),
                "BDR": st.column_config.TextColumn("Ativo BR"),
            },
            hide_index=True,
            use_container_width=True,
            height=500
        )
        
        # Área de Destaques (Texto)
        st.markdown("### 📝 Resumo Executivo")
        tops = df.head(3)
        for _, row in tops.iterrows():
            st.info(f"**{row['BDR']} ({row['US']})**: {row['Ação']} - {row['Motivo']}. \n\n*Notícia: {row['Manchete']}*")
            
    else:
        st.warning("Nenhuma oportunidade relevante encontrada com os filtros atuais.")
