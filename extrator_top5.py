import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date
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

def raspar_dia_completo(banca_key, data_alvo):
    data_str = data_alvo.strftime("%Y-%m-%d")
    slug = CONFIG_BANCAS[banca_key]['slug']
    
    # URL Padrão: https://www.resultadofacil.com.br/resultados-lotep-de-2024-01-28
    url = f"https://www.resultadofacil.com.br/resultados-{slug}-de-{data_str}"
    
    # Se for hoje, tenta URL específica as vezes necessária
    if data_alvo == date.today():
        # Mas geralmente o site redireciona a data de hoje para /hoje, então vamos testar a URL data primeiro
        pass

    st.write(f"🔍 Tentando acessar: {url}") # Debug visual para você

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code != 200: 
            return [], f"Erro HTTP {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Verifica se a página diz "Não foram encontrados resultados"
        if "Não foram encontrados resultados" in soup.get_text():
            return [], "Site diz: Sem resultados para esta data."

        tabelas = soup.find_all('table')
        resultados_do_dia = []
        
        for tabela in tabelas:
            # Critério mais flexível para achar tabela de resultado
            texto_tab = tabela.get_text()
            if "Prêmio" in texto_tab or "1º" in texto_tab:
                
                # Tenta achar o horário
                horario = "00:00"
                # Procura no container anterior (título do sorteio)
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev:
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario = m.group(1)
                
                bichos = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 3:
                        premio = cols[0].get_text().strip()
                        grupo = cols[2].get_text().strip() # Assumindo coluna 3 é grupo
                        
                        # Validação forte de grupo (tem que ser numérico)
                        if not grupo.isdigit(): continue
                        
                        # Filtra 1 a 5
                        # Pega o número do prêmio (ex: "1º" -> "1")
                        nums = re.findall(r'\d+', premio)
                        if nums:
                            posicao = int(nums[0])
                            if 1 <= posicao <= 5:
                                bichos.append(int(grupo))
                
                # Se pegou 5 bichos, salva
                if len(bichos) >= 5:
                    # Garante que pegou na ordem certa (a lista append segue a ordem da tabela)
                    top5 = bichos[:5]
                    
                    # Evita duplicatas de horário na mesma extração
                    ja_tem = False
                    for r in resultados_do_dia:
                        if r['horario'] == horario: ja_tem = True
                    
                    if not ja_tem:
                        resultados_do_dia.append({
                            "data": data_str,
                            "horario": horario,
                            "premios": top5
                        })
                    
        return resultados_do_dia, "Sucesso"
        
    except Exception as e:
        return [], f"Erro Fatal: {e}"

# =============================================================================
# INTERFACE
# =============================================================================
st.title("🏗️ Robô Extrator V2.0")

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
                
                # Check de duplicidade simples
                try:
                    existentes = ws.get_all_values()
                    # Cria lista de chaves unicas (Data+Horario)
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
                    st.warning("Todos os sorteios encontrados já estavam salvos.")
                
                st.write("Visualização do que foi encontrado:")
                st.json(dados)
            else:
                st.error(f"Nada encontrado. Msg: {msg}")
