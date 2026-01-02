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
st.set_page_config(page_title="Scanner Pro BDRs", page_icon="💹", layout="wide")

# --- SEGREDOS ---
FINNHUB_KEY = st.secrets.get("FINNHUB_API_KEY", "d4uouchr01qnm7pnasq0d4uouchr01qnm7pnasqg")
BRAPI_TOKEN = st.secrets.get("BRAPI_API_TOKEN", "iExnKM1xcbQcYL3cNPhPQ3")

# --- CLASSE MONITOR ---
class SwingTradeMonitor:
    def __init__(self):
        # Instancia o tradutor
        self.translator = GoogleTranslator(source='auto', target='pt')
        self.ticker_map = self._carregar_mapa_bdr_us()
        
    def _carregar_mapa_bdr_us(self):
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
        """Traduz texto para PT-BR com tratamento de erro"""
        if not texto or len(texto) < 3: return ""
        try:
            return self.translator.translate(texto)
        except:
            return texto # Retorna original se falhar a API de tradução

    def obter_bdrs_brapi(self, limite=50):
        try:
            url = f"https://brapi.dev/api/quote/list?token={BRAPI_TOKEN}"
            r = requests.get(url, timeout=10)
            data = r.json().get('stocks', [])
            df = pd.DataFrame(data)
            df = df[df['stock'].str.contains(r'(31|32|33|34|35|39)$')]
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            return df.sort_values('volume', ascending=False).head(limite)['stock'].tolist()
        except:
            return list(self.ticker_map.values())

    def converter_para_us(self, bdr):
        bdr_clean = bdr.replace('.SA', '')
        for us, br in self.ticker_map.items():
            if br == bdr_clean: return us
        return re.sub(r'\d+$', '', bdr_clean)

    def get_yahoo_data(self, ticker_us):
        try:
            stock = yf.Ticker(ticker_us)
            try: cal = stock.calendar; earn_date = cal.get('Earnings Date', [None])[0] if cal else None
            except: earn_date = None
            try: info = stock.info; ex_div = info.get('exDividendDate'); div_yield = info.get('dividendYield')
            except: ex_div, div_yield = None, None
            
            hist = stock.history(period='1mo')
            trend = "Lateral"
            price = 0
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                sma20 = hist['Close'].mean()
                trend = "Alta 📈" if price > sma20 else "Baixa 📉"
            
            return {'earnings': earn_date, 'ex_div': ex_div, 'yield': div_yield, 'trend': trend, 'price': price}
        except: return None

    def get_news(self, ticker_us):
        try:
            hj = datetime.now().strftime('%Y-%m-%d')
            inicio = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/company-news?symbol={ticker_us}&from={inicio}&to={hj}&token={FINNHUB_KEY}'
            r = requests.get(url, timeout=5)
            return r.json() if r.status_code == 200 else []
        except: return []

    def gerar_analise_compra(self, gatilho, score):
        """Gera a explicação do porquê comprar"""
        if "Balanço" in gatilho:
            return "Alta volatilidade esperada. Oportunidade de captura de movimento forte pós-resultado."
        elif "Data Com" in gatilho:
            return "Entrada estratégica para garantir o recebimento de dividendos (Yield atraente)."
        elif "Upgrade" in gatilho or "Buy" in gatilho:
            return "Bancos e analistas revisaram a nota para cima, indicando fluxo comprador institucional."
        elif "Record" in gatilho or "Growth" in gatilho:
            return "Empresa reportando crescimento ou recordes, validando a tendência de alta."
        elif "Approval" in gatilho:
            return "Aprovação regulatória (ex: FDA) destrava valor fundamental na ação."
        else:
            return "Fluxo de notícias extremamente positivo sugere otimismo do mercado."

    def analisar_ativo(self, bdr):
        ticker_us = self.converter_para_us(bdr)
        if not ticker_us: return None
        
        y_data = self.get_yahoo_data(ticker_us)
        if not y_data: return None
        
        noticias = self.get_news(ticker_us)
        
        score = 0
        eventos = []
        manchete_top = ""
        resumo_top = ""
        fonte_top = ""
        link_top = ""
        gatilho_principal = ""
        
        # 1. Earnings (50 pts)
        if y_data['earnings']:
            dias = (pd.to_datetime(y_data['earnings']).replace(tzinfo=None) - datetime.now()).days
            if 0 <= dias <= 15:
                score += 50
                gatilho_principal = "Balanço Próximo"
                eventos.append(f"Balanço em {dias}d")
        
        # 2. Dividendos (30 pts)
        if y_data['ex_div']:
            dias = (datetime.fromtimestamp(y_data['ex_div']) - datetime.now()).days
            if 0 <= dias <= 10:
                score += 30
                if not gatilho_principal: gatilho_principal = "Data Com (Dividendos)"
                y_val = f"{(y_data['yield']*100):.1f}%" if y_data['yield'] else "?"
                eventos.append(f"Div (Y: {y_val})")

        # 3. Notícias (até 20 pts)
        keyword_map = {
            'upgrade': 'Upgrade de Analista', 'buy': 'Recomendação de Compra', 
            'record': 'Recorde Histórico', 'growth': 'Crescimento', 
            'approval': 'Aprovação Regulatória', 'soar': 'Disparada', 'jump': 'Salto'
        }

        for n in noticias[:15]:
            texto = f"{n['headline']} {n['summary']}".lower()
            
            for k, v in keyword_map.items():
                if k in texto:
                    blob = TextBlob(texto)
                    if blob.sentiment.polarity > 0.1:
                        score += 5
                        if not manchete_top:
                            manchete_top = n['headline']
                            resumo_top = n['summary']
                            fonte_top = n.get('source', 'Finnhub')
                            link_top = n['url']
                            if not gatilho_principal: gatilho_principal = v
            
            if score >= 80: break

        if score < 20: return None 

        acao = "COMPRAR AGORA 🔴" if score >= 60 else "MONITORAR 🟠" if score >= 40 else "OBSERVAR 🟡"
        
        # Tradução Final
        if manchete_top:
            manchete_top = self.traduzir(manchete_top)
            if resumo_top:
                resumo_top = self.traduzir(resumo_top)
        else:
            manchete_top = "Movimento técnico/fundamental detectado"
            resumo_top = "Nenhuma notícia específica recente, mas indicadores técnicos ou calendário apontam oportunidade."
            fonte_top = "Análise Técnica"

        analise_robo = self.gerar_analise_compra(gatilho_principal, score)

        return {
            "BDR": bdr,
            "US": ticker_us,
            "Preço": y_data['price'],
            "Tendência": y_data['trend'],
            "Score": min(score, 100),
            "Ação": acao,
            "Manchete": manchete_top,
            "Resumo": resumo_top,
            "Fonte": fonte_top,
            "Link": link_top,
            "Análise": analise_robo,
            "Gatilho": gatilho_principal if gatilho_principal else "Fluxo Positivo"
        }

