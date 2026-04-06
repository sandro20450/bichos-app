import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time

# --- IMPORTAÇÃO DA INTELIGÊNCIA ARTIFICIAL ---
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    import numpy as np
    HAS_AI = True
except ImportError:
    HAS_AI = False

# =============================================================================
# --- 1. CONFIGURAÇÕES GERAIS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V116.0 - Atirador de Elite", page_icon="👁️", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (Dezenas)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "tradicional", "tipo": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    
    "TRADICIONAL_MILHAR": { "display_name": "👁️ TRADICIONAL (Hórus)", "nome_aba": "TRADICIONAL_MILHAR", "slug": "tradicional", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "base_dez": "BASE_TRADICIONAL_DEZ", "radar_centena": True },
    "LOTEP_MILHAR": { "display_name": "👁️ LOTEP (Hórus)", "nome_aba": "LOTEP_MILHAR", "slug": "lotep", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"], "base_dez": "LOTEP_TOP5", "radar_centena": True },
    "CAMINHO_MILHAR": { "display_name": "👁️ CAMINHO (Hórus)", "nome_aba": "CAMINHO_MILHAR", "slug": "caminho-da-sorte", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"], "base_dez": "CAMINHO_TOP5", "radar_centena": True },
    
    "MONTE_MILHAR": { "display_name": "👑 MONTE CARLOS (Vitorino)", "nome_aba": "MONTE_MILHAR", "slug": "nordeste-monte-carlos", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"], "base_dez": "MONTE_TOP5" }
}

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #ffd700 !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .card-ranking { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #00ff00; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO SEGURA COM GOOGLE SHEETS ---
# =============================================================================

@st.cache_resource(ttl=3600, show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    return None

def conectar_planilha(nome_aba):
    gc = get_gspread_client()
    if gc:
        try: return gc.open("CentralBichos").worksheet(nome_aba)
        except: return None
    return None

@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados_hibridos(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 3:
                    data_str = str(row[0]).strip()
                    hr_str = str(row[1]).strip()
                    h_clean = re.sub(r'[a-zA-Z]', '', hr_str).strip()
                    if len(h_clean) > 5: h_clean = h_clean[:5] 
                    if ':' not in h_clean and len(h_clean) >= 2: h_clean = f"{int(h_clean):02}:00"
                    
                    chave = f"{data_str}|{h_clean}"
                    premios = []
                    for i in range(2, 7):
                        if i < len(row):
                            p_str = str(row[i]).strip()
                            premios.append(p_str.zfill(2) if p_str.isdigit() else "00")
                        else: premios.append("00")
                    
                    dados_unicos[chave] = {
                        "data": data_str,
                        "horario": h_clean,
                        "premios": premios
                    }
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda x: f"{x['data']} {x['horario']}")
            return lista_final
        except: return [] 
    return []

def normalizar_data(data_str):
    data_str = str(data_str).strip()
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]
    for fmt in formatos:
        try: return datetime.strptime(data_str, fmt).date()
        except: continue
    return None

def normalizar_hora(hora_str):
    h_str = str(hora_str).strip()
    h_clean = re.sub(r'[a-zA-Z]', '', h_str).strip()
    if len(h_clean) > 5: h_clean = h_clean[:5] 
    try:
        if ':' in h_clean: return f"{int(h_clean.split(':')[0]):02}:{int(h_clean.split(':')[1]):02}"
        else: return f"{int(h_clean):02}:00"
    except: return "00:00"

# =============================================================================
# --- 3. EXTRATOR DE ELITE (BLINDAGEM CONTRA MENUS) ---
# =============================================================================

def raspar_dados_hibrido(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    tipo_ext = config.get('tipo_extracao', config['tipo'])
    slug = config['slug']
    
    if "TRADICIONAL" in banca_key:
        url = f"https://playbicho.com/resultado-jogo-do-bicho/{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    else:
        if data_alvo == date.today(): 
            url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
        else:
            url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Cache-Control': 'no-cache'
        }
        
        for _ in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200: break
            except requests.exceptions.RequestException:
                time.sleep(1)
                
        if r.status_code == 404 and data_alvo == date.today():
            url_fallback = f"https://playbicho.com/resultado-jogo-do-bicho/{slug}"
            r = requests.get(url_fallback, headers=headers, timeout=10)
            
        if r.status_code != 200: return None, f"Acesso negado. O servidor retornou erro {r.status_code}."
            
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        try: target_h, target_m = map(int, horario_alvo.split(':'))
        except: return None, "Formato de hora inválido."
        
        for tabela in tabelas:
            txt_tabela = tabela.get_text().lower()
            if "federal" in txt_tabela and "federal" not in banca_key.lower(): continue 
            
            # --- VISÃO DE FRANCO-ATIRADOR (ISOLAMENTO ESTRITO) ---
            texto_analise = txt_tabela + " "
            
            # 1. Pega apenas o PRIMEIRO cabeçalho oficial colado na tabela
            cabecalho = tabela.find_previous(['h2', 'h3', 'h4', 'h5', 'caption'])
            if cabecalho:
                texto_analise += cabecalho.get_text().lower() + " "
                
            # 2. Pega a caixa pai da tabela apenas se for pequena (rejeita menus e a página inteira)
            if tabela.parent:
                txt_parent = tabela.parent.get_text().lower()
                if len(txt_parent) < 1500:  
                    texto_analise += txt_parent + " "
            
            # 3. Pega blocos soltos vizinhos imediatamente acima da tabela
            prev = tabela.previous_sibling
            for _ in range(3):
                if prev:
                    if prev.name == 'table': break # Se bater noutra tabela, para instantaneamente
                    if prev.name and prev.get_text():
                        texto_analise += prev.get_text().lower() + " "
                    elif isinstance(prev, str):
                        texto_analise += prev.lower() + " "
                    prev = prev.previous_sibling

            # Busca segura com Regex para não confundir
            times_found = re.findall(r'(?<!\d)(\d{1,2})[:hH]s?(\d{2})(?!\d)', texto_analise)
            
            match_found = False
            for h, m in times_found:
                if int(h) == target_h and int(m) == target_m:
                    match_found = True
                    break
            
            if match_found:
                dezenas_encontradas = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 2:
                        numero_txt = cols[1].get_text().strip()
                        nums_premio = re.findall(r'\d+', cols[0].get_text())
                        if nums_premio:
                            p_idx = int(nums_premio[0])
                            limite = 5 if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW", "PENTA"] else 1
                            if 1 <= p_idx <= limite:
                                clean_num = re.sub(r'\D', '', numero_txt)
                                if len(clean_num) >= 2: 
                                    if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]: 
                                        dezenas_encontradas.append(clean_num[-4:].zfill(4))
                                    else: 
                                        dezenas_encontradas.append(clean_num[-2:])
                
                if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]:
                    if len(dezenas_encontradas) >= 1: 
                        return dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas)), "Sucesso"
                else:
                    if tipo_ext == "SOLO" and len(dezenas_encontradas) >= 1: 
                        return [dezenas_encontradas[0], "00", "00", "00", "00"], "Sucesso"
                    elif len(dezenas_encontradas) >= 5: 
                        return dezenas_encontradas[:5], "Sucesso"
                
                return None, "Tabela Encontrada, mas falha ao ler as milhares."
                
        return None, f"Horário ({horario_alvo}) não encontrado na página. A banca ainda não publicou."
    except Exception as e: return None, f"Erro de Varredura: {e}"

