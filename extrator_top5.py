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
        # URL de Hoje: resultados-lotep-de-hoje
        return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1:
        # URL de Ontem: resultados-lotep-de-ontem
        return f"{base}/resultados-{slug}-de-ontem"
    else:
        # URL Antiga: resultados-lotep-do-dia-2026-01-08
        # AQUI ESTAVA O ERRO: mudamos de '-de-' para '-do-dia-'
        data_str = data_alvo.strftime("%Y-%m-%d")
        return f"{base}/resultados-{slug}-do-dia-{data_str}"

def raspar_dia_completo(banca_key, data_alvo):
    slug = CONFIG_BANCAS[banca_key]['slug']
    url = montar_url_correta(slug, data_alvo)
    
    st.info(f"🔎 Robô acessando: {url}") # Mostra na tela para conferência

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
        
        for tabela in tabelas:
            texto_tab = tabela.get_text()
            # Busca tabelas que tenham "1º" ou "Prêmio"
            if "Prêmio" in texto_tab or "1º" in texto_tab:
                
                # Tenta achar o horário no bloco anterior
                horario = "00:00"
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev:
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario = m.group(1)
                
                bichos = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 3:
                        premio_txt = cols[0].get_text().strip()
                        grupo_txt = cols[2].get_text().strip()
                        
                        if not grupo_txt.isdigit(): continue
                        
                        # Extrai a posição do prêmio (1º, 2º...)
                        nums = re.findall(r'\d+', premio_txt)
                        if nums:
                            posicao = int(nums[0])
                            # Filtra apenas do 1 ao 5
                            # OBS: Se o site listar até o 10º, ignoramos do 6 pra cima
                            if 1 <= posicao <= 5:
                                bichos.append(int(grupo_txt))
                
                # Só salva se tiver encontrado pelo menos 5 bichos
                if len(bichos) >= 5:
                    top5 = bichos[:5] # Garante só os 5 primeiros
                    
                    # Evita duplicar horário no mesmo dia
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
st.title("🏗️ Robô Extrator V2.1 (Correção URL)")

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
