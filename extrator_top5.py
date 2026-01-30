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
st.set_page_config(page_title="Robô Extrator V5.1 (DIAGNÓSTICO)", page_icon="🚨", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": { "slug": "lotep", "nome_aba": "LOTEP_TOP5" },
    "CAMINHODASORTE": { "slug": "caminho-da-sorte", "nome_aba": "CAMINHO_TOP5" },
    "MONTECAI": { "slug": "nordeste-monte-carlos", "nome_aba": "MONTE_TOP5" },
    "FEDERAL": { "slug": "nordeste-monte-carlos", "nome_aba": "FEDERAL_TOP5" }
}

# =============================================================================
# FUNÇÕES DE CONEXÃO (SEM FILTRO DE ERRO)
# =============================================================================
def conectar_planilha_debug(nome_aba):
    st.write(f"🔌 Tentando conectar na aba: **{nome_aba}**...")
    
    if "gcp_service_account" not in st.secrets:
        st.error("❌ ERRO: Secrets 'gcp_service_account' não encontrado!")
        return None

    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        st.write("✅ Planilha 'CentralBichos' aberta com sucesso.")
        
        try:
            ws = sh.worksheet(nome_aba)
            st.write(f"✅ Aba '{nome_aba}' encontrada!")
            return ws
        except gspread.WorksheetNotFound:
            st.warning(f"⚠️ Aba '{nome_aba}' não existe. Tentando criar...")
            try:
                ws = sh.add_worksheet(title=nome_aba, rows=1000, cols=10)
                ws.append_row(["DATA", "HORARIO", "P1", "P2", "P3", "P4", "P5"])
                st.success(f"✅ Aba '{nome_aba}' criada com sucesso!")
                return ws
            except Exception as e_create:
                st.error(f"❌ ERRO CRÍTICO: Não foi possível criar a aba. O robô tem permissão de 'Editor'? Erro: {e_create}")
                return None
    except Exception as e:
        st.error(f"❌ ERRO DE CONEXÃO GERAL: {e}")
        return None

# =============================================================================
# FUNÇÃO DE RASPAGEM (ESTRATÉGIA MONTE CARLOS)
# =============================================================================
def montar_url_correta(banca_key, data_alvo):
    config = CONFIG_BANCAS[banca_key]
    slug = config['slug']
    base = "https://www.resultadofacil.com.br"
    hoje = date.today()
    delta = (hoje - data_alvo).days
    
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_dia_completo(banca_key, data_alvo):
    url = montar_url_correta(banca_key, data_alvo)
    st.info(f"🔎 Acessando URL: {url}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200: return [], f"Erro HTTP {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados_do_dia = []
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')

        for tabela in tabelas:
            texto_tab = tabela.get_text()
            
            # --- FEDERAL VIA MONTE CARLOS ---
            if banca_key == "FEDERAL":
                # Procura qualquer menção a FEDERAL no cabeçalho ou no título anterior
                cabecalho = tabela.find_previous(string=re.compile(r"FEDERAL", re.IGNORECASE))
                
                # Se não achou "FEDERAL" escrito perto da tabela, IGNORA.
                if not cabecalho: continue
                
                # Se achou, assume que é o sorteio das 19h
                horario = "19:00"
            
            # --- OUTRAS BANCAS ---
            else:
                if "Prêmio" not in texto_tab and "1º" not in texto_tab: continue
                # Se pediu outra banca, ignora se tiver FEDERAL no nome
                header_check = tabela.find_previous(string=re.compile(r"FEDERAL", re.IGNORECASE))
                if header_check: continue

                horario = "00:00"
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m: 
                        raw = m.group(1).strip()
                        if ':' in raw: horario = raw
                        elif 'h' in raw: horario = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: horario = raw.strip().zfill(2) + ":00"

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
                        if 1 <= posicao <= 5: bichos.append(int(grupo_txt))
            
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
    except Exception as e: return [], f"Erro Fatal: {e}"

# =============================================================================
# INTERFACE
# =============================================================================
st.title("🚨 Robô V5.1 - MODO DIAGNÓSTICO")
st.warning("Este modo mostra erros técnicos na tela. Use para descobrir por que não está gravando.")

c1, c2 = st.columns(2)
with c1:
    banca = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
with c2:
    data_sel = st.date_input("Data para Extrair:", date.today())

st.markdown("---")
if st.button("🚀 EXECUTAR DIAGNÓSTICO", type="primary"):
    
    # 1. TESTE DE CONEXÃO
    ws = conectar_planilha_debug(CONFIG_BANCAS[banca]['nome_aba'])
    
    if ws:
        # 2. TESTE DE RASPAGEM
        with st.spinner(f"Varrendo site..."):
            dados, msg = raspar_dia_completo(banca, data_sel)
            
            if dados:
                st.success(f"📦 DADOS ENCONTRADOS NA MEMÓRIA: {len(dados)}")
                st.write(dados) # MOSTRA O DADO NA TELA
                
                # 3. TESTE DE GRAVAÇÃO
                st.write("💾 Tentando gravar na planilha agora...")
                novos = 0
                for jogo in dados:
                    try:
                        row = [jogo['data'], jogo['horario']] + jogo['premios']
                        st.write(f"📝 Escrevendo linha: {row}")
                        ws.append_row(row)
                        st.success("✅ Linha gravada com sucesso!")
                        novos += 1
                    except Exception as e_write:
                        st.error(f"❌ ERRO AO GRAVAR LINHA: {e_write}")
                
                if novos > 0:
                    st.balloons()
            else:
                st.error(f"❌ Nada encontrado no site. Mensagem: {msg}")
    else:
        st.error("❌ O processo parou porque não conseguimos conectar na planilha.")
