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
#CONFIGURAÇÕES
# =============================================================================
st.set_page_config(page_title="Robô Extrator TOP 5", page_icon="🏗️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": {
        "url_base": "https://www.resultadofacil.com.br/resultados-lotep-de-",
        "nome_aba": "LOTEP_TOP5"
    },
    "CAMINHODASORTE": {
        "url_base": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-",
        "nome_aba": "CAMINHO_TOP5"
    },
    "MONTECAI": {
        "url_base": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-",
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
            # Cria a aba se não existir
            ws = sh.add_worksheet(title=nome_aba, rows=1000, cols=10)
            ws.append_row(["DATA", "HORARIO", "P1", "P2", "P3", "P4", "P5"]) # Cabeçalho
        return ws
    return None

def raspar_dia_completo(banca_key, data_alvo):
    # Formata a URL: hoje -> resultados-lotep-de-hoje | data -> resultados-lotep-de-ontem ou data
    # Para simplificar, o site usa o formato YYYY-MM-DD na URL para dias passados
    data_str = data_alvo.strftime("%Y-%m-%d")
    url = f"{CONFIG_BANCAS[banca_key]['url_base']}{data_str}"
    
    # Ajuste para "hoje" se a data for hoje, pois a URL muda as vezes
    if data_alvo == date.today():
        # Tenta URL de hoje padrão do config original se necessário, mas o padrão data costuma funcionar
        pass 

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return [], f"Erro HTTP {r.status_code}"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        resultados_do_dia = [] # Lista de dicionarios
        
        for tabela in tabelas:
            if "1º" in tabela.get_text():
                # Tenta achar o horário
                horario = "00:00"
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev:
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario = m.group(1)
                
                # Extrair os 5 bichos
                bichos = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 3:
                        premio = cols[0].get_text().strip()
                        grupo = cols[2].get_text().strip()
                        
                        # Filtra apenas 1º ao 5º
                        valid_premios = ['1º', '2º', '3º', '4º', '5º', '1', '2', '3', '4', '5', 'Pri', 'Seg', 'Ter', 'Qua', 'Qui']
                        if any(p in premio for p in valid_premios):
                            # Correção LOTEP: Ignorar 6 a 10 se aparecerem na mesma tabela (raro, mas previne)
                            if "6" in premio or "7" in premio or "8" in premio or "9" in premio or "10" in premio:
                                continue
                                
                            if grupo.isdigit():
                                bichos.append(int(grupo))
                
                # Só salva se tiver pego os 5 bichos (Consistência)
                # Se pegar menos (ex: sorteio cancelado), ignoramos ou salvamos parcial? Melhor 5 para estatística.
                if len(bichos) >= 5:
                    # Pega só os 5 primeiros caso a tabela tenha mais
                    top5 = bichos[:5]
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
st.title("🏗️ Robô Extrator: Base de Dados TOP 5")
st.markdown("Use esta ferramenta para popular a planilha com os 5 prêmios de cada sorteio.")

c1, c2 = st.columns(2)
with c1:
    banca = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
with c2:
    data_sel = st.date_input("Data para Extrair:", date.today())

if st.button("🚀 INICIAR EXTRAÇÃO", type="primary"):
    ws = conectar_planilha(CONFIG_BANCAS[banca]['nome_aba'])
    if not ws:
        st.error("Erro ao conectar na planilha Google Sheets.")
    else:
        with st.spinner(f"Varrendo resultados de {banca} em {data_sel}..."):
            dados, msg = raspar_dia_completo(banca, data_sel)
            
            if dados:
                st.success(f"Encontrados {len(dados)} sorteios completos (1º ao 5º)!")
                
                # Verificar duplicidade simples (pelo horário) antes de salvar
                try:
                    existentes = ws.get_all_values()
                    horarios_existentes = [row[1] for row in existentes if len(row) > 1 and row[0] == str(data_sel)]
                except: horarios_existentes = []
                
                novos_cnt = 0
                for jogo in dados:
                    if jogo['horario'] not in horarios_existentes:
                        # Salva: DATA | HORARIO | P1 | P2 | P3 | P4 | P5
                        row = [jogo['data'], jogo['horario']] + jogo['premios']
                        ws.append_row(row)
                        novos_cnt += 1
                
                if novos_cnt > 0:
                    st.toast(f"{novos_cnt} Novos sorteios salvos na aba {CONFIG_BANCAS[banca]['nome_aba']}!", icon="💾")
                    time.sleep(2)
                else:
                    st.warning("Dados desta data já estavam na planilha.")
                
                # Mostra o que achou
                df = pd.DataFrame(dados)
                st.dataframe(df)
            else:
                st.warning(f"Nenhum dado encontrado. Motivo: {msg}")
                st.markdown("*Dica: Verifique se o site já publicou os resultados desta data.*")

st.markdown("---")
st.info("ℹ️ **Como usar:** Selecione datas passadas (ontem, anteontem, semana passada) e vá clicando em Iniciar Extração para criar um histórico robusto. Quando tivermos uns 200 jogos (linhas), criaremos o **App Analítico**.")
