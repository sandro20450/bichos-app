import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
st.set_page_config(page_title="Robô Extrator TOP 5", page_icon="🏗️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": {
        "slug": "lotep",
        "nome_aba": "LOTEP_TOP5"
    },
    "CAMINHODASORTE": {
        "slug": "caminho-da-sorte",
        "nome_aba": "CAMINHO_TOP5"
    },
    "MONTECAI": {
        "slug": "nordeste-monte-carlos",
        "nome_aba": "MONTE_TOP5"
    }
}

# =============================================================================
# FUNÇÕES
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try:
            ws = sh.worksheet(nome_aba)
        except:
            ws = sh.add_worksheet(title=nome_aba, rows=1000, cols=10)
            ws.append_row(["DATA", "HORARIO", "P1", "P2", "P3", "P4", "P5"])
        return ws
    return None

def montar_url_correta(slug, data_alvo):
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    
    if delta == 0:
        return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1:
        return f"{base}/resultados-{slug}-de-ontem"
    else:
        data_str = data_alvo.strftime("%Y-%m-%d")
        return f"{base}/resultados-{slug}-do-dia-{data_str}"

def raspar_dia_completo(banca_key, data_alvo):
    slug = CONFIG_BANCAS[banca_key]['slug']
    url = montar_url_correta(slug, data_alvo)
    
    st.info(f"🔎 Robô acessando: {url}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code != 200: 
            return [], f"Erro HTTP {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        if "Não foram encontrados resultados" in soup.get_text():
            return [], "Site diz: Sem resultados para esta data."

        tabelas = soup.find_all('table')
        resultados_do_dia = []
        
        # Padrão para pegar "HH:MM" ou "HHh" (ex: 18h)
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h)')

        for tabela in tabelas:
            texto_tab = tabela.get_text()
            if "Prêmio" in texto_tab or "1º" in texto_tab:
                
                horario = "00:00"
                # Procura hora no texto anterior à tabela
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m: 
                        raw_hora = m.group(1)
                        # Se achou "18h", converte para "18:00"
                        if 'h' in raw_hora and ':' not in raw_hora:
                            horario = raw_hora.replace('h', '').zfill(2) + ":00"
                        else:
                            horario = raw_hora
                
                bichos = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 3:
                        premio_txt = cols[0].get_text().strip()
                        grupo_txt = cols[2].get_text().strip()
                        
                        if not grupo_txt.isdigit(): continue
                        
                        nums = re.findall(r'\d+', premio_txt)
                        if nums:
                            posicao = int(nums[0])
                            if 1 <= posicao <= 5:
                                bichos.append(int(grupo_txt))
                
                if len(bichos) >= 5:
                    top5 = bichos[:5]
                    
                    ja_tem = False
                    for x in resultados_do_dia:
                        if x['horario'] == horario: ja_tem = True
                    
                    if not ja_tem:
                        resultados_do_dia.append({
                            "data": data_alvo.strftime("%Y-%m-%d"),
                            "horario": horario,
                            "premios": top5
                        })
                    
        return resultados_do_dia, "Sucesso"
        
    except Exception as e:
        return [], f"Erro Fatal: {e}"

# =============================================================================
# INTERFACE
# =============================================================================
st.title("🏗️ Robô Extrator V2.2 (Fix 18h)")

c1, c2 = st.columns(2)
with c1:
    banca = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
with c2:
    data_sel = st.date_input("Data para Extrair:", date.today())

if st.button("🚀 INICIAR EXTRAÇÃO", type="primary"):
    ws = conectar_planilha(CONFIG_BANCAS[banca]['nome_aba'])
    if not ws:
        st.error("Erro Conexão Planilha (Verifique Secrets).")
    else:
        with st.spinner("Analisando página..."):
            dados, msg = raspar_dia_completo(banca, data_sel)
            
            if dados:
                st.success(f"📦 Encontrados {len(dados)} sorteios!")
                
                try:
                    existentes = ws.get_all_values()
                    chaves_existentes = [f"{row[0]}|{row[1]}" for row in existentes if len(row) > 1]
                except: chaves_existentes = []
                
                novos = 0
                for jogo in dados:
                    chave = f"{jogo['data']}|{jogo['horario']}"
                    if chave not in chaves_existentes:
                        ws.append_row([jogo['data'], jogo['horario']] + jogo['premios'])
                        novos += 1
                
                if novos > 0:
                    st.toast(f"✅ {novos} Sorteios salvos na nuvem!", icon="☁️")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Todos os sorteios encontrados JÁ estavam salvos.")
                
                st.json(dados)
            else:
                st.error(f"Nada encontrado. Msg: {msg}")
