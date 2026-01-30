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
st.set_page_config(page_title="Robô Extrator V4.2 (Mode Force)", page_icon="🏗️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": {
        "slug": "lotep",
        "nome_aba": "LOTEP_TOP5",
        "tipo_url": "dinamica"
    },
    "CAMINHODASORTE": {
        "slug": "caminho-da-sorte",
        "nome_aba": "CAMINHO_TOP5",
        "tipo_url": "dinamica"
    },
    "MONTECAI": {
        "slug": "nordeste-monte-carlos",
        "nome_aba": "MONTE_TOP5",
        "tipo_url": "dinamica"
    },
    "FEDERAL": {
        "slug": "federal",
        "nome_aba": "FEDERAL_TOP5",
        "tipo_url": "estatica",
        "url_fixa": "https://www.resultadofacil.com.br/ultimos-resultados-da-federal"
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
    if config.get("tipo_url") == "estatica":
        return config["url_fixa"]
    slug = config['slug']
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
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
        
        if CONFIG_BANCAS[banca_key].get("tipo_url") == "dinamica":
            if "Não foram encontrados resultados" in soup.get_text():
                return [], "Site diz: Sem resultados para esta data."

        tabelas = soup.find_all('table')
        resultados_do_dia = []
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        data_fmt_br = data_alvo.strftime("%d/%m/%Y")

        for tabela in tabelas:
            texto_tab = tabela.get_text()
            
            # --- LÓGICA FEDERAL ---
            if banca_key == "FEDERAL":
                cabecalho = tabela.find_previous(string=re.compile(r"FEDERAL", re.IGNORECASE))
                if not cabecalho: continue
                
                # Verifica se a data alvo está no bloco do cabeçalho
                bloco_texto = cabecalho.parent.parent.get_text()
                if data_fmt_br not in bloco_texto: continue
                
                horario = "19:00"
            
            # --- LÓGICA OUTRAS BANCAS ---
            else:
                if "Prêmio" not in texto_tab and "1º" not in texto_tab: continue
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
st.title("🏗️ Robô Extrator V4.2 (Mode Force)")
st.caption("Suporta: Lotep, Caminho, Monte Carlos e FEDERAL.")

c1, c2 = st.columns(2)
with c1:
    banca = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
with c2:
    data_sel = st.date_input("Data para Extrair:", date.today())

st.markdown("---")
col_chk, col_btn = st.columns([1, 1])
with col_chk:
    forcar = st.checkbox("⚠️ FORÇAR GRAVAÇÃO (Ignorar se já existe)", value=False, help="Marque isso se o robô achou o resultado mas não está salvando.")

if col_btn.button("🚀 INICIAR EXTRAÇÃO", type="primary"):
    ws = conectar_planilha(CONFIG_BANCAS[banca]['nome_aba'])
    if not ws:
        st.error("Erro Conexão Planilha (Verifique Secrets).")
    else:
        with st.spinner(f"Buscando dados da {banca}..."):
            dados, msg = raspar_dia_completo(banca, data_sel)
            
            if dados:
                st.success(f"📦 Encontrados {len(dados)} sorteios válidos na memória!")
                st.write("Dados extraídos:", dados) # Debug Visual
                
                try:
                    existentes = ws.get_all_values()
                    chaves_existentes = [f"{row[0]}|{row[1]}" for row in existentes if len(row) > 1]
                    # st.write("Chaves na Planilha:", chaves_existentes) # Debug (Descomente se precisar)
                except: chaves_existentes = []
                
                novos = 0
                for jogo in dados:
                    chave = f"{jogo['data']}|{jogo['horario']}"
                    
                    # LÓGICA DE GRAVAÇÃO (COM FORÇAR)
                    if (chave not in chaves_existentes) or forcar:
                        ws.append_row([jogo['data'], jogo['horario']] + jogo['premios'])
                        novos += 1
                        if forcar: st.warning(f"Gravado forçadamente: {chave}")
                    else:
                        st.info(f"Ignorado (Já existe): {chave}")
                
                if novos > 0:
                    st.toast(f"✅ {novos} Sorteios salvos na nuvem!", icon="☁️")
                    time.sleep(1)
                    st.rerun()
                elif novos == 0 and not forcar:
                    st.warning("Nenhum dado novo salvo. (Tente marcar 'Forçar Gravação' se achar que é erro).")
                
            else:
                st.error(f"Nada encontrado. Msg: {msg}")
                if banca == "FEDERAL":
                    st.info(f"O robô buscou pela data exata {data_sel.strftime('%d/%m/%Y')} na página da Federal.")
