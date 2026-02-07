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
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="CENTURION 75 - V3.0 Turbo", page_icon="🛡️", layout="wide")

# Configuração das Bancas e Abas (Dezenas)
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

# Mapeamento: Quais dezenas pertencem a qual grupo?
GRUPOS_BICHOS = {}
for g in range(1, 26):
    fim = g * 4
    inicio = fim - 3
    dezenas = []
    for n in range(inicio, fim + 1):
        if n == 100: dezenas.append("00")
        else: dezenas.append(f"{n:02}")
    GRUPOS_BICHOS[g] = dezenas 

# Estilo Visual (CSS - Tema Centurião)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    
    .box-centurion {
        background: linear-gradient(135deg, #5c0000, #2b0000);
        border: 2px solid #ffd700;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 0 25px rgba(255, 215, 0, 0.15);
    }
    
    .titulo-gold { 
        color: #ffd700; 
        font-weight: 900; 
        font-size: 26px; 
        text-transform: uppercase; 
        letter-spacing: 2px; 
        margin-bottom: 5px;
    }
    
    .subtitulo { 
        color: #cccccc; 
        font-size: 14px; 
        margin-bottom: 20px; 
        font-style: italic;
    }
    
    .nums-destaque { 
        font-size: 20px; 
        color: #ffffff; 
        font-weight: bold; 
        word-wrap: break-word; 
        line-height: 1.8;
        letter-spacing: 1px;
    }
    
    .lucro-info { 
        background-color: rgba(0, 255, 0, 0.05); 
        border: 1px solid #00ff00; 
        padding: 10px; 
        border-radius: 8px; 
        color: #00ff00; 
        font-weight: bold; 
        margin-top: 20px;
        font-size: 16px;
    }
    
    div[data-testid="stTable"] table { color: white; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (EXTRAÇÃO) ---
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_historico_dezenas(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        raw = ws.get_all_values()
        if len(raw) < 2: return []
        dados = []
        for row in raw[1:]:
            if len(row) >= 7:
                dezenas = [str(d).strip().zfill(2) for d in row[2:7] if d.strip().isdigit()]
                if len(dezenas) == 5:
                    dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
        return dados
    return []

def raspar_dezenas_site(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    
    if delta == 0: url = f"{base}/resultados-{config['slug']}-de-hoje"
    elif delta == 1: url = f"{base}/resultados-{config['slug']}-de-ontem"
    else: url = f"{base}/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')

        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                # --- FILTRO ANTI-FEDERAL ---
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if cabecalho and "FEDERAL" in cabecalho.upper(): continue 

                # Valida Horário
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        if ':' in raw: h_detect = raw
                        elif 'h' in raw: h_detect = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: h_detect = raw.strip().zfill(2) + ":00"

                        if h_detect == horario_alvo:
                            dezenas_encontradas = []
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                cols = linha.find_all('td')
                                if len(cols) >= 2:
                                    premio_txt = cols[0].get_text().strip()
                                    numero_txt = cols[1].get_text().strip()
                                    
                                    nums_premio = re.findall(r'\d+', premio_txt)
                                    if nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                        if numero_txt.isdigit() and len(numero_txt) >= 2:
                                            dezena = numero_txt[-2:]
                                            dezenas_encontradas.append(dezena)
                            
                            if len(dezenas_encontradas) >= 5:
                                return dezenas_encontradas[:5], "Sucesso"
                            else: return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: LÓGICA DE ELIMINAÇÃO ---
# =============================================================================
def gerar_matriz_75(historico, indice_premio):
    if not historico:
        padrao = []
        cortadas = []
        for g in range(1, 26):
            dzs = GRUPOS_BICHOS[g]
            padrao.extend(dzs[:3])
            cortadas.append(f"G{g}:{dzs[3]}")
        return padrao, cortadas

    dezenas_historico = []
    recorte = historico[-30:] 
    for jogo in recorte:
        try: dezenas_historico.append(jogo['dezenas'][indice_premio])
        except: pass
    
    contagem = Counter(dezenas_historico)
    
    palpite_final = []
    dezenas_cortadas = []
    
    for grupo, lista_dezenas in GRUPOS_BICHOS.items():
        rank = []
        for d in lista_dezenas:
            freq = contagem.get(d, 0)
            rank.append((d, freq))
        
        rank.sort(key=lambda x: x[1])
        
        dezena_removida = rank[0][0] 
        dezenas_selecionadas = [x[0] for x in rank[1:]] 
        
        palpite_final.extend(dezenas_selecionadas)
        dezenas_cortadas.append(f"G{grupo}:{dezena_removida} ({rank[0][1]}x)")
        
    return sorted(palpite_final), dezenas_cortadas

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
st.title("🛡️ CENTURION 75")
st.markdown("**Estratégia de Cobertura de Dezenas (Lucro: 22%)**")

# --- SIDEBAR: IMPORTAÇÃO TURBO ---
with st.sidebar:
    st.header("📥 Extração em Massa")
    banca_sel = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
    conf = CONFIG_BANCAS[banca_sel]
    
    st.info("⚠️ Selecione o período para baixar TUDO de uma vez.")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        data_ini = st.date_input("Início:", date.today() - timedelta(days=1))
    with col_d2:
        data_fim = st.date_input("Fim:", date.today())
    
    if st.button("🚀 INICIAR EXTRAÇÃO TOTAL"):
        ws = conectar_planilha(conf['aba'])
        if ws:
            status_placeholder = st.empty()
            bar_placeholder = st.progress(0)
            
            # Carrega chaves existentes para não duplicar
            try:
                existentes = ws.get_all_values()
                chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
            except: chaves = []
            
            # Gera lista de datas
            delta = data_fim - data_ini
            lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
            
            total_ops = len(lista_datas) * len(conf['horarios'])
            op_atual = 0
            sucessos = 0
            
            st.toast("Iniciando motor de extração...", icon="🔥")
            
            for dia in lista_datas:
                for hora in conf['horarios']:
                    op_atual += 1
                    progresso = op_atual / total_ops
                    bar_placeholder.progress(progresso)
                    
                    status_placeholder.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                    
                    chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                    
                    if chave_atual in chaves:
                        # Já existe, pula
                        continue
                    
                    # Se data for futura, para
                    if dia > date.today():
                        continue
                    if dia == date.today():
                        # Se for hoje, verifica se o horário já passou (aprox)
                        hora_limite = datetime.now().strftime("%H:%M")
                        if hora > hora_limite:
                            continue

                    # Tenta baixar
                    dezenas, msg = raspar_dezenas_site(banca_sel, dia, hora)
                    
                    if dezenas:
                        row = [dia.strftime('%Y-%m-%d'), hora] + dezenas
                        ws.append_row(row)
                        sucessos += 1
                        chaves.append(chave_atual) # Adiciona na lista local para não duplicar no mesmo loop
                    
                    # Pausa de segurança (Anti-Bloqueio)
                    time.sleep(1.0)
            
            bar_placeholder.progress(100)
            status_placeholder.success(f"🏁 Concluído! {sucessos} novos sorteios salvos.")
            time.sleep(2)
            st.rerun()
            
        else: st.error("Erro ao conectar na Planilha.")

# --- TELA PRINCIPAL ---
conf_atual = CONFIG_BANCAS[banca_sel]
st.subheader(f"Analise: {conf_atual['display']}")

historico = carregar_historico_dezenas(conf_atual['aba'])

if len(historico) == 0:
    st.warning("⚠️ Base de dados vazia para esta banca.")
    st.info("👉 Use o menu lateral para baixar os primeiros resultados.")
    st.stop()

tabs = st.tabs(["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"])

for i, tab in enumerate(tabs):
    with tab:
        lista_75, cortadas = gerar_matriz_75(historico, i)
        
        html_content = f"""
<div class="box-centurion">
<div class="titulo-gold">LEGIÃO 75 - {i+1}º PRÊMIO</div>
<div class="subtitulo">Estratégia: Eliminação da Dezena mais fraca de cada Grupo</div>
<div class="nums-destaque">{', '.join(lista_75)}</div>
<div class="lucro-info">💰 Custo: R$ 75,00 | Retorno: R$ 92,00 | Lucro: R$ 17,00 (22%)</div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)
        
        with st.expander("✂️ Ver Dezenas Eliminadas (Ovelhas Negras)"):
            st.write(", ".join(cortadas))
            st.caption("Estas foram as dezenas removidas por serem as menos frequentes do grupo nos últimos 30 jogos.")

        st.markdown("---")
        st.write(f"📊 **Base de Análise:** {len(historico)} sorteios.")
