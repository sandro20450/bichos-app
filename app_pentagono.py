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

# --- IMPORTAÇÃO DA INTELIGÊNCIA ARTIFICIAL ---
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    HAS_AI = True
except ImportError:
    HAS_AI = False

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V49.0 Matrix Dezenas", page_icon="🛡️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": { "display_name": "LOTEP (1º ao 5º)", "nome_aba": "LOTEP_TOP5", "slug": "lotep", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHODASORTE": { "display_name": "CAMINHO (1º ao 5º)", "nome_aba": "CAMINHO_TOP5", "slug": "caminho-da-sorte", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "MONTECAI": { "display_name": "MONTE CARLOS (1º ao 5º)", "nome_aba": "MONTE_TOP5", "slug": "nordeste-monte-carlos", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] }
}

# MAPA DE GRUPOS E GÊMEAS (Para Matrix)
GRUPO_TO_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4
    inicio = fim - 3
    dezenas_do_grupo = []
    for n in range(inicio, fim + 1):
        d_str = "00" if n == 100 else f"{n:02}"
        dezenas_do_grupo.append(d_str)
    GRUPO_TO_DEZENAS[g] = dezenas_do_grupo

GEMEAS = ['00', '11', '22', '33', '44', '55', '66', '77', '88', '99']

# Estilo Visual Nativo
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #00ff00 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (DEZENAS) ---
# =============================================================================

def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_dados_dezenas_top5(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados = []
            for row in raw[1:]:
                # Espera formato: DATA | HORA | P1 | P2 | P3 | P4 | P5
                if len(row) >= 7:
                    # Tenta extrair as dezenas (últimos 2 dígitos)
                    dezenas = []
                    for p in row[2:7]:
                        p_str = str(p).strip()
                        if p_str.isdigit():
                            dezenas.append(p_str.zfill(2)[-2:]) # Garante 2 dígitos
                        else:
                            dezenas.append("00") # Fallback
                    
                    if len(dezenas) == 5:
                        dados.append({"data": row[0], "horario": row[1], "premios": dezenas})
            return dados
        except: return [] 
    return []

def obter_chaves_existentes(ws):
    try:
        raw = ws.get('A:B')
        chaves = []
        for row in raw:
            if len(row) >= 2:
                d = str(row[0]).strip()
                h = str(row[1]).strip()
                chaves.append(f"{d}|{h}")
        return chaves
    except: return []

def montar_url_correta(slug, data_alvo):
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_dezenas_top5(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    url = montar_url_correta(config['slug'], data_alvo)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Site"
        soup = BeautifulSoup(r.text, 'html.parser')
        
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        
        for tabela in tabelas:
            # Verifica se é tabela de prêmios
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                # Evita Federal misturada
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
                
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        # Normaliza hora
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
                                    
                                    # Extrai numero (milhar/centena)
                                    nums_premio = re.findall(r'\d+', premio_txt)
                                    if nums_premio:
                                        p_idx = int(nums_premio[0])
                                        if 1 <= p_idx <= 5:
                                            # Limpa e pega dezena
                                            clean_num = re.sub(r'\D', '', numero_txt)
                                            if len(clean_num) >= 2:
                                                dezenas_encontradas.append(clean_num[-2:])
                                                
                            if len(dezenas_encontradas) >= 5: 
                                return dezenas_encontradas[:5], "Sucesso"
                            else: 
                                return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA MATRIX DEZENAS (IGUAL CENTURION V27) ---
# =============================================================================

def analisar_filtros_avancados(historico, indice_premio):
    if len(historico) < 2: return [], [], []
    
    bloqueio_unidade = []
    bloqueio_gemeas = False
    bloqueio_linha = None 
    
    try:
        d_atual = historico[-1]['premios'][indice_premio]
        d_anterior = historico[-2]['premios'][indice_premio]
        
        u_atual = int(d_atual[-1])
        u_anterior = int(d_anterior[-1])
        
        # 1. Filtro Sequência Unidade
        if u_atual == (u_anterior + 1) or (u_anterior == 9 and u_atual == 0):
            prox = (u_atual + 1) % 10
            bloqueio_unidade.append(prox)
        if u_atual == (u_anterior - 1) or (u_anterior == 0 and u_atual == 9):
            prox = (u_atual - 1)
            if prox < 0: prox = 9
            bloqueio_unidade.append(prox)
            
        # 2. Filtro Gêmeas
        if d_atual in GEMEAS and d_anterior in GEMEAS:
            bloqueio_gemeas = True
            
        # 3. Filtro Linha
        if d_atual[0] == d_anterior[0]:
            bloqueio_linha = d_atual[0]
            
    except: pass
    
    return list(set(bloqueio_unidade)), bloqueio_gemeas, bloqueio_linha

def treinar_probabilidade_global(historico, indice_premio):
    if not HAS_AI or len(historico) < 30: 
        return {f"{i:02}": 0.5 for i in range(100)} 

    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['horario'])
    
    try:
        dezenas_alvo = [j['premios'][indice_premio] for j in historico if 'data_dt' in df.columns]
    except: return {}
    
    df = df.iloc[:len(dezenas_alvo)]
    df['target'] = dezenas_alvo
    df['target_futuro'] = df['target'].shift(-1)
    df_treino = df.dropna().tail(150)
    
    if len(df_treino) < 20: return {}
    
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro']
    
    modelo = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    mapa_probs = {c: 0.0 for c in [f"{i:02}" for i in range(100)]}
    for i, prob in enumerate(probs):
        mapa_probs[classes[i]] = prob
        
    return mapa_probs

def gerar_estrategia_matrix_50(historico, indice_premio):
    if not historico: return [], 0, {}
    
    mapa_ia = treinar_probabilidade_global(historico, indice_premio)
    if not mapa_ia: return [], 0, {}
    
    unis_proibidas, block_gemeas, block_linha = analisar_filtros_avancados(historico, indice_premio)
    
    palpite_matrix = []
    
    for g in range(1, 26):
        dezenas_candidatas = GRUPO_TO_DEZENAS[g]
        ranking_grupo = []
        for d in dezenas_candidatas:
            score = mapa_ia.get(d, 0.0)
            if int(d[-1]) in unis_proibidas: score -= 0.5
            if block_gemeas and d in GEMEAS: score -= 0.8
            if block_linha and d.startswith(block_linha): score -= 0.6
            ranking_grupo.append((d, score))
        
        ranking_grupo.sort(key=lambda x: x[1], reverse=True)
        top_2 = [x[0] for x in ranking_grupo[:2]]
        palpite_matrix.extend(top_2)
        
    conf_media = sum([mapa_ia.get(d, 0) for d in palpite_matrix]) / len(palpite_matrix) * 100 if palpite_matrix else 0
    
    info_filtros = {
        "uni": unis_proibidas,
        "gemeas": block_gemeas,
        "linha": block_linha
    }
    
    return sorted(palpite_matrix), conf_media, info_filtros

# =============================================================================
# --- 4. BACKTESTS (MATRIX) ---
# =============================================================================

def calcular_metricas_matrix(historico, indice_premio):
    if len(historico) < 20: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(20, total - 50)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    
    for i in range(inicio, total):
        target = historico[i]['premios'][indice_premio]
        hist_p = historico[:i]
        palpite, _, _ = gerar_estrategia_matrix_50(hist_p, indice_premio)
        
        if target in palpite:
            seq_loss = 0; seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0; seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    idx = -1; atual_loss = 0; atual_win = 0
    target = historico[idx]['premios'][indice_premio]
    palpite, _, _ = gerar_estrategia_matrix_50(historico[:idx], indice_premio)
    
    if target in palpite:
        atual_win = 1
        for k in range(2, 10):
            t = historico[-k]['premios'][indice_premio]
            p, _, _ = gerar_estrategia_matrix_50(historico[:-k], indice_premio)
            if t in p: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 10):
            t = historico[-k]['premios'][indice_premio]
            p, _, _ = gerar_estrategia_matrix_50(historico[:-k], indice_premio)
            if t not in p: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

