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
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V106.0 - Olho de Hórus", page_icon="👁️", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (Dezenas)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "tipo": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    
    # TRADICIONAL AGORA PUXA DO 1º AO 5º (DUAL_PENTA) PARA O RADAR DE CENTENAS
    "TRADICIONAL_MILHAR": { "display_name": "👁️ TRADICIONAL (Hórus)", "nome_aba": "TRADICIONAL_MILHAR", "slug": "loteria-tradicional", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "base_dez": "BASE_TRADICIONAL_DEZ", "radar_centena": True },
    
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
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #00ff00; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .card-ranking { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #00ff00; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM ---
# =============================================================================

def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

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

def carregar_dados_hibridos(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 3:
                    dt_obj = normalizar_data(row[0])
                    hr_str = normalizar_hora(row[1])
                    if dt_obj:
                        chave = f"{dt_obj.strftime('%Y-%m-%d')}|{hr_str}"
                        premios = []
                        for i in range(2, 7):
                            if i < len(row):
                                p_str = str(row[i]).strip()
                                if p_str.isdigit(): premios.append(p_str.zfill(2))
                                else: premios.append("00")
                            else: premios.append("00")
                        dados_unicos[chave] = {
                            "data": dt_obj.strftime('%Y-%m-%d'),
                            "horario": hr_str,
                            "premios": premios
                        }
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda x: datetime.strptime(f"{x['data']} {x['horario']}", "%Y-%m-%d %H:%M"))
            return lista_final
        except: return [] 
    return []

def raspar_dados_hibrido(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    tipo_ext = config.get('tipo_extracao', config['tipo'])
    url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    if data_alvo == date.today(): url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        h_formatado = horario_alvo 
        h_h = f"{horario_alvo.split(':')[0]}h{horario_alvo.split(':')[1]}" 
        
        for tabela in tabelas:
            cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
            if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
            
            texto_arredores = ""
            tag_anterior = tabela.find_previous(['h2', 'h3', 'h4', 'div', 'caption'])
            if tag_anterior:
                texto_arredores = tag_anterior.get_text().lower()
                
            texto_tabela = tabela.get_text().lower()
            
            if (h_formatado in texto_arredores or h_h in texto_arredores or 
                h_formatado in texto_tabela or h_h in texto_tabela):
                
                dezenas_encontradas = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 2:
                        premio_txt = cols[0].get_text().strip()
                        numero_txt = cols[1].get_text().strip()
                        nums_premio = re.findall(r'\d+', premio_txt)
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
                        res = dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas))
                        return res[:5], "Sucesso"
                else:
                    if tipo_ext == "SOLO" and len(dezenas_encontradas) >= 1: return [dezenas_encontradas[0], "00", "00", "00", "00"], "Sucesso"
                    elif len(dezenas_encontradas) >= 5: return dezenas_encontradas[:5], "Sucesso"
                
                return None, "Extração Incompleta"
                
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: OLHO DE HÓRUS (RADAR DE CENTENAS 1º AO 5º) ---
# =============================================================================

def analisar_radar_centena(history_slice):
    """Analisa as centenas do 1º ao 5º prêmio combinados e prevê o algarismo mais forte."""
    if len(history_slice) < 15: return None

    # Extrai o algarismo da centena (index 1 de "ABCD") de cada prêmio (1º ao 5º)
    historico_centenas = []
    for draw in history_slice:
        centenas_draw = []
        for p in range(5):
            m = str(draw['premios'][p]).zfill(4)
            if m != "0000" and m != "00" and len(m) == 4:
                centenas_draw.append(m[1]) # Pega o segundo dígito (Centena)
        if centenas_draw:
            historico_centenas.append(centenas_draw)

    if len(historico_centenas) < 2: return None

    ultimas_centenas = historico_centenas[-1]

    # 1. Atraso (Quantos sorteios o algarismo não aparece na centena do 1º ao 5º)
    atrasos = {str(d): 0 for d in range(10)}
    for d in range(10):
        d_str = str(d)
        atraso = 0
        for draw in reversed(historico_centenas[:-1]):
            if d_str in draw: break
            atraso += 1
        atrasos[d_str] = atraso

    # 2. Frequência (Quantas vezes apareceu nos últimos 10 sorteios - 1º ao 5º)
    freq_recente = {str(d): 0 for d in range(10)}
    ultimos_10 = historico_centenas[-11:-1]
    for draw in ultimos_10:
        for d_str in set(draw): 
            freq_recente[d_str] += 1

    # 3. Transição de Cadeia de Markov (Se a tropa atual apareceu no passado, quem veio no próximo?)
    transicoes = {str(d): 0 for d in range(10)}
    total_transicoes = 0
    for i in range(len(historico_centenas) - 1):
        draw_atual = historico_centenas[i]
        draw_next = historico_centenas[i+1]
        
        # Se pelo menos um dos algarismos da tropa atual estava no passado
        if any(c in ultimas_centenas for c in draw_atual):
            for c_next in set(draw_next):
                transicoes[c_next] += 1
            total_transicoes += 1

    # 4. Cálculo de Pontuação Tática
    scores = {}
    for d in range(10):
        d_str = str(d)
        tx_transicao = (transicoes[d_str] / total_transicoes * 100) if total_transicoes > 0 else 0.0
        
        # Fórmula: Peso equilibrado entre Markov (Atração), Frequência (Tendência) e Atraso (Pressão)
        score = (tx_transicao * 0.5) + (freq_recente[d_str] * 2.0) + (min(atrasos[d_str], 15) * 1.5)
        
        scores[d_str] = {
            "score": score,
            "atraso": atrasos[d_str],
            "freq": freq_recente[d_str],
            "transicao": tx_transicao
        }

    # Ordena pelo maior score
    rank = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
    top_digit = rank[0][0]
    top_data = rank[0][1]

    return {
        "ultimas": ultimas_centenas,
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
                    dt = normalizar_data(row[0])
                    hr = normalizar_hora(row[1])
                    if dt:
                        chave = f"{dt.strftime('%Y-%m-%d')}|{hr}"
                        row[0] = dt.strftime('%Y-%m-%d')
                        row[1] = hr
                        dados_unicos[chave] = row
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda r: datetime.strptime(f"{r[0]} {r[1]}", "%Y-%m-%d %H:%M"))
            ws.clear()
            ws.append_row(cabecalho)
            if lista_final: ws.append_rows(lista_final)
            return f"Sucesso! Reduzido de {len(raw)-1} para {len(lista_final)} registros."
        except Exception as e: return f"Erro: {e}"
    return "Erro Conexão"

