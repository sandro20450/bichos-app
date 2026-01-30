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
st.set_page_config(page_title="Robô Extrator V5.0 (Estratégia MC)", page_icon="🏗️", layout="wide")

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
    },
    "FEDERAL": {
        # TRUQUE DE MESTRE: Usamos o slug da Monte Carlos para achar a Federal!
        "slug": "nordeste-monte-carlos", 
        "nome_aba": "FEDERAL_TOP5"
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

def montar_url_correta(banca_key, data_alvo):
    config = CONFIG_BANCAS[banca_key]
    slug = config['slug']
    
    # Montagem padrão de URL (que funciona perfeitamente para Monte Carlos)
    base = "https://www.resultadofacil.com.br"
    hoje = date.today()
    delta = (hoje - data_alvo).days
    
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else:
        data_str = data_alvo.strftime("%Y-%m-%d")
        return f"{base}/resultados-{slug}-do-dia-{data_str}"

def raspar_dia_completo(banca_key, data_alvo):
    url = montar_url_correta(banca_key, data_alvo)
    st.info(f"🔎 Robô acessando: {url}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200: return [], f"Erro HTTP {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        if "Não foram encontrados resultados" in soup.get_text():
            return [], "Site diz: Sem resultados para esta data."

        tabelas = soup.find_all('table')
        resultados_do_dia = []
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')

        for tabela in tabelas:
            texto_tab = tabela.get_text()
            
            # --- LÓGICA FEDERAL (ESTRATÉGIA MONTE CARLOS) ---
            if banca_key == "FEDERAL":
                # Procura o cabeçalho "Resultado do dia..."
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                
                eh_federal = False
                if cabecalho and "FEDERAL" in cabecalho.upper():
                    eh_federal = True
                
                # Se NÃO tiver a palavra FEDERAL no título, IGNORA (pois é sorteio normal da Monte Carlos)
                if not eh_federal: continue
                
                # Se achou, fixa o horário
                horario = "19:00"
            
            # --- LÓGICA OUTRAS BANCAS ---
            else:
                if "Prêmio" not in texto_tab and "1º" not in texto_tab: continue
                
                # Filtro Anti-Federal (Se pedir Monte Carlos, ignora a Federal)
                header_check = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if header_check and "FEDERAL" in header_check.upper(): continue

                horario = "00:00"
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m: 
                        raw = m.group(1).strip()
                        if ':' in raw: horario = raw
                        elif 'h' in raw: horario = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: horario = raw.strip().zfill(2) + ":00"

            # EXTRAÇÃO DOS NÚMEROS
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
st.title("🏗️ Robô Extrator V5.0 (Estratégia MC)")
st.caption("Suporta: Lotep, Caminho, Monte e FEDERAL (via Monte Carlos)")

c1, c2 = st.columns(2)
with c1:
    banca = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
with c2:
    data_sel = st.date_input("Data para Extrair:", date.today())

st.markdown("---")
col_chk, col_btn = st.columns([1, 1])
with col_chk:
    forcar = st.checkbox("⚠️ FORÇAR GRAVAÇÃO", value=True, help="Deixe marcado para garantir a gravação.")

if col_btn.button("🚀 INICIAR EXTRAÇÃO", type="primary"):
    ws = conectar_planilha(CONFIG_BANCAS[banca]['nome_aba'])
    if not ws:
        st.error("Erro Conexão Planilha (Verifique Secrets).")
    else:
        with st.spinner(f"Varrendo dados..."):
            dados, msg = raspar_dia_completo(banca, data_sel)
            
            if dados:
                st.success(f"📦 Resultado Encontrado: {len(dados)}")
                st.json(dados) # Mostra o JSON bonito na tela
                
                try:
                    existentes = ws.get_all_values()
                    chaves_existentes = [f"{row[0]}|{row[1]}" for row in existentes if len(row) > 1]
                except: chaves_existentes = []
                
                novos = 0
                for jogo in dados:
                    chave = f"{jogo['data']}|{jogo['horario']}"
                    
                    if (chave not in chaves_existentes) or forcar:
                        ws.append_row([jogo['data'], jogo['horario']] + jogo['premios'])
                        novos += 1
                
                if novos > 0:
                    st.toast(f"✅ Salvo com sucesso!", icon="☁️")
                    time.sleep(1)
                    st.rerun()
                elif novos == 0 and not forcar:
                    st.warning("Dado já existia na planilha.")
                
            else:
                st.error(f"Nada encontrado. Msg: {msg}")
                if banca == "FEDERAL":
                    st.info("O Robô buscou na página da Monte Carlos por uma tabela com nome 'FEDERAL'. Verifique se a data escolhida tem esse sorteio.")
