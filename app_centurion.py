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
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="CENTURION 46 - V23.0 Stable", page_icon="🛡️", layout="wide")

# Configuração das Bancas
CONFIG_BANCAS = {
    "LOTEP": { "display": "LOTEP (Dezenas)", "aba": "BASE_LOTEP_DEZ", "slug": "lotep", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHO": { "display": "CAMINHO (Dezenas)", "aba": "BASE_CAMINHO_DEZ", "slug": "caminho-da-sorte", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "19:30", "20:00", "21:00"] },
    "MONTE": { "display": "MONTE CARLOS (Dezenas)", "aba": "BASE_MONTE_DEZ", "slug": "nordeste-monte-carlos", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] },
    "TRADICIONAL": { "display": "TRADICIONAL (1º Prêmio)", "aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] }
}

# Estilo Visual Mínimo (Nativo)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (SEM CACHE - LIVE) ---
# =============================================================================

def conectar_planilha(nome_aba):
    """Conecta ao Google Sheets (Conexão Direta)."""
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(creds)
        try:
            sh = gc.open("CentralBichos")
            return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_historico_dezenas(nome_aba):
    """Baixa os dados da planilha em tempo real."""
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados = []
            for row in raw[1:]:
                if len(row) >= 3:
                    raw_dezenas = [str(d).strip().zfill(2) for d in row[2:] if str(d).strip().isdigit()]
                    if "TRADICIONAL" in nome_aba:
                        while len(raw_dezenas) < 5: raw_dezenas.append("00")
                    dados.append({"data": row[0], "hora": row[1], "dezenas": raw_dezenas[:5]})
            return dados
        except: return [] 
    return []

def obter_chaves_existentes(ws):
    """Lê chaves existentes para evitar duplicidade."""
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

def raspar_dezenas_site(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Site"
        soup = BeautifulSoup(r.text, 'html.parser')
        
        alvos_possiveis = [horario_alvo, f"{horario_alvo}h", f"{horario_alvo}H"]
        if ":00" in horario_alvo:
            hora_simples = horario_alvo.split(':')[0]
            alvos_possiveis.extend([f"{hora_simples}h", f"{hora_simples}H", f"{hora_simples} h"])
        if ":20" in horario_alvo:
             alvos_possiveis.append(f"{horario_alvo}h") 

        for alvo in alvos_possiveis:
            headers_found = soup.find_all(string=re.compile(re.escape(alvo)))
            for header_text in headers_found:
                if "FEDERAL" in header_text.upper(): continue
                
                element = header_text.parent
                tabela = element.find_next('table')
                if tabela:
                    dezenas_encontradas = []
                    linhas = tabela.find_all('tr')
                    for linha in linhas:
                        cols = linha.find_all('td')
                        if len(cols) >= 2:
                            premio_txt = cols[0].get_text().strip()
                            numero_txt = cols[1].get_text().strip()
                            nums_premio = re.findall(r'\d+', premio_txt)
                            
                            if banca_key == "TRADICIONAL":
                                if nums_premio and int(nums_premio[0]) == 1:
                                    if numero_txt.isdigit() and len(numero_txt) >= 2:
                                        dezena = numero_txt[-2:]
                                        dezenas_encontradas.append(dezena)
                                        while len(dezenas_encontradas) < 5: dezenas_encontradas.append("00")
                                        return dezenas_encontradas, f"Sucesso"
                            elif nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                if numero_txt.isdigit() and len(numero_txt) >= 2:
                                    dezena = numero_txt[-2:]
                                    dezenas_encontradas.append(dezena)
                    
                    if banca_key != "TRADICIONAL" and len(dezenas_encontradas) >= 5:
                        return dezenas_encontradas[:5], "Sucesso"
        return None, f"Horário {horario_alvo} do dia {data_alvo.strftime('%d/%m/%Y')} não encontrado."
    except Exception as e: return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA PURE (SEM CACHE) ---
# =============================================================================

def treinar_oraculo_dezenas(historico, indice_premio):
    if not HAS_AI or len(historico) < 50: return [], 0
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    try:
        dezenas_alvo = [j['dezenas'][indice_premio] for j in historico if 'data_dt' in df.columns]
    except: return [], 0
    df = df.iloc[:len(dezenas_alvo)]
    df['target_dezena'] = dezenas_alvo
    df['target_futuro'] = df['target_dezena'].shift(-1)
    
    # Reduzido para os últimos 150 para ganhar performance sem cache
    df_treino = df.dropna().tail(150)
    
    if len(df_treino) < 30: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target_dezena']]
    y = df_treino['target_futuro']
    
    # Menos estimadores para ser mais rápido em tempo real
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    ultimo_real = df.iloc[-1]
    X_novo = pd.DataFrame({
        'dia_semana': [ultimo_real['dia_semana']],
        'hora_code': [ultimo_real['hora_code']],
        'target_dezena': [ultimo_real['target_dezena']]
    })
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking_ia = []
    for i, prob in enumerate(probs):
        dezena = classes[i]
        ranking_ia.append((dezena, prob))
    ranking_ia.sort(key=lambda x: x[1], reverse=True)
    return ranking_ia, (ranking_ia[0][1] * 100)

def identificar_dezenas_saturadas(historico, indice_premio):
    if len(historico) < 40: return []
    recorte = historico[-40:]
    try:
        dezenas = [j['dezenas'][indice_premio] for j in recorte]
        contagem = Counter(dezenas)
        saturadas = [d for d, qtd in contagem.items() if qtd >= 4]
        return saturadas
    except: return []

def gerar_legiao_46_ai_pure(historico, indice_premio):
    if not historico: return [], [], 0
    ranking_ia, confianca = treinar_oraculo_dezenas(historico, indice_premio)
    if not ranking_ia: return [], [], 0
    saturadas = identificar_dezenas_saturadas(historico, indice_premio)
    palpite_final = []
    cortadas_log = []
    for dezena, prob in ranking_ia:
        if len(palpite_final) >= 46: break
        if dezena in saturadas:
            cortadas_log.append(dezena)
            continue 
        palpite_final.append(dezena)
    if len(palpite_final) < 46:
        for dezena, prob in ranking_ia:
            if len(palpite_final) >= 46: break
            if dezena not in palpite_final: palpite_final.append(dezena)
    return sorted(palpite_final), cortadas_log, confianca

def calcular_metricas_ai_pure(historico, indice_premio):
    if len(historico) < 10: return 0, 0, 0, 0
    total = len(historico)
    # Analisa últimos 50 jogos para performance (sem cache, reduzir range é bom)
    inicio = max(50, total - 50) 
    max_loss = 0; seq_loss = 0
    max_win = 0; seq_win = 0
    
    # Loop Otimizado
    for i in range(inicio, total):
        target_dezena = historico[i]['dezenas'][indice_premio]
        # Treina com dados passados
        hist_parcial = historico[:i]
        palpite, _, _ = gerar_legiao_46_ai_pure(hist_parcial, indice_premio)
        win = target_dezena in palpite
        if win:
            seq_loss = 0; seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0; seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    # Atual
    atual_loss = 0; atual_win = 0
    idx = -1
    target_last = historico[idx]['dezenas'][indice_premio]
    palpite_last, _, _ = gerar_legiao_46_ai_pure(historico[:idx], indice_premio)
    win_last = target_last in palpite_last
    
    if win_last:
        atual_win = 1
        for k in range(2, 10): # Reduzido para 10 para velocidade
            target = historico[-k]['dezenas'][indice_premio]
            palp, _, _ = gerar_legiao_46_ai_pure(historico[:-k], indice_premio)
            if target in palp: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 10):
            target = historico[-k]['dezenas'][indice_premio]
            palp, _, _ = gerar_legiao_46_ai_pure(historico[:-k], indice_premio)
            if target not in palp: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

# --- IA UNIDADES ---
def treinar_oraculo_unidades(historico):
    if not HAS_AI or len(historico) < 50: return [], 0
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    try:
        unidades_alvo = [int(j['dezenas'][0][-1]) for j in historico if 'data_dt' in df.columns]
    except: return [], 0
    df = df.iloc[:len(unidades_alvo)]
    df['target_uni'] = unidades_alvo
    df['target_futuro'] = df['target_uni'].shift(-1)
    
    df_treino = df.dropna().tail(150)
    if len(df_treino) < 30: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target_uni']]
    y = df_treino['target_futuro']
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    ultimo_real = df.iloc[-1]
    X_novo = pd.DataFrame({
        'dia_semana': [ultimo_real['dia_semana']],
        'hora_code': [ultimo_real['hora_code']],
        'target_uni': [ultimo_real['target_uni']]
    })
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking_uni = []
    for i, prob in enumerate(probs):
        uni = int(classes[i])
        ranking_uni.append((uni, prob))
    ranking_uni.sort(key=lambda x: x[1], reverse=True)
    return ranking_uni, (ranking_uni[0][1] * 100)

def calcular_metricas_unidade_ia(historico):
    if len(historico) < 10: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(50, total - 50)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    for i in range(inicio, total):
        try:
            target = int(historico[i]['dezenas'][0][-1])
            hist_p = historico[:i]
            rank_u, _ = treinar_oraculo_unidades(hist_p)
            top_5_ia = [u for u, p in rank_u[:5]]
            if target in top_5_ia:
                seq_loss = 0; seq_win += 1
                if seq_win > max_win: max_win = seq_win
            else:
                seq_win = 0; seq_loss += 1
                if seq_loss > max_loss: max_loss = seq_loss
        except: continue
    
    atual_loss = 0; atual_win = 0
    idx = -1
    try:
        target = int(historico[idx]['dezenas'][0][-1])
        rank_u, _ = treinar_oraculo_unidades(historico[:idx])
        top_5_ia = [u for u, p in rank_u[:5]]
        if target in top_5_ia:
            atual_win = 1
            for k in range(2, 10):
                t = int(historico[-k]['dezenas'][0][-1])
                ru, _ = treinar_oraculo_unidades(historico[:-k])
                t5 = [u for u, p in ru[:5]]
                if t in t5: atual_win += 1
                else: break
        else:
            atual_loss = 1
            for k in range(2, 10):
                t = int(historico[-k]['dezenas'][0][-1])
                ru, _ = treinar_oraculo_unidades(historico[:-k])
                t5 = [u for u, p in ru[:5]]
                if t not in t5: atual_loss += 1
                else: break
    except: pass
    return atual_loss, max_loss, atual_win, max_win

# =============================================================================
# --- 4. EXIBIÇÃO ---
# =============================================================================

def analisar_padroes_futuros(historico, indice_premio):
    if len(historico) < 10: return None, []
    ultima_dezena_real = historico[-1]['dezenas'][indice_premio]
    encontrados = []
    for i in range(len(historico) - 2, -1, -1):
        try:
            if historico[i]['dezenas'][indice_premio] == ultima_dezena_real:
                encontrados.append({ "Data": historico[i+1]['data'], "Hora": historico[i+1]['hora'], "Veio Dezena": historico[i+1]['dezenas'][indice_premio] })
                if len(encontrados) >= 5: break
        except: continue
    return ultima_dezena_real, encontrados

def analisar_padroes_unidade(historico):
    if len(historico) < 10: return None, []
    try: ultima_uni = historico[-1]['dezenas'][0][-1]
    except: return None, []
    encontrados = []
    for i in range(len(historico) - 2, -1, -1):
        try:
            if historico[i]['dezenas'][0][-1] == ultima_uni:
                encontrados.append({ "Data": historico[i+1]['data'], "Hora": historico[i+1]['hora'], "Veio Final": historico[i+1]['dezenas'][0][-1] })
                if len(encontrados) >= 5: break
        except: continue
    return ultima_uni, encontrados

def executar_backtest_centurion(historico, indice_premio):
    if len(historico) < 60: return []
    resultados = []
    for i in range(1, 5):
        idx = -i
        target = historico[idx]['dezenas'][indice_premio]
        palpite, _, _ = gerar_legiao_46_ai_pure(historico[:idx], indice_premio)
        win = target in palpite
        resultados.append({'index': i, 'dezena': target, 'win': win})
    return resultados

def executar_backtest_unidade(historico):
    if len(historico) < 60: return []
    resultados = []
    for i in range(1, 5):
        idx = -i
        try:
            target = int(historico[idx]['dezenas'][0][-1])
            rank_u, _ = treinar_oraculo_unidades(historico[:idx])
            top_5_ia = [u for u, p in rank_u[:5]]
            win = target in top_5_ia
            resultados.append({'index': i, 'real': target, 'win': win})
        except: continue
    return resultados

def tela_dashboard_global():
    st.title("🛡️ CENTURION COMMAND CENTER")
    st.markdown("### 📡 Radar Global de Oportunidades")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Bancas", "4", "Lotep, Caminho, Monte, Trad")
    alertas_criticos = []
    
    with st.spinner("Analisando todas as bancas em tempo real..."):
        for banca_key, config in CONFIG_BANCAS.items():
            historico = carregar_historico_dezenas(config['aba'])
            if len(historico) > 50:
                limit_range = 1 if banca_key == "TRADICIONAL" else 5
                for i in range(limit_range):
                    loss, max_loss, win, max_win = calcular_metricas_ai_pure(historico, i)
                    if max_loss > 0:
                        if loss >= max_loss: alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": loss, "rec": max_loss, "tipo": "CRITICO"})
                        elif loss == (max_loss - 1): alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": loss, "rec": max_loss, "tipo": "PERIGO"})
                    if max_win > 2 and win == (max_win - 1):
                         alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": win, "rec": max_win, "tipo": "VITORIA"})
                if banca_key == "TRADICIONAL":
                    u_loss, u_max_loss, u_win, u_max_win = calcular_metricas_unidade_ia(historico)
                    if u_max_loss > 0:
                        if u_loss >= u_max_loss: alertas_criticos.append({"banca": "TRADICIONAL (Unidade IA)", "premio": "Sniper 50%", "val": u_loss, "rec": u_max_loss, "tipo": "CRITICO_UNI"})
                        elif u_loss == (u_max_loss - 1): alertas_criticos.append({"banca": "TRADICIONAL (Unidade IA)", "premio": "Sniper 50%", "val": u_loss, "rec": u_max_loss, "tipo": "PERIGO_UNI"})

    col2.metric("Sinais no Radar", f"{len(alertas_criticos)}", "Win/Loss")
    col3.metric("Status Base", "Online", "Google Sheets")
    st.markdown("---")
    
    if alertas_criticos:
        st.subheader("🚨 Zonas de Interesse Identificadas")
        for alerta in alertas_criticos:
            if alerta['tipo'] == "CRITICO":
                st.error(f"🚨 **{alerta['banca']} - {alerta['premio']}** | RECORDE ATINGIDO! {alerta['val']} Derrotas (Max: {alerta['rec']})")
            elif alerta['tipo'] == "PERIGO":
                st.warning(f"⚠️ **{alerta['banca']} - {alerta['premio']}** | ZONA DE PERIGO: {alerta['val']} Derrotas (Max: {alerta['rec']})")
            elif alerta['tipo'] == "VITORIA":
                st.success(f"🤑 **{alerta['banca']} - {alerta['premio']}** | SEQUÊNCIA DE VITÓRIAS! {alerta['val']} Vitórias (Max: {alerta['rec']})")
            elif alerta['tipo'] == "CRITICO_UNI":
                st.error(f"🎯 **{alerta['banca']} - {alerta['premio']}** | SNIPER CRÍTICO! {alerta['val']} Derrotas (Max: {alerta['rec']})")
            elif alerta['tipo'] == "PERIGO_UNI":
                st.warning(f"🎯 **{alerta['banca']} - {alerta['premio']}** | SNIPER ALERTA! {alerta['val']} Derrotas (Max: {alerta['rec']})")
    else:
        st.success("✅ O Radar não detectou anomalias críticas no momento.")

# =============================================================================
# --- 5. APP PRINCIPAL ---
# =============================================================================
menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

st.sidebar.markdown("---")
st.sidebar.link_button("🛡️ Ir para App PENTÁGONO", "https://seu-app-pentagono.streamlit.app")
st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    tela_dashboard_global()

else:
    banca_selecionada = escolha_menu
    conf = CONFIG_BANCAS[banca_selecionada]
    
    url_site_base = f"https://www.resultadofacil.com.br/resultados-{conf['slug']}-de-hoje"
    st.sidebar.link_button("🔗 Ver Site Oficial", url_site_base)
    
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária (1 Sorteio)", "🌪️ Em Massa (Turbo)"])
    st.sidebar.markdown("---")

    if modo_extracao == "🎯 Unitária (1 Sorteio)":
        st.sidebar.subheader("Extração Unitária")
        opt_data = st.sidebar.radio("Data:", ["Hoje", "Ontem", "Outra"])
        if opt_data == "Hoje": data_busca = date.today()
        elif opt_data == "Ontem": data_busca = date.today() - timedelta(days=1)
        else: data_busca = st.sidebar.date_input("Escolha a Data:", date.today())
        
        lista_horarios = conf['horarios'].copy()
        if banca_selecionada == "CAMINHO" and (data_busca.weekday() == 2 or data_busca.weekday() == 5):
            lista_horarios = [h.replace("20:00", "19:30") for h in lista_horarios]

        hora_busca = st.sidebar.selectbox("Horário:", lista_horarios)
        
        if st.sidebar.button("🚀 Baixar Sorteio"):
            ws = conectar_planilha(conf['aba'])
            if ws:
                with st.spinner(f"Buscando {hora_busca}..."):
                    # Busca FRESH para evitar duplicidade
                    chaves_existentes = obter_chaves_existentes(ws)
                    chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{hora_busca}"
                    
                    if chave_atual in chaves_existentes:
                        st.sidebar.warning(f"⚠️ Resultado {hora_busca} já existe na planilha!")
                    else:
                        dezenas, msg = raspar_dezenas_site(banca_selecionada, data_busca, hora_busca)
                        if dezenas:
                            ws.append_row([data_busca.strftime('%Y-%m-%d'), hora_busca] + dezenas)
                            st.sidebar.success(f"✅ Salvo! {dezenas}")
                            time.sleep(1); st.rerun()
                        else: st.sidebar.error(f"❌ {msg}")
            else: st.sidebar.error("Erro Conexão Planilha")

    else:
        st.sidebar.subheader("Extração em Massa")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        
        if st.sidebar.button("🚀 INICIAR TURBO"):
            ws = conectar_planilha(conf['aba'])
            if ws:
                status = st.sidebar.empty()
                bar = st.sidebar.progress(0)
                
                chaves_existentes = obter_chaves_existentes(ws)
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(conf['horarios'])
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    for hora in conf['horarios']:
                        op_atual += 1
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                        if chave_atual in chaves_existentes: continue
                        
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue

                        dezenas, msg = raspar_dezenas_site(banca_selecionada, dia, hora)
                        if dezenas:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + dezenas)
                            sucessos += 1
                            chaves_existentes.append(chave_atual)
                        time.sleep(1.0)
                bar.progress(100)
                status.success(f"🏁 Concluído! {sucessos} novos sorteios.")
                time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão Planilha")

    st.sidebar.markdown("---")
    with st.sidebar.expander("✍️ Inserção Manual"):
        man_data = st.sidebar.date_input("Data", date.today())
        h_manual_list = conf['horarios'].copy()
        if banca_selecionada == "CAMINHO" and "19:30" not in h_manual_list: h_manual_list.append("19:30"); h_manual_list.sort()
        man_hora = st.sidebar.selectbox("Horário", h_manual_list)
        
        c1, c2, c3, c4, c5 = st.sidebar.columns(5)
        p1 = c1.text_input("1", max_chars=2, key="mp1")
        if banca_selecionada == "TRADICIONAL":
            st.caption("Apenas 1º prêmio necessário.")
            p2, p3, p4, p5 = "00", "00", "00", "00"
        else:
            p2 = c2.text_input("2", max_chars=2, key="mp2")
            p3 = c3.text_input("3", max_chars=2, key="mp3")
            p4 = c4.text_input("4", max_chars=2, key="mp4")
            p5 = c5.text_input("5", max_chars=2, key="mp5")
        
        if st.sidebar.button("💾 Salvar"):
            man_dezenas = [p1, p2, p3, p4, p5]
            if p1.isdigit() and len(p1) == 2:
                ws = conectar_planilha(conf['aba'])
                if ws:
                    chaves_existentes = obter_chaves_existentes(ws)
                    chave_atual = f"{man_data.strftime('%Y-%m-%d')}|{man_hora}"
                    if chave_atual in chaves_existentes: st.sidebar.warning("Já existe!")
                    else:
                        ws.append_row([man_data.strftime('%Y-%m-%d'), man_hora] + man_dezenas)
                        st.sidebar.success("Salvo!"); time.sleep(1); st.rerun()
                else: st.sidebar.error("Erro Conexão")
            else: st.sidebar.error("Preencha corretamente")

    st.subheader(f"Analise: {conf['display']}")
    historico = carregar_historico_dezenas(conf['aba'])

    if len(historico) == 0:
        st.warning(f"⚠️ Base vazia. Verifique se a aba '{conf['aba']}' existe na planilha.")
    else:
        ult = historico[-1]
        st.info(f"📅 **STATUS ATUAL:** Último: **{ult['data']}** às **{ult['hora']}**.")

    tabs = st.tabs(["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"])

    for i, tab in enumerate(tabs):
        with tab:
            if banca_selecionada == "TRADICIONAL" and i > 0:
                st.warning("⚠️ Esta banca foca exclusivamente no 1º Prêmio (Cabeça).")
                continue

            lista_final, cortadas, confianca_ia = gerar_legiao_46_ai_pure(historico, i)
            loss, max_loss, win, max_win = calcular_metricas_ai_pure(historico, i)
            
            if HAS_AI:
                with st.container(border=True):
                    st.markdown("### 🧠 Oráculo IA (Pure Dezenas)")
                    st.info(f"Confiança do Modelo: {confianca_ia:.1f}%")
            
            if loss >= max_loss and max_loss > 0:
                st.error(f"🚨 **ALERTA MÁXIMO:** {loss} Derrotas Seguidas (Recorde Atingido!)")
            
            with st.container(border=True):
                if cortadas:
                    st.warning(f"🚫 {len(cortadas)} Dezenas Saturadas Cortadas")
                
                st.markdown(f"<h2 style='text-align: center; color: #00ff00;'>LEGIÃO 46 - {i+1}º PRÊMIO</h2>", unsafe_allow_html=True)
                st.caption("Estratégia V23.0: AI Pure + Filtro Saturação")
                st.code(", ".join(lista_final), language="text")
            
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Derrotas", f"{loss}", f"Max: {max_loss}", delta_color="inverse")
            col_m2.metric("Vitórias", f"{win}", f"Max: {max_win}")
            
            bt_results = executar_backtest_centurion(historico, i)
            if bt_results:
                st.markdown("### ⏪ Performance Recente")
                cols_bt = st.columns(len(bt_results))
                for idx_bt, res in enumerate(reversed(bt_results)):
                    with cols_bt[idx_bt]:
                        lbl = "VITÓRIA" if res['win'] else "DERROTA"
                        val = res['dezena']
                        if res['win']: st.success(f"{val} ({lbl})")
                        else: st.error(f"{val} ({lbl})")

            st.markdown("---")
            
            ultima_dz_real, padroes_futuros = analisar_padroes_futuros(historico, i)
            if padroes_futuros:
                st.markdown(f"#### 🔍 Rastreador de Padrões (DEZENA - Última: **{ultima_dz_real}**)")
                st.caption(f"Nas últimas 5 vezes que a dezena {ultima_dz_real} saiu, veja o que veio depois:")
                st.table(pd.DataFrame(padroes_futuros))
            
            if banca_selecionada == "TRADICIONAL":
                if HAS_AI:
                    rank_unidades, conf_uni = treinar_oraculo_unidades(historico)
                    top_5_uni = [str(u) for u, p in rank_unidades[:5]]
                    
                    with st.container(border=True):
                        st.markdown("### 🧠 Oráculo IA (Unidades)")
                        st.info(f"Confiança: {conf_uni:.1f}%")
                        st.markdown(f"**Top 5 Finais:** {', '.join(top_5_uni)}")
                        st.caption("Estratégia Exclusiva de Final")
                
                u_loss, u_max, u_win, u_max_win = calcular_metricas_unidade_ia(historico)
                
                c_u1, c_u2 = st.columns(2)
                c_u1.metric("Uni Derrotas", f"{u_loss}", f"Max: {u_max}", delta_color="inverse")
                c_u2.metric("Uni Vitórias", f"{u_win}", f"Max: {u_max_win}")
                
                bt_sniper = executar_backtest_unidade(historico)
                if bt_sniper:
                    cols_ubt = st.columns(len(bt_sniper))
                    for idx_ubt, res in enumerate(reversed(bt_sniper)):
                        with cols_ubt[idx_ubt]:
                            lbl = "WIN" if res['win'] else "LOSS"
                            val = f"F{res['real']}"
                            if res['win']: st.success(f"{val}")
                            else: st.error(f"{val}")

                ultima_uni_real, padroes_uni = analisar_padroes_unidade(historico)
                if padroes_uni:
                    st.markdown(f"#### 🔍 Rastreador de Padrões (UNIDADE - Última: **{ultima_uni_real}**)")
                    st.caption(f"Nas últimas 5 vezes que a unidade {ultima_uni_real} saiu, veja o que veio depois:")
                    st.table(pd.DataFrame(padroes_uni))