st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR TÁTICO (Home)":
    st.title("👁️ OLHO DE HÓRUS (RADAR DE CENTENAS)")
    st.markdown("O sistema ignora as milhares e escaneia cirurgicamente a coluna das **CENTENAS do 1º ao 5º Prêmio**. Monitorando TRADICIONAL, LOTEP e CAMINHO DA SORTE.")
    
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
        st.info("⚠️ Sem dados suficientes ou bancas offline.")
    else:
        # Ordena pelo maior score tático
        ranking_global.sort(key=lambda x: x['score'], reverse=True)
        
        st.markdown("### 🏆 ALVOS DE DISPARO (CENTENAS 1º AO 5º)")
        
        html_final = ""
        for idx, alvo in enumerate(ranking_global):
            banca_nome = alvo['banca']
            tropa = ", ".join(alvo['ultimas'])
            digito = alvo['top_digit']
            
            html_ranking = (
                f'<div class="card-ranking">'
                f'<h3 style="margin:0 0 10px 0; color:#fff;">#{idx+1} | Banca: {banca_nome}</h3>'
                f'<div style="background-color:#222; padding:15px; border-radius:8px;">'
                f'  <p style="margin:0 0 10px 0; color:#aaa; font-size:1.1em;">Últimas Centenas no Globo (1º ao 5º): <b>{tropa}</b></p>'
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
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.sidebar.date_input("Escolha:", date.today())
            
            lista_horarios = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca.weekday() in [2, 5]: 
                if "20:00" in lista_horarios:
                    lista_horarios[lista_horarios.index("20:00")] = "19:30"
                    
            horario_busca = st.selectbox("Horário:", lista_horarios)
            
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
                                    st.toast(f"Duplo Sucesso! Inteligência atualizada.", icon="✅")
                                elif tipo_ext == "DUAL_PENTA":
                                    row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios]
                                    ws_dez.append_row(row_dez)
                                    if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                    st.toast(f"Motor Duplo Acionado! Dados salvos na base e no Vitorino.", icon="✅")
                                time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro na Planilha")
                
    elif modo_extracao == "🌪️ Em Massa (Turbo)": 
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        
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
                buffer_dez = []
                buffer_m = []
                
                for dia in lista_datas:
                    for hora_base in config['horarios']:
                        hora_efetiva = hora_base
                        if "CAMINHO" in banca_selecionada and dia.weekday() in [2, 5]:
                            if hora_base == "20:00":
                                hora_efetiva = "19:30"
                                
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
                status.text("🚚 Sincronizando Matrizes Fantasmas e Visuais...")
                if buffer_dez: ws_dez.append_rows(buffer_dez)
                if buffer_m and ws_milhar: ws_milhar.append_rows(buffer_m)
                bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos registros."); time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão")
            
    elif modo_extracao == "✍️ Manual":
        with st.sidebar.expander("📝 Lançar Manualmente", expanded=True):
            opcao_data_man = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key="data_man")
            if opcao_data_man == "Hoje": data_busca = date.today()
            elif opcao_data_man == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.date_input("Escolha:", date.today(), key="data_pick_man")
            
            lista_horarios = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca.weekday() in [2, 5]: 
                if "20:00" in lista_horarios:
                    lista_horarios[lista_horarios.index("20:00")] = "19:30"
                    
            horario_busca = st.selectbox("Horário:", lista_horarios, key="hora_man")
            
            st.markdown("🎯 **Preencha as Milhares (4 dígitos):**")
            p1 = st.text_input("1º Prêmio", max_chars=4, key="man_p1")
            p2 = st.text_input("2º Prêmio", max_chars=4, key="man_p2")
            p3 = st.text_input("3º Prêmio", max_chars=4, key="man_p3")
            p4 = st.text_input("4º Prêmio", max_chars=4, key="man_p4")
            p5 = st.text_input("5º Prêmio", max_chars=4, key="man_p5")
            
            if st.button("💾 Salvar Resultado", key="btn_salvar_man", use_container_width=True):
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
                    with st.spinner(f"Salvando {horario_busca} manualmente..."):
                        try: 
                            existentes = ws_dez.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            if tipo_ext == "DUAL_SOLO":
                                row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca, premios_finais[0][-2:], "00", "00", "00", "00"]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios_finais)
                                st.toast(f"Lançamento Manual Salvo!", icon="✅")
                            elif tipo_ext == "DUAL_PENTA":
                                row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios_finais]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios_finais)
                                st.toast(f"Lançamento Manual Salvo com Sucesso!", icon="✅")
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
                    alvo_digito = res_centena['top_digit']
                    
                    with st.container(border=True):
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