# =============================================================================
# --- 4. CÉREBRO: OLHO DE HÓRUS (RADAR DE CENTENAS 1º AO 5º) ---
# =============================================================================

def analisar_radar_centena(history_slice):
    if len(history_slice) < 15: return None

    historico_centenas = []
    historico_milhares = [] # Captura a milhar completa para exibir
    for draw in history_slice:
        centenas_draw = []
        milhares_draw = []
        for p in range(5):
            try:
                m = str(draw['premios'][p]).zfill(4)
                if m != "0000" and m != "00" and len(m) == 4:
                    centenas_draw.append(m[1]) 
                    milhares_draw.append(m)
            except: continue
        if centenas_draw:
            historico_centenas.append(centenas_draw)
            historico_milhares.append(milhares_draw)

    if len(historico_centenas) < 2: return None

    ultimas_centenas = historico_centenas[-1]
    ultimas_milhares = historico_milhares[-1]

    # 1. Atraso
    atrasos = {str(d): 0 for d in range(10)}
    for d in range(10):
        d_str = str(d)
        atraso = 0
        for draw in reversed(historico_centenas[:-1]):
            if d_str in draw: break
            atraso += 1
        atrasos[d_str] = atraso

    # 2. Frequência
    freq_recente = {str(d): 0 for d in range(10)}
    ultimos_10 = historico_centenas[-11:-1]
    for draw in ultimos_10:
        for d_str in set(draw): 
            freq_recente[d_str] += 1

    # 3. Transição (Markov)
    transicoes = {str(d): 0 for d in range(10)}
    total_transicoes = 0
    for i in range(len(historico_centenas) - 1):
        draw_atual = historico_centenas[i]
        draw_next = historico_centenas[i+1]
        if any(c in ultimas_centenas for c in draw_atual):
            for c_next in set(draw_next):
                transicoes[c_next] += 1
            total_transicoes += 1

    # 4. Pontuação Final
    scores = {}
    for d in range(10):
        d_str = str(d)
        tx_transicao = (transicoes[d_str] / total_transicoes * 100) if total_transicoes > 0 else 0.0
        score = (tx_transicao * 0.5) + (freq_recente[d_str] * 2.0) + (min(atrasos[d_str], 15) * 1.5)
        scores[d_str] = {
            "score": score,
            "atraso": atrasos[d_str],
            "freq": freq_recente[d_str],
            "transicao": tx_transicao
        }

    rank = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
    top_digit = rank[0][0]
    top_data = rank[0][1]

    return {
        "ultimas": ultimas_centenas,
        "ultimas_milhares": ultimas_milhares,
        "top_digit": top_digit,
        "atraso": top_data["atraso"],
        "freq": top_data["freq"],
        "transicao": top_data["transicao"],
        "score": top_data["score"],
        "rank_completo": rank
    }