def executar_backtest_recente_matrix(historico, indice_premio):
    results = []
    for i in range(1, 6):
        idx = -i
        target = historico[idx]['premios'][indice_premio]
        palp, _, _ = gerar_estrategia_matrix_50(historico[:idx], indice_premio)
        win = target in palp
        results.append({"val": target, "win": win})
    return results

def rastreador_padroes(historico, indice_premio):
    if len(historico) < 10: return []
    encontrados = []
    ultimo_real = historico[-1]['premios'][indice_premio]
    label = ultimo_real
    for i in range(len(historico)-2, -1, -1):
        if historico[i]['premios'][indice_premio] == ultimo_real:
            encontrados.append({ "Data": historico[i+1]['data'], "Veio": historico[i+1]['premios'][indice_premio] })
            if len(encontrados) >= 5: break
    return label, encontrados

# =============================================================================
# --- 5. INTERFACE (REPLICA CENTURION) ---
# =============================================================================

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

st.sidebar.markdown("---")
st.sidebar.link_button("🛡️ Ir para App CENTURION", "https://seu-app-centurion.streamlit.app") 
st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    st.title("🛡️ PENTÁGONO - MATRIX COMMAND")
    col1, col2 = st.columns(2)
    col1.metric("Estratégia", "Matrix 50 (Dezenas)")
    col2.metric("Status", "Online")
    st.info("Selecione uma banca no menu lateral para iniciar a análise Matrix.")