# --- INTERFACE ---
st.title("🌐 Scanner BDR: Notícias & Oportunidades")
st.markdown("### Monitoramento Fundamentalista em Tempo Real (PT-BR)")

with st.sidebar:
    st.header("Filtros")
    qtd = st.slider("Ativos para analisar:", 10, 60, 30)
    filtro_score = st.slider("Score Mínimo:", 0, 50, 20)

if st.button("🚀 Iniciar Scanner", type="primary"):
    monitor = SwingTradeMonitor()
    status = st.empty()
    bar = st.progress(0)
    
    status.info("Buscando lista de BDRs...")
    bdrs = monitor.obter_bdrs_brapi(qtd)
    
    resultados = []
    
    for i, bdr in enumerate(bdrs):
        bar.progress((i+1)/len(bdrs))
        status.text(f"Analisando {bdr}... Traduzindo dados...")
        try:
            res = monitor.analisar_ativo(bdr)
            if res and res['Score'] >= filtro_score:
                resultados.append(res)
        except: continue
            
    bar.empty()
    status.empty()
    
    if resultados:
        df = pd.DataFrame(resultados)
        df = df.sort_values(['Score'], ascending=False)
        
        st.success(f"{len(df)} Oportunidades encontradas!")
        
        # TABELA RESUMIDA
        st.subheader("📋 Tabela Geral")
        st.data_editor(
            df[['BDR', 'Preço', 'Score', 'Ação', 'Manchete', 'Fonte', 'Link']],
            column_config={
                "Link": st.column_config.LinkColumn("Ver", display_text="Original"),
                "Score": st.column_config.ProgressColumn("Força", format="%d", min_value=0, max_value=100),
                "Preço": st.column_config.NumberColumn("Preço ($)", format="$ %.2f"),
                "Manchete": st.column_config.TextColumn("Última Notícia (Traduzida)", width="large"),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # DETALHES EXPANDIDOS (CARTÕES)
        st.markdown("---")
        st.subheader("🕵️‍♂️ Detalhes das Oportunidades (Análise Profunda)")
        
        for index, row in df.iterrows():
            cor_card = "red" if "COMPRAR" in row['Ação'] else "orange" if "MONITORAR" in row['Ação'] else "blue"
            
            with st.expander(f"{row['BDR']} ({row['US']}) - {row['Ação']} (Score: {row['Score']})", expanded=(index < 2)):
                c1, c2 = st.columns([2, 1])
                
                with c1:
                    st.markdown(f"**📢 Notícia:** {row['Manchete']}")
                    st.caption(f"Fonte: {row['Fonte']}")
                    st.info(f"**Resumo:** {row['Resumo']}")
                    
                with c2:
                    st.markdown(f"**🎯 Por que é compra?**")
                    st.write(f"_{row['Análise']}_")
                    st.metric("Tendência", row['Tendência'])
                    st.markdown(f"[Ler notícia original]({row['Link']})")
    else:
        st.warning("Nenhuma oportunidade encontrada.")