# =============================================================================
# --- 5. INTERFACE NAVEGAÇÃO E TELAS ---
# =============================================================================

if "menu_nav" not in st.session_state:
    st.session_state.menu_nav = "🏠 RADAR TÁTICO (Home)"

def acionar_teletransporte(destino):
    st.session_state.menu_nav = destino

menu_opcoes = ["🏠 RADAR TÁTICO (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes, key="menu_nav")

def acao_limpar_banco(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return "Banco vazio"
            cabecalho = raw[0]
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 2:
                    dt = row[0].strip()
                    hr = row[1].strip()
                    if dt:
                        chave = f"{dt}|{hr}"
                        dados_unicos[chave] = row
            lista_final = list(dados_unicos.values())
            
            def get_sort_key(r):
                try: return datetime.strptime(f"{r[0]} {r[1]}", "%Y-%m-%d %H:%M")
                except: return datetime.min
            lista_final.sort(key=get_sort_key)
            
            ws.clear()
            ws.append_row(cabecalho)
            if lista_final: ws.append_rows(lista_final)
            st.cache_data.clear()
            return f"Sucesso! Reduzido de {len(raw)-1} para {len(lista_final)} registros."
        except Exception as e: return f"Erro: {e}"
    return "Erro Conexão"

st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR TÁTICO (Home)":
    st.title("👁️ OLHO DE HÓRUS (RADAR DE CENTENAS)")
    st.markdown("O sistema escaneia cirurgicamente a coluna das **CENTENAS do 1º ao 5º Prêmio**. Monitorando TRADICIONAL, LOTEP e CAMINHO DA SORTE.")
    
    ranking_global = []
    
    with st.spinner("📡 Rastreiando fluxo de Centenas no globo..."):
        for banca_key, config in CONFIG_BANCAS.items():
            if config.get('radar_centena') == True:
                hist_milhar = carregar_dados_hibridos(config['nome_aba'])
                if len(hist_milhar) >= 15:
                    analise = analisar_radar_centena(hist_milhar)
                    if analise:
                        analise['banca'] = config['display_name'].replace("👁️ ", "").replace(" (Hórus)", "")
                        analise['banca_key'] = banca_key
                        ranking_global.append(analise)

    if not ranking_global:
        st.info("⚠️ Sem dados suficientes ou bancas vazias.")
    else:
        ranking_global.sort(key=lambda x: x['score'], reverse=True)
        st.markdown("### 🏆 ALVOS DE DISPARO (CENTENAS 1º AO 5º)")
        
        html_final = ""
        for idx, alvo in enumerate(ranking_global):
            banca_nome = alvo['banca']
            tropa = ", ".join(alvo['ultimas'])
            milhares_tropa = ", ".join(alvo['ultimas_milhares'])
            digito = alvo['top_digit']
            
            html_ranking = (
                f'<div class="card-ranking">'
                f'<h3 style="margin:0 0 10px 0; color:#fff;">#{idx+1} | Banca: {banca_nome}</h3>'
                f'<div style="background-color:#222; padding:15px; border-radius:8px;">'
                f'  <p style="margin:0 0 5px 0; color:#aaa; font-size:1.1em;">Milhares do Globo (1º ao 5º): <b>{milhares_tropa}</b></p>'
                f'  <p style="margin:0 0 10px 0; color:#aaa; font-size:1.1em;">Últimas Centenas (1º ao 5º): <b>{tropa}</b></p>'
                f'  <h2 style="margin:0; color:#00ff00; text-align:center;">🎯 ALVO RECOMENDADO: CENTENA ({digito})</h2>'
                f'  <p style="margin:5px 0 0 0; color:#fff; text-align:center;">Jogue a Centena com o algarismo <b>{digito}</b> do 1º ao 5º Prêmio.</p>'
                f'</div>'
                f'<div style="margin-top:10px; display:flex; justify-content:space-around; font-size:0.9em; color:#ddd;">'
                f'  <span><b>⏳ Atraso:</b> {alvo["atraso"]} sorteios fora</span>'
                f'  <span><b>🔁 Frequência:</b> {alvo["freq"]} (últ. 10 jogos)</span>'
                f'  <span><b>🧲 Atração (Markov):</b> {alvo["transicao"]:.1f}%</span>'
                f'</div>'
                f'</div>'
            )
            html_final += html_ranking
            
        st.markdown(html_final, unsafe_allow_html=True)

else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    
    if "TRADICIONAL" in banca_selecionada:
        url_banca = f"https://playbicho.com/resultado-jogo-do-bicho/{config['slug']}-do-dia-{date.today().strftime('%Y-%m-%d')}"
    else:
        url_banca = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
        
    st.sidebar.markdown(f"<a href='{url_banca}' target='_blank'><button style='width: 100%; border-radius: 5px; font-weight: bold; background-color: #007bff; color: white; padding: 8px 10px; border: none; cursor: pointer; margin-bottom: 10px;'>🌐 Visitar Site da Banca</button></a>", unsafe_allow_html=True)
    
    if st.sidebar.button("🧹 EXECUTAR FAXINA NO BANCO DE DADOS", key=f"btn_fax_stb_{banca_selecionada}"):
        with st.spinner("Limpando e reescrevendo planilha..."):
            res_principal = acao_limpar_banco(config['nome_aba'])
            if 'base_dez' in config: acao_limpar_banco(config['base_dez'])
            if "Sucesso" in res_principal: st.sidebar.success("Faxina Dupla Concluída com Sucesso!")
            else: st.sidebar.error(res_principal)
            time.sleep(2)
            st.rerun()
            
    st.sidebar.markdown("---")
    
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)", "✍️ Manual"])
    
    if modo_extracao == "🎯 Unitária":
        data_busca = date.today()
        horario_busca = config['horarios'][0]
        
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key=f"rad_dt_{banca_selecionada}")
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.date_input("Escolha:", date.today(), key=f"dt_pk_{banca_selecionada}")
            
            lista_horarios = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca.weekday() in [2, 5]: 
                if "20:00" in lista_horarios:
                    lista_horarios[lista_horarios.index("20:00")] = "19:30"
                    
            horario_busca = st.selectbox("Horário:", lista_horarios, key=f"sel_hr_{banca_selecionada}")
            
            if st.button("🚀 Baixar & Salvar", key=f"btn_b_stb_{banca_selecionada}"):
                aba_dez = config.get('base_dez', config['nome_aba'])
                aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
                tipo_ext = config.get('tipo_extracao', config['tipo'])
                
                ws_dez = conectar_planilha(aba_dez)
                ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
                
                if ws_dez:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try: 
                            existentes = ws_dez.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                            if premios:
                                if tipo_ext == "DUAL_SOLO":
                                    row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca, premios[0][-2:], "00", "00", "00", "00"]
                                    ws_dez.append_row(row_dez)
                                    if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                    st.toast(f"Sucesso!", icon="✅")
                                elif tipo_ext == "DUAL_PENTA":
                                    row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios]
                                    ws_dez.append_row(row_dez)
                                    if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                    st.toast(f"Sucesso Total!", icon="✅")
                                st.cache_data.clear() 
                                time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro na Planilha do Google")

    elif modo_extracao == "🌪️ Em Massa (Turbo)": 
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1), key=f"dt_ini_{banca_selecionada}")
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today(), key=f"dt_fim_{banca_selecionada}")
        
        if st.sidebar.button("🚀 INICIAR TURBO", key=f"btn_tb_stb_{banca_selecionada}"):
            aba_dez = config.get('base_dez', config['nome_aba'])
            aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
            tipo_ext = config.get('tipo_extracao', config['tipo'])
            
            ws_dez = conectar_planilha(aba_dez)
            ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
            
            if ws_dez:
                status = st.sidebar.empty(); bar = st.sidebar.progress(0)
                try: chaves_d = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_dez.get_all_values() if len(r) >= 2 and normalizar_data(r[0])]
                except: chaves_d = []
                try: chaves_m = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_milhar.get_all_values() if len(r) >= 2 and normalizar_data(r[0])] if ws_milhar else []
                except: chaves_m = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config['horarios']); op_atual = 0; sucessos = 0
                buffer_dez = []; buffer_m = []
                
                for dia in lista_datas:
                    for hora_base in config['horarios']:
                        hora_efetiva = hora_base
                        if "CAMINHO" in banca_selecionada and dia.weekday() in [2, 5]:
                            if hora_base == "20:00": hora_efetiva = "19:30"
                                
                        op_atual += 1; bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora_efetiva}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{normalizar_hora(hora_efetiva)}"
                        
                        if chave_atual in chaves_d: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora_efetiva > datetime.now().strftime("%H:%M"): continue
                        
                        premios, msg = raspar_dados_hibrido(banca_selecionada, dia, hora_efetiva)
                        if premios:
                            if tipo_ext == "DUAL_SOLO":
                                row_d = [dia.strftime('%Y-%m-%d'), hora_efetiva, premios[0][-2:], "00", "00", "00", "00"]
                                buffer_dez.append(row_d); chaves_d.append(chave_atual)
                                if ws_milhar and chave_atual not in chaves_m: buffer_m.append([dia.strftime('%Y-%m-%d'), hora_efetiva] + premios); chaves_m.append(chave_atual)
                            elif tipo_ext == "DUAL_PENTA":
                                row_d = [dia.strftime('%Y-%m-%d'), hora_efetiva] + [p[-2:] for p in premios]
                                buffer_dez.append(row_d); chaves_d.append(chave_atual)
                                if ws_milhar and chave_atual not in chaves_m: buffer_m.append([dia.strftime('%Y-%m-%d'), hora_efetiva] + premios); chaves_m.append(chave_atual)
                            sucessos += 1
                        time.sleep(1.0) 
                status.text("🚚 Sincronizando Matrizes...")
                if buffer_dez: ws_dez.append_rows(buffer_dez)
                if buffer_m and ws_milhar: ws_milhar.append_rows(buffer_m)
                st.cache_data.clear() 
                bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos registros."); time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão Google")

    elif modo_extracao == "✍️ Manual":
        data_busca_man = date.today()
        horario_busca_man = config['horarios'][0]
        
        with st.sidebar.expander("📝 Lançar Manualmente", expanded=True):
            opcao_data_man = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key=f"rad_man_{banca_selecionada}")
            if opcao_data_man == "Hoje": data_busca_man = date.today()
            elif opcao_data_man == "Ontem": data_busca_man = date.today() - timedelta(days=1)
            else: data_busca_man = st.date_input("Escolha:", date.today(), key=f"dt_man_{banca_selecionada}")
            
            lista_horarios_man = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca_man.weekday() in [2, 5]: 
                if "20:00" in lista_horarios_man:
                    lista_horarios_man[lista_horarios_man.index("20:00")] = "19:30"
                    
            horario_busca_man = st.selectbox("Horário:", lista_horarios_man, key=f"hr_man_{banca_selecionada}")
            
            st.markdown("🎯 **Preencha as Milhares (4 dígitos):**")
            p1 = st.text_input("1º Prêmio", max_chars=4, key=f"man_p1_{banca_selecionada}")
            p2 = st.text_input("2º Prêmio", max_chars=4, key=f"man_p2_{banca_selecionada}")
            p3 = st.text_input("3º Prêmio", max_chars=4, key=f"man_p3_{banca_selecionada}")
            p4 = st.text_input("4º Prêmio", max_chars=4, key=f"man_p4_{banca_selecionada}")
            p5 = st.text_input("5º Prêmio", max_chars=4, key=f"man_p5_{banca_selecionada}")
            
            if st.button("💾 Salvar Resultado", key=f"btn_salvar_man_{banca_selecionada}", use_container_width=True):
                def limpar_milhar(m):
                    num = re.sub(r'\D', '', str(m))
                    return num.zfill(4) if num else "0000"
                
                premios_finais = [limpar_milhar(p1), limpar_milhar(p2), limpar_milhar(p3), limpar_milhar(p4), limpar_milhar(p5)]
                aba_dez = config.get('base_dez', config['nome_aba'])
                aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
                tipo_ext = config.get('tipo_extracao', config['tipo'])
                ws_dez = conectar_planilha(aba_dez)
                ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
                
                if ws_dez:
                    with st.spinner(f"Salvando {horario_busca_man} manualmente..."):
                        try: 
                            existentes = ws_dez.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual_man = f"{data_busca_man.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca_man)}"
                        
                        if chave_atual_man in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            if tipo_ext == "DUAL_SOLO":
                                row_dez = [data_busca_man.strftime('%Y-%m-%d'), horario_busca_man, premios_finais[0][-2:], "00", "00", "00", "00"]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca_man.strftime('%Y-%m-%d'), horario_busca_man] + premios_finais)
                                st.toast(f"Salvo!", icon="✅")
                            elif tipo_ext == "DUAL_PENTA":
                                row_dez = [data_busca_man.strftime('%Y-%m-%d'), horario_busca_man] + [p[-2:] for p in premios_finais]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca_man.strftime('%Y-%m-%d'), horario_busca_man] + premios_finais)
                                st.toast(f"Salvo Total!", icon="✅")
                            st.cache_data.clear() 
                            time.sleep(1); st.rerun()
                else: st.error("Erro na Planilha")

    # --- PÁGINA DA BANCA ---
    
    if config['tipo'] == "MILHAR_VIEW":
        st.header(f"👁️ {config['display_name']}")
        
        with st.spinner("Processando Radar de Centenas..."):
            hist_milhar = carregar_dados_hibridos(config['nome_aba'])
            
        if len(hist_milhar) > 0:
            ult = hist_milhar[-1]
            st.success(f"📅 **Último Sorteio Lido:** {ult['data']} às {ult['horario']}")
            
            if config.get('radar_centena'):
                st.markdown("### 👁️‍🗨️ OLHO DE HÓRUS (Análise 1º ao 5º Prêmio)")
                res_centena = analisar_radar_centena(hist_milhar)
                
                if res_centena:
                    tropa_atual = ", ".join(res_centena['ultimas'])
                    milhares_atual = ", ".join(res_centena['ultimas_milhares'])
                    alvo_digito = res_centena['top_digit']
                    
                    with st.container(border=True):
                        st.info(f"**Milhares Sorteadas no Globo (1º ao 5º):** {milhares_atual}")
                        st.info(f"**Tropa de Centenas Atual no Globo (1º ao 5º):** {tropa_atual}")
                        st.markdown(f"<h2 style='color:#00ff00; text-align:center;'>🎯 ALVO DE OURO: APOSTE NO ALGARISMO ({alvo_digito})</h2>", unsafe_allow_html=True)
                        st.markdown(f"<p style='text-align:center; color:#ccc; font-size:1.1em;'>Jogue a Centena com o algarismo <b>{alvo_digito}</b> do 1º ao 5º Prêmio.</p>", unsafe_allow_html=True)
                        
                        col_c1, col_c2, col_c3 = st.columns(3)
                        col_c1.metric("Atraso (Sorteios Fora)", res_centena['atraso'])
                        col_c2.metric("Frequência (Últimos 10)", res_centena['freq'])
                        col_c3.metric("Poder de Transição (Atração)", f"{res_centena['transicao']:.1f}%")
                        
                        st.markdown("---")
                        st.markdown("#### 📊 Posição Completa do Globo (Top 3)")
                        rank = res_centena['rank_completo']
                        for i in range(min(3, len(rank))):
                            dig = rank[i][0]
                            st.write(f"**{i+1}º Lugar:** Centena **{dig}** (Atraso: {rank[i][1]['atraso']} | Freq: {rank[i][1]['freq']})")
                else:
                    st.info("Sem dados suficientes para o Radar de Centenas. Extraia mais resultados.")
                    
            else:
                st.info("⚠️ O Radar de Centenas não está ativo para esta banca.")
                
            # --- CALCULADORA DE HEDGE ---
            st.markdown("---")
            st.subheader("🛡️ Calculadora de Seguro de Banca")
            with st.container(border=True):
                col_calc1, col_calc2 = st.columns(2)
                with col_calc1:
                    valor_milhar = st.number_input("💰 Valor da Invertida 8D (R$):", min_value=1.0, value=40.96, step=1.0)
                seguro_recomendado = valor_milhar / 21 
                custo_total = valor_milhar + seguro_recomendado
                retorno_seguro = seguro_recomendado * 23
                with col_calc2:
                    st.info(f"**🛡️ Jogue no Grupo da Milhar:** R$ {seguro_recomendado:.2f}")
                    st.caption(f"Custo Total: R$ {custo_total:.2f} | Prêmio Grupo: R$ {retorno_seguro:.2f}")
                    
            # --- TABELA DO BANCO DE DADOS RESTAURADA ---
            st.markdown("---")
            st.markdown("### 📊 Banco de Dados Bruto (Últimos Sorteios)")
            df_show = pd.DataFrame(hist_milhar)
            st.dataframe(df_show.tail(15), use_container_width=True)

        else:
            st.warning("⚠️ Base vazia. Extraia os dados primeiro através do menu ao lado.")

    # ==========================================
    # PAINEL DE EXTRAÇÃO BASE (DEZENAS/DUAL)
    # ==========================================
    else:
        st.header(f"🔭 {config['display_name']} - Oracle 46")
        with st.spinner("Carregando e Limpando dados..."):
            historico = carregar_dados_hibridos(config['nome_aba'])
            
        if len(historico) > 0:
            ult = historico[-1]
            if config['tipo'] == "DUAL_SOLO": st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **1º Prêmio:** {str(ult['premios'][0])[-2:]}")
            else: st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **P1:** {ult['premios'][0]} ... **P5:** {ult['premios'][4]}")
            
            range_abas = [0, 1] 
            abas = st.tabs(["🔮 Oracle 46", "🎯 Unidades"])
            
            for idx_aba in range_abas:
                with abas[idx_aba]:
                    if idx_aba == 1:
                        st.markdown("### 🏹 The Chaser (Perseguição de Ciclo de 8 Jogos)")
                        estado_chaser = rastrear_estado_chaser(historico, 0)
                        if estado_chaser['target'] is not None:
                            col_gold, col_info = st.columns([1, 2])
                            with col_gold: st.metric("🌟 Alvo Principal", f"Final {estado_chaser['target']}")
                            with col_info:
                                if estado_chaser['status'] == 'ativo': st.warning(f"🔒 **PERSEGUIÇÃO (TENTATIVA {estado_chaser['attempts']+1} DE 8)**")
                                else: st.success("🎯 **NOVO CICLO (TENTATIVA 1 DE 8)**")
                                st.caption(f"Base Matemática: {estado_chaser['prob']:.1f}%")
                        st.markdown("---")
                        markov, ciclo, quente = calcular_3_estrategias_unidade(historico, 0)
                        c_m, c_c, c_q = st.columns(3)
                        c_m.metric('1. Ímã (Markov)', f"Final {markov}", "Maior atração")
                        c_c.metric('2. Fechamento Ciclo', f"Final {ciclo}", "Mais atrasada", delta_color="off")
                        c_q.metric('3. Tendência Quente', f"Final {quente}", "Moda repetição")
                    else:
                        lista_matrix, conf_total, info_predator, dados_oracle = gerar_estrategia_oracle_46(historico, idx_aba)
                        if HAS_AI:
                            c_ima, c_rep = st.columns(2)
                            with c_ima: st.success(f"🧲 **ÍMÃS:** {dados_oracle['imas']}")
                            with c_rep: st.error(f"⛔ **REPELIDOS:** {dados_oracle['repelidos']}")
                        with st.container(border=True): st.code(", ".join(lista_matrix), language="text")
        else:
            st.warning("⚠️ Base vazia. Extraia os dados primeiro através do menu ao lado.")
