import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time
from collections import Counter

# =============================================================================
# --- 1. CONFIGURAÇÕES ---
# =============================================================================
st.set_page_config(page_title="CENTURION 75 - Caçador de Dezenas", page_icon="🛡️", layout="wide")

# Mapeamento das Abas Novas (Só Dezenas)
CONFIG_BANCAS = {
    "LOTEP": { 
        "display": "LOTEP (Dezenas)", 
        "aba": "BASE_LOTEP_DEZ", 
        "slug": "lotep", 
        "horarios": ["10:45", "12:45", "15:45", "18:00"] 
    },
    "CAMINHO": { 
        "display": "CAMINHO (Dezenas)", 
        "aba": "BASE_CAMINHO_DEZ", 
        "slug": "caminho-da-sorte", 
        "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] 
    },
    "MONTE": { 
        "display": "MONTE CARLOS (Dezenas)", 
        "aba": "BASE_MONTE_DEZ", 
        "slug": "nordeste-monte-carlos", 
        "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] 
    }
}

# Mapeamento Matemático: Qual dezena pertence a qual grupo?
GRUPOS_BICHOS = {}
for g in range(1, 26):
    fim = g * 4
    inicio = fim - 3
    dezenas = []
    for n in range(inicio, fim + 1):
        if n == 100: dezenas.append("00")
        else: dezenas.append(f"{n:02}")
    GRUPOS_BICHOS[g] = dezenas # Ex: Grupo 1 = ['01', '02', '03', '04']

