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
st.set_page_config(page_title="Robô Extrator V6.0 (Chrome Fake)", page_icon="🕵️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": { "slug": "lotep", "nome_aba": "LOTEP_TOP5", "tipo_url": "dinamica" },
    "CAMINHODASORTE": { "slug": "caminho-da-sorte", "nome_aba": "CAMINHO_TOP5", "tipo_url": "dinamica" },
    "MONTECAI": { "slug": "nordeste-monte-carlos", "nome_aba": "MONTE_TOP5", "tipo_url": "dinamica" },
    "FEDERAL": { "slug": "nordeste-monte-carlos", "nome_aba": "FEDERAL_TOP5", "tipo_url": "federal_mc" }
}

# =============================================================================
# FUNÇÕES DE CONEXÃO
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try:
            ws = sh.worksheet(nome_aba)
            return ws
        except:
            # Cria aba nova se não existir
            ws = sh.add_worksheet(title=nome_aba, rows=1000, cols=10)
            ws.update(range_name='A1:G1', values=[["DATA", "HORARIO", "P1", "P2", "P3", "P4", "P5"]])
            return ws
    return None

def gravar_na_forca(ws, dados, forcar=False):
    # Pega todos os dados da coluna A para saber onde escrever
    coluna_a = ws.col_values(1)
    prox_linha = len(coluna_a) + 1
    
    # Lista de chaves já existentes (Data|Hora)
    if not forcar:
        raw_data = ws.get_all_values()
        chaves_existentes = [f"{row[0]}|{row[1]}" for row in raw_data if len(row) > 1]
    else:
        chaves_existentes = []

    novos = 0
    for jogo in dados:
        chave = f"{jogo['data']}|{jogo['horario']}"
        
        if (chave not in chaves_existentes) or forcar:
            linha_dados = [jogo['data'], jogo['horario']] + jogo['premios']
            
            # ESCREVE NA COORDENADA EXATA (Evita erro da linha 1000)
            range_name = f"A{prox_linha}:G{prox_linha}"
            ws.update(range_name=range_name, values=[linha_dados])
            
            st.success(f"✅ Gravado na linha {prox_linha}: {chave}")
            prox_linha += 1
            novos += 1
        else:
            st.info(f"Ignorado (Duplicado): {chave}")
    
    return novos

# =============================================================================
# RASPAGEM (COM CAMUFLAGEM)
# =============================================================================
def montar_url(banca_key, data_alvo):
    config = CONFIG_BANCAS[banca_key]
    slug = config['slug']
    base = "https://www.resultadofacil.com.br"
    
    # Federal usa a URL da Monte Carlos
    
    hoje = date.today()
    delta = (hoje - data_alvo).days
    
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_dados(banca_key, data_alvo):
    url = montar_url(banca_key, data_alvo)
    st.info(f"🔎 Visitando: {url}")
    
    # --- CAMUFLAGEM DE NAVEGADOR (CRUCIAL PARA CAMINHO DA SORTE) ---
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200: return [], f"Bloqueio ou Erro {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Verifica se o site retornou erro padrão
        if "Não foram encontrados resultados" in soup.get_text():
            return [], "Site retornou vazio (Verifique a data)."

        tabelas = soup.find_all('table')
        resultados = []
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        
        st.write(f"Tabelas encontradas na página: {len(tabelas)}") # Debug

        for tabela in tabelas:
            texto_tab = tabela.get_text()
            horario = "00:00"
            eh_federal = False
            
            # --- DETECÇÃO DE FEDERAL ---
            # Procura "FEDERAL" no bloco da tabela
            # Às vezes está no 'thead', às vezes num 'div' anterior
            header_node = tabela.find_previous(string=re.compile(r"Resultado do dia|FEDERAL", re.IGNORECASE))
            if header_node:
                bloco_full = header_node.parent.parent.get_text().upper()
                if "FEDERAL" in bloco_full: eh_federal = True

            # LÓGICA DE FILTRO
            if banca_key == "FEDERAL":
                if not eh_federal: continue # Se quer federal e não é, pula
                horario = "19:00"
            else:
                if eh_federal: continue # Se quer lotep/caminho e é federal, pula
                if "Prêmio" not in texto_tab and "1º" not in texto_tab: continue
                
                # Tenta achar hora
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m: 
                        raw = m.group(1).strip()
                        if ':' in raw: horario = raw
                        elif 'h' in raw: horario = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: horario = raw.strip().zfill(2) + ":00"

            # EXTRAIR BICHOS
            bichos = []
            linhas = tabela.find_all('tr')
            for linha in linhas:
                cols = linha.find_all('td')
                if len(cols) >= 3:
                    premio = cols[0].get_text().strip()
                    grupo = cols[2].get_text().strip()
                    if grupo.isdigit():
                        # Limpa texto do premio (ex: "1º Premio" -> "1")
                        nums = re.findall(r'\d+', premio)
                        if nums:
                            pos = int(nums[0])
                            if 1 <= pos <= 5: bichos.append(int(grupo))
            
            if len(bichos) >= 5:
                # Evita duplicatas do mesmo horario na mesma pagina
                ja_tem = False
                for x in resultados:
                    if x['horario'] == horario: ja_tem = True
                
                if not ja_tem:
                    resultados.append({
                        "data": data_alvo.strftime("%Y-%m-%d"),
                        "horario": horario,
                        "premios": bichos[:5]
                    })

        return resultados, "Sucesso"

    except Exception as e: return [], f"Erro Python: {e}"

# =============================================================================
# APP
# =============================================================================
st.title("🕵️ Extrator V6.0 (Camuflado)")
st.caption("Correções: Bloqueio Caminho da Sorte & Erro de Linha 1000")

c1, c2 = st.columns(2)
with c1: banca = st.selectbox("Banca:", list(CONFIG_BANCAS.keys()))
with c2: data_sel = st.date_input("Data:", date.today())

st.markdown("---")
forcar = st.checkbox("⚠️ Forçar Gravação (Ignora duplicatas)", value=True)

if st.button("🚀 INICIAR", type="primary"):
    ws = conectar_planilha(CONFIG_BANCAS[banca]['nome_aba'])
    if ws:
        with st.spinner("Robô trabalhando..."):
            dados, msg = raspar_dados(banca, data_sel)
            
            if dados:
                st.write(f"📦 Encontrados: {len(dados)}")
                st.json(dados)
                
                novos = gravar_na_forca(ws, dados, forcar)
                
                if novos > 0:
                    st.balloons()
                    st.toast("Sucesso! Planilha atualizada.")
                else:
                    st.warning("Nada novo para gravar.")
            else:
                st.error(f"Nada encontrado. ({msg})")
    else:
        st.error("Erro na Planilha.")