else:
    banca_selecionada = escolha_menu
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    st.sidebar.markdown("---")
    url_site = f"https://www.resultadofacil.com.br/resultados-{config_banca['slug']}-de-hoje"
    st.sidebar.link_button("🔗 Ver Site Oficial", url_site)
    st.sidebar.markdown("---")
    
    # --- MODO EXTRAÇÃO (DEZENAS) ---
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)"])
    
    if modo_extracao == "🎯 Unitária":
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.sidebar.date_input("Escolha:", date.today())
            
            horario_busca = st.selectbox("Horário:", config_banca['horarios'])
            
            if st.button("🚀 Baixar & Salvar"):
                ws = conectar_planilha(config_banca['nome_aba'])
                if ws:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try:
                            existentes = ws.get_all_values()
                            chaves = [f"{str(row[0]).strip()}|{str(row[1]).strip()}" for row in existentes if len(row)>1]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{horario_busca}"
                        
                        if chave_atual in chaves:
                            st.warning("Resultado já existe!")
                        else:
                            dezenas, msg = raspar_dezenas_top5(banca_selecionada, data_busca, horario_busca)
                            if dezenas:
                                row = [data_busca.strftime('%Y-%m-%d'), horario_busca] + dezenas
                                ws.append_row(row)
                                st.toast(f"Sucesso! {dezenas}", icon="✅")
                                time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro Planilha")
                
    else: # MODO TURBO
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        
        if st.sidebar.button("🚀 INICIAR TURBO"):
            ws = conectar_planilha(config_banca['nome_aba'])
            if ws:
                status = st.sidebar.empty()
                bar = st.sidebar.progress(0)
                try:
                    existentes = ws.get_all_values()
                    chaves = [f"{str(row[0]).strip()}|{str(row[1]).strip()}" for row in existentes if len(row)>1]
                except: chaves = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config_banca['horarios'])
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    for hora in config_banca['horarios']:
                        op_atual += 1
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                        
                        if chave_atual in chaves: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue

                        dezenas, msg = raspar_dezenas_top5(banca_selecionada, dia, hora)
                        if dezenas:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + dezenas)
                            sucessos += 1
                            chaves.append(chave_atual)
                        time.sleep(1.0)
                
                bar.progress(100)
                status.success(f"🏁 Concluído! {sucessos} novos sorteios.")
                time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão")

    # --- PÁGINA DA BANCA ---
    st.header(f"🔭 {config_banca['display_name']} - Matrix 50")
    
    with st.spinner("Carregando dados..."):
        historico = carregar_dados_dezenas_top5(config_banca['nome_aba'])

    if len(historico) > 0:
        ult = historico[-1]
        st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **Dezenas:** {', '.join(ult['premios'])}")
        
        nomes_posicoes = ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]
        abas = st.tabs(nomes_posicoes)
        
        for idx_aba, aba in enumerate(abas):
            with aba:
                # --- ANÁLISE MATRIX (POR PRÊMIO) ---
                lista_matrix, conf_dez, info_filtros = gerar_estrategia_matrix_50(historico, idx_aba)
                loss_d, max_loss_d, win_d, max_win_d = calcular_metricas_matrix(historico, idx_aba)
                
                if HAS_AI:
                    st.info(f"🧠 Confiança Média IA: {conf_dez:.1f}%")
                    filtros_ativos = []
                    if info_filtros['uni']: filtros_ativos.append(f"Unidades Proibidas: {info_filtros['uni']}")
                    if info_filtros['gemeas']: filtros_ativos.append("Anti-Trinca Gêmea")
                    if info_filtros['linha']: filtros_ativos.append(f"Anti-Fadiga Linha ({info_filtros['linha']}X)")
                    
                    if filtros_ativos:
                        st.warning(f"🚫 **Filtros Ativos:** {', '.join(filtros_ativos)}")
                    else:
                        st.success("✅ Nenhum filtro de bloqueio acionado. IA Pura.")
                
                if loss_d >= max_loss_d and max_loss_d > 0:
                    st.error(f"🚨 ALERTA: {loss_d} Derrotas (Recorde!)")
                
                with st.container(border=True):
                    st.markdown("### 50 Dezenas Selecionadas (Matrix Filter)")
                    st.code(", ".join(lista_matrix), language="text")
                    
                c1, c2 = st.columns(2)
                c1.metric("Derrotas", f"{loss_d}", f"Max: {max_loss_d}", delta_color="inverse")
                c2.metric("Vitórias", f"{win_d}", f"Max: {max_win_d}")
                
                st.markdown("**Histórico Recente (Matrix):**")
                bt_dez = executar_backtest_recente_matrix(historico, idx_aba)
                cols_bt = st.columns(5)
                for i, res in enumerate(reversed(bt_dez)):
                    with cols_bt[i]:
                        if res['win']: st.success(res['val'])
                        else: st.error(res['val'])
                        
                lbl_d, padroes_d = rastreador_padroes(historico, idx_aba)
                if padroes_d:
                    st.caption(f"Padrões após a dezena **{lbl_d}**:")
                    st.table(pd.DataFrame(padroes_d))

    else:
        st.warning("⚠️ Base vazia.")