# Estilo Visual (Tema Romano/Centurion)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    .box-centurion {
        background: linear-gradient(135deg, #700000, #3d0000); /* Vermelho Romano */
        border: 2px solid #ffd700; /* Ouro */
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.2);
    }
    .titulo-gold { color: #ffd700; font-weight: 900; font-size: 28px; text-transform: uppercase; letter-spacing: 2px; }
    .subtitulo { color: #ccc; font-size: 14px; margin-bottom: 15px; }
    .nums-destaque { font-size: 18px; color: #fff; font-weight: bold; word-wrap: break-word; line-height: 1.6; }
    .lucro-info { background-color: rgba(0, 255, 0, 0.1); border: 1px solid #00ff00; padding: 10px; border-radius: 5px; color: #00ff00; font-weight: bold; margin-top: 10px; }
    .info-corte { font-size: 12px; color: #ff9999; margin-top: 5px; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM DE DEZENAS ---
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos") # Nome da sua planilha geral
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_historico_dezenas(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        raw = ws.get_all_values()
        if len(raw) < 2: return []
        dados = []
        for row in raw[1:]: # Pula cabeçalho
            if len(row) >= 7:
                # Pega as dezenas das colunas 3 a 7 (índices 2 a 6)
                dezenas = [str(d).zfill(2) for d in row[2:7] if d.isdigit()]
                if len(dezenas) == 5:
                    dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
        return dados
    return []

# ROBÔ DE EXTRAÇÃO DE DEZENAS (V1.0)
def raspar_dezenas_site(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    
    # Monta URL (Lógica de data)
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    if delta == 0: url = f"{base}/resultados-{config['slug']}-de-hoje"
    elif delta == 1: url = f"{base}/resultados-{config['slug']}-de-ontem"
    else: url = f"{base}/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Conexão Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')

        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                # Verifica data no cabeçalho anterior
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if cabecalho and "FEDERAL" in cabecalho.upper(): continue 

                # Verifica horário
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        # Normaliza hora (ex: 10h -> 10:00)
                        if ':' in raw: h_detect = raw
                        elif 'h' in raw: h_detect = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: h_detect = raw.strip().zfill(2) + ":00"

                        if h_detect == horario_alvo:
                            dezenas_encontradas = []
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                cols = linha.find_all('td')
                                if len(cols) >= 2:
                                    premio_txt = cols[0].get_text().strip() # "1º Prêmio"
                                    numero_txt = cols[1].get_text().strip() # "4582" (Milhar)
                                    
                                    # Verifica se é do 1º ao 5º
                                    nums_premio = re.findall(r'\d+', premio_txt)
                                    if nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                        # EXTRAÇÃO DA DEZENA
                                        # Pega os 2 últimos dígitos do milhar
                                        if numero_txt.isdigit() and len(numero_txt) >= 2:
                                            dezena = numero_txt[-2:] # Pega o final
                                            dezenas_encontradas.append(dezena)
                            
                            if len(dezenas_encontradas) >= 5:
                                return dezenas_encontradas[:5], "Sucesso"
                            else:
                                return None, "Leitura Incompleta"
        return None, "Horário não encontrado"
    except Exception as e:
        return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO ESTRATÉGICO (CENTURION 75) ---
# =============================================================================
def gerar_matriz_75(historico, indice_premio):
    # Analisa as dezenas que saíram na posição específica (ex: 1º prêmio)
    # Se histórico for vazio, retorna as 3 primeiras de cada grupo (padrão)
    
    dezenas_historico = []
    if historico:
        # Pega as últimas 30 dezenas que saíram nessa posição
        recorte = historico[-30:] 
        for jogo in recorte:
            try:
                dezenas_historico.append(jogo['dezenas'][indice_premio])
            except: pass
    
    contagem = Counter(dezenas_historico) # Conta frequência: '82': 3x, '10': 0x...
    
    palpite_final = []
    dezenas_cortadas = []
    
    # Para cada um dos 25 Grupos (Bichos)
    for grupo, lista_dezenas in GRUPOS_BICHOS.items():
        # Vamos ranquear as 4 dezenas do grupo
        # Critério: Frequência (da menor para maior)
        # O usuário quer remover a "menos provável" (a mais fria/que sai menos)
        
        # Cria lista de tuplas: (dezena, frequencia)
        rank = []
        for d in lista_dezenas:
            freq = contagem.get(d, 0)
            rank.append((d, freq))
        
        # Ordena: Menor frequência primeiro (Frias) -> Maior (Quentes)
        rank.sort(key=lambda x: x[1])
        
        # Lógica de Corte:
        # Removemos a que tem MENOS saídas (rank[0])
        # Sobram as 3 "mais fortes" (ou menos frias)
        
        # ATENÇÃO: Se todas tiverem 0, remove a última do grupo (padrão do jogo)
        
        dezena_removida = rank[0][0] # A mais fria
        dezenas_selecionadas = [x[0] for x in rank[1:]] # As outras 3
        
        palpite_final.extend(dezenas_selecionadas)
        dezenas_cortadas.append(f"G{grupo}:{dezena_removida}")
        
    return sorted(palpite_final), dezenas_cortadas

# =============================================================================
# --- 4. INTERFACE (FRONTEND) ---
# =============================================================================
st.title("🛡️ CENTURION 75")
st.markdown("**Estratégia de Cobertura de Dezenas (3x1)**")

# MENU LATERAL (IMPORTAR)
with st.sidebar:
    st.header("📥 Importar Dezenas")
    banca_sel = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
    conf = CONFIG_BANCAS[banca_sel]
    
    opt_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
    if opt_data == "Hoje": data_busca = date.today()
    elif opt_data == "Ontem": data_busca = date.today() - timedelta(days=1)
    else: data_busca = st.date_input("Data:", date.today())
    
    hora_busca = st.selectbox("Horário:", conf['horarios'])
    
    if st.button("🚀 Baixar Dezenas"):
        ws = conectar_planilha(conf['aba'])
        if ws:
            with st.spinner(f"Caçando dezenas em {banca_sel}..."):
                # Verifica duplicidade simples
                try:
                    existentes = ws.get_all_values()
                    chaves = [f"{r[0]}|{r[1]}" for r in existentes]
                except: chaves = []
                
                chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{hora_busca}"
                
                if chave_atual in chaves:
                    st.warning("Esse resultado já foi baixado!")
                else:
                    dezenas, msg = raspar_dezenas_site(banca_sel, data_busca, hora_busca)
                    if dezenas:
                        row = [data_busca.strftime('%Y-%m-%d'), hora_busca] + dezenas
                        ws.append_row(row)
                        st.success(f"✅ Sucesso! Dezenas: {dezenas}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        else:
            st.error("Erro ao conectar na Planilha (Verifique se criou a aba correta!)")

# TELA PRINCIPAL
conf_atual = CONFIG_BANCAS[banca_sel] # Usa a seleção do sidebar
st.subheader(f"Analise: {conf_atual['display']}")

historico = carregar_historico_dezenas(conf_atual['aba'])

if len(historico) == 0:
    st.info(f"⚠️ A base de dados da {banca_sel} está vazia. Use o menu lateral para baixar os primeiros resultados!")
    st.stop()

# Abas para os 5 prêmios
tabs = st.tabs(["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"])

for i, tab in enumerate(tabs):
    with tab:
        # Gera a matriz
        lista_75, cortadas = gerar_matriz_75(historico, i)
        
        st.markdown(f"""
        <div class="box-centurion">
            <div class="titulo-gold">LEGIÃO 75 - {i+1}º PRÊMIO</div>
            <div class="subtitulo">Cobertura Estatística (Eliminação da Pior Dezena de cada Grupo)</div>
            
            <div class="nums-destaque">
                {', '.join(lista_75)}
            </div>
            
            <div class="lucro-info">
                💰 Custo: R$ 75,00 | Retorno: R$ 92,00 | Lucro: R$ 17,00 (22%)
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("✂️ Ver Dezenas Eliminadas (Ovelhas Negras)"):
            st.write(", ".join(cortadas))
            st.caption("Estas foram as dezenas removidas por serem as mais frias do seu grupo.")

        st.markdown("---")
        st.write(f"📊 **Base de Análise:** {len(historico)} sorteios registrados.")
