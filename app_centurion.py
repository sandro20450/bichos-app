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
# --- 1. CONFIGURAÇÕES (MODO ESPECIALISTA) ---
# =============================================================================
st.set_page_config(page_title="CENTURION TRADICIONAL - V30.0 Bug Fix", page_icon="🎯", layout="wide")

CONFIG_TRADICIONAL = {
    "display": "TRADICIONAL (1º Prêmio)", 
    "aba": "BASE_TRADICIONAL_DEZ", 
    "slug": "loteria-tradicional", 
    "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] 
}

# MAPEAMENTO DE GRUPOS E GÊMEAS
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
# --- 2. CONEXÃO E RASPAGEM (LIVE) ---
# =============================================================================

def conectar_planilha():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(creds)
        try:
            sh = gc.open("CentralBichos")
            return sh.worksheet(CONFIG_TRADICIONAL['aba'])
        except: return None
    return None

def carregar_historico():
    ws = conectar_planilha()
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados = []
            for row in raw[1:]:
                if len(row) >= 3:
                    val_raw = str(row[2]).strip()
                    d1 = val_raw.zfill(2) if val_raw.isdigit() else "00"
                    dezenas = [d1, "00", "00", "00", "00"]
                    dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
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

def raspar_site(data_alvo, horario_alvo):
    url = f"https://www.resultadofacil.com.br/resultados-{CONFIG_TRADICIONAL['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Site"
        soup = BeautifulSoup(r.text, 'html.parser')
        
        alvos_possiveis = [horario_alvo, f"{horario_alvo}h", f"{horario_alvo}H"]
        if ":00" in horario_alvo:
            hora_simples = horario_alvo.split(':')[0]
            alvos_possiveis.extend([f"{hora_simples}h", f"{hora_simples}H"])
        
        for alvo in alvos_possiveis:
            headers_found = soup.find_all(string=re.compile(re.escape(alvo)))
            for header_text in headers_found:
                if "FEDERAL" in header_text.upper(): continue
                element = header_text.parent
                tabela = element.find_next('table')
                if tabela:
                    linhas = tabela.find_all('tr')
                    for linha in linhas:
                        cols = linha.find_all('td')
                        if len(cols) >= 2:
                            premio_txt = cols[0].get_text().strip()
                            numero_txt = cols[1].get_text().strip()
                            nums_premio = re.findall(r'\d+', premio_txt)
                            if nums_premio and int(nums_premio[0]) == 1:
                                if numero_txt.isdigit() and len(numero_txt) >= 2:
                                    dezena = numero_txt[-2:]
                                    return [dezena, "00", "00", "00", "00"], "Sucesso"
        return None, f"Horário {horario_alvo} não encontrado."
    except Exception as e: return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA MATRIX + FILTROS ---
# =============================================================================

def analisar_sequencias_profundas(lista_wins):
    if not lista_wins: return 0, 0, 0
    sequencias = []
    atual = 0
    for w in lista_wins:
        if w: atual += 1
        else:
            if atual > 0: sequencias.append(atual)
            atual = 0
    if atual > 0: sequencias.append(atual)
    if not sequencias: return 0, 0, 0
    maximo = max(sequencias)
    ocorrencias = sequencias.count(maximo)
    total_jogos = len(lista_wins)
    ciclo = int(total_jogos / ocorrencias) if ocorrencias > 0 else 0
    return maximo, ocorrencias, ciclo

def analisar_filtros_avancados(historico):
    if len(historico) < 2: return [], [], []
    bloqueio_unidade = []
    bloqueio_gemeas = False
    bloqueio_linha = None 
    try:
        d_atual = historico[-1]['dezenas'][0]
        d_anterior = historico[-2]['dezenas'][0]
        u_atual = int(d_atual[-1])
        u_anterior = int(d_anterior[-1])
        if u_atual == (u_anterior + 1) or (u_anterior == 9 and u_atual == 0):
            prox = (u_atual + 1) % 10
            bloqueio_unidade.append(prox)
        if u_atual == (u_anterior - 1) or (u_anterior == 0 and u_atual == 9):
            prox = (u_atual - 1)
            if prox < 0: prox = 9
            bloqueio_unidade.append(prox)
        if d_atual in GEMEAS and d_anterior in GEMEAS:
            bloqueio_gemeas = True
        if d_atual[0] == d_anterior[0]:
            bloqueio_linha = d_atual[0]
    except: pass
    return list(set(bloqueio_unidade)), bloqueio_gemeas, bloqueio_linha

def treinar_probabilidade_global(historico):
    if not HAS_AI or len(historico) < 30: 
        return {f"{i:02}": 0.01 for i in range(100)} 

    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    
    try:
        dezenas_alvo = [str(j['dezenas'][0]).zfill(2) for j in historico if 'data_dt' in df.columns]
    except: return {}
    
    df = df.iloc[:len(dezenas_alvo)]
    df['target'] = dezenas_alvo
    df['target_futuro'] = df['target'].shift(-1)
    df_treino = df.dropna().tail(150)
    
    if len(df_treino) < 20: return {}
    
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro'].astype(str)
    
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    mapa_probs = {c: 0.0 for c in [f"{i:02}" for i in range(100)]}
    for i, prob in enumerate(probs):
        chave = str(classes[i]).zfill(2)
        mapa_probs[chave] = prob
        
    return mapa_probs

def gerar_estrategia_matrix_50(historico):
    if not historico: return [], 0, {}
    mapa_ia = treinar_probabilidade_global(historico)
    if not mapa_ia: return [], 0, {}
    
    unis_proibidas, block_gemeas, block_linha = analisar_filtros_avancados(historico)
    
    palpite_matrix = []
    
    for g in range(1, 26):
        dezenas_candidatas = GRUPO_TO_DEZENAS[g]
        ranking_grupo = []
        for d in dezenas_candidatas:
            score = mapa_ia.get(d, 0.01)
            score_ajustado = score
            if int(d[-1]) in unis_proibidas: score_ajustado -= 0.5
            if block_gemeas and d in GEMEAS: score_ajustado -= 0.8
            if block_linha and d.startswith(block_linha): score_ajustado -= 0.6
            ranking_grupo.append((d, score_ajustado, score))
        
        ranking_grupo.sort(key=lambda x: x[1], reverse=True)
        top_2 = [x[0] for x in ranking_grupo[:2]]
        palpite_matrix.extend(top_2)
        
    prob_total = sum([mapa_ia.get(d, 0.01) for d in palpite_matrix])
    conf_media = prob_total * 100 
    
    if conf_media < 1.0: conf_media = 50.0
    if conf_media > 99.9: conf_media = 99.9
    
    info_filtros = { "uni": unis_proibidas, "gemeas": block_gemeas, "linha": block_linha }
    return sorted(palpite_matrix), conf_media, info_filtros

def treinar_oraculo_unidades(historico):
    if not HAS_AI or len(historico) < 30: return [], 0
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    try:
        unis_alvo = [int(j['dezenas'][0][-1]) for j in historico if 'data_dt' in df.columns]
    except: return [], 0
    df = df.iloc[:len(unis_alvo)]
    df['target'] = unis_alvo
    df['target_futuro'] = df['target'].shift(-1)
    df_treino = df.dropna().tail(150)
    if len(df_treino) < 20: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro']
    modelo = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking = []
    for i, prob in enumerate(probs):
        ranking.append((int(classes[i]), prob))
    ranking.sort(key=lambda x: x[1], reverse=True)
    return ranking, (ranking[0][1] * 100)

# =============================================================================
# --- 4. BACKTESTS COM LÓGICA RIGOROSA ---
# =============================================================================

def calcular_metricas_matrix_detalhado(historico):
    if len(historico) < 20: return {}, {}
    total = len(historico)
    inicio = max(20, total - 50)
    
    historico_wins = []
    
    for i in range(inicio, total):
        target = historico[i]['dezenas'][0]
        hist_p = historico[:i]
        palpite, _, _ = gerar_estrategia_matrix_50(hist_p)
        win = target in palpite
        historico_wins.append(win)
        
    seq_atual_loss = 0; seq_atual_win = 0
    if historico_wins:
        if historico_wins[-1]:
            for w in reversed(historico_wins):
                if w: seq_atual_win += 1
                else: break
        else:
            for w in reversed(historico_wins):
                if not w: seq_atual_loss += 1
                else: break
                
    max_w, count_w, ciclo_w = analisar_sequencias_profundas([x for x in historico_wins])
    max_l, count_l, ciclo_l = analisar_sequencias_profundas([not x for x in historico_wins])
    
    stats_loss = { "atual": seq_atual_loss, "max": max_l, "freq": count_l, "ciclo": ciclo_l }
    stats_win = { "atual": seq_atual_win, "max": max_w, "freq": count_w, "ciclo": ciclo_w }
    
    return stats_loss, stats_win

def calcular_metricas_unidades_detalhado(historico):
    if len(historico) < 30: return {}, {}
    total = len(historico)
    inicio = max(30, total - 50)
    max_loss = 0; max_win = 0; current_loss_streak = 0; current_win_streak = 0
    
    # Simulação cronológica exata para detectar o estado (5 ou 7 números)
    historico_wins = []
    
    # Precisa de uma variável de estado que persista através do loop
    streak_no_momento = 0 
    
    for i in range(inicio, total):
        target = int(historico[i]['dezenas'][0][-1])
        hist_parcial = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_parcial)
        
        # Decide o palpite com base no STREAK ANTERIOR
        if streak_no_momento >= 2:
            palpite = [u for u, p in rank[:7]] # Defesa
        else:
            palpite = [u for u, p in rank[:5]] # Ataque
            
        # Verifica se ganhou
        if target in palpite:
            current_loss_streak = 0
            current_win_streak += 1
            historico_wins.append(True)
            streak_no_momento = 0 # Reset streak
        else:
            current_win_streak = 0
            current_loss_streak += 1
            historico_wins.append(False)
            streak_no_momento += 1 # Aumenta streak para o próximo
            
        if current_loss_streak > max_loss: max_loss = current_loss_streak
        if current_win_streak > max_win: max_win = current_win_streak
            
    # Deep Stats
    max_w, count_w, ciclo_w = analisar_sequencias_profundas([x for x in historico_wins])
    max_l, count_l, ciclo_l = analisar_sequencias_profundas([not x for x in historico_wins])
    
    # O "atual" é o último estado do loop
    stats_loss = { "atual": current_loss_streak, "max": max_l, "freq": count_l, "ciclo": ciclo_l }
    stats_win = { "atual": current_win_streak, "max": max_w, "freq": count_w, "ciclo": ciclo_w }
    
    return stats_loss, stats_win

def executar_backtest_recente_uni_preciso(historico):
    """
    Recalcula os últimos 5 jogos garantindo que o Status (5 ou 7)
    corresponda exatamente ao que aconteceu na simulação dinâmica.
    """
    total = len(historico)
    # Analisa um bloco maior para garantir que o 'streak' inicial esteja correto
    start = max(30, total - 60) 
    streak_no_momento = 0
    
    resultados_reais = []
    
    for i in range(start, total):
        target = int(historico[i]['dezenas'][0][-1])
        hist_parcial = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_parcial)
        
        # Lógica rigorosa de Ataque/Defesa
        is_defense = False
        if streak_no_momento >= 2:
            palpite = [u for u, p in rank[:7]]
            is_defense = True
        else:
            palpite = [u for u, p in rank[:5]]
            
        win = target in palpite
        
        # Guarda apenas os últimos 5 para exibição
        if i >= total - 5:
            modo_str = "🛡️(7)" if is_defense else "⚔️(5)"
            resultados_reais.append({
                "val": f"Final {target}",
                "win": win,
                "modo": modo_str
            })
            
        # Atualiza streak para o próximo passo
        if win: streak_no_momento = 0
        else: streak_no_momento += 1
        
    return reversed(resultados_reais) # Inverte para mostrar o mais recente primeiro

def executar_backtest_recente_matrix(historico):
    results = []
    for i in range(1, 6):
        idx = -i
        target = historico[idx]['dezenas'][0]
        palp, _, _ = gerar_estrategia_matrix_50(historico[:idx])
        win = target in palp
        results.append({"val": target, "win": win})
    return results

def rastreador_padroes(historico, tipo="DEZENA"):
    if len(historico) < 10: return []
    encontrados = []
    if tipo == "DEZENA":
        ultimo_real = historico[-1]['dezenas'][0]
        label = ultimo_real
        for i in range(len(historico)-2, -1, -1):
            if historico[i]['dezenas'][0] == ultimo_real:
                encontrados.append({ "Data": historico[i+1]['data'], "Veio": historico[i+1]['dezenas'][0] })
                if len(encontrados) >= 5: break
    else:
        ultimo_real = historico[-1]['dezenas'][0][-1]
        label = f"Final {ultimo_real}"
        for i in range(len(historico)-2, -1, -1):
            if historico[i]['dezenas'][0][-1] == ultimo_real:
                encontrados.append({ "Data": historico[i+1]['data'], "Veio": f"Final {historico[i+1]['dezenas'][0][-1]}" })
                if len(encontrados) >= 5: break
    return label, encontrados

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================

st.sidebar.header("🔧 Extração de Dados")
modo_extracao = st.sidebar.radio("Modo:", ["Unitária", "Turbo (Massa)"])

if modo_extracao == "Unitária":
    d_data = st.sidebar.date_input("Data:", date.today())
    d_hora = st.sidebar.selectbox("Horário:", CONFIG_TRADICIONAL['horarios'])
    
    if st.sidebar.button("🚀 Baixar Resultado"):
        ws = conectar_planilha()
        if ws:
            with st.spinner("Buscando..."):
                chaves = obter_chaves_existentes(ws)
                key = f"{d_data.strftime('%Y-%m-%d')}|{d_hora}"
                if key in chaves:
                    st.sidebar.warning("Resultado já existe!")
                else:
                    dez, msg = raspar_site(d_data, d_hora)
                    if dez:
                        ws.append_row([d_data.strftime('%Y-%m-%d'), d_hora] + dez)
                        st.sidebar.success(f"Salvo: {dez[0]}")
                        time.sleep(1); st.rerun()
                    else: st.sidebar.error(f"Erro: {msg}")
        else: st.sidebar.error("Erro Conexão")

else:
    d_ini = st.sidebar.date_input("Início:", date.today())
    d_fim = st.sidebar.date_input("Fim:", date.today())
    if st.sidebar.button("🚀 INICIAR TURBO"):
        ws = conectar_planilha()
        if ws:
            bar = st.sidebar.progress(0)
            chaves = obter_chaves_existentes(ws)
            delta = d_fim - d_ini
            dias = [d_ini + timedelta(days=i) for i in range(delta.days + 1)]
            total = len(dias) * len(CONFIG_TRADICIONAL['horarios'])
            count = 0; success = 0
            for dia in dias:
                for hora in CONFIG_TRADICIONAL['horarios']:
                    count += 1
                    bar.progress(count / total)
                    if dia > date.today(): continue
                    if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue
                    key = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                    if key in chaves: continue
                    dez, msg = raspar_site(dia, hora)
                    if dez:
                        ws.append_row([dia.strftime('%Y-%m-%d'), hora] + dez)
                        chaves.append(key)
                        success += 1
                    time.sleep(0.5)
            st.sidebar.success(f"Finalizado! {success} novos.")
            time.sleep(2); st.rerun()

st.sidebar.markdown("---")
st.sidebar.link_button("🛡️ Ir para PENTÁGONO", "https://seu-app-pentagono.streamlit.app")

st.title("🎯 CENTURION (Tradicional Exclusive)")

historico = carregar_historico()

if len(historico) > 0:
    ult = historico[-1]
    st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['hora']} | **Resultado:** {ult['dezenas'][0]}")
    
    aba_dez, aba_uni = st.tabs(["🎲 Matrix 50 (2/Grupo)", "🎯 IA Unidades (Dinâmico)"])
    
    with aba_dez:
        st.subheader("Análise: Matrix 50 (Cobertura Total 2x25)")
        
        lista_matrix, conf_total, info_filtros = gerar_estrategia_matrix_50(historico)
        stats_loss, stats_win = calcular_metricas_matrix_detalhado(historico)
        
        if HAS_AI:
            st.info(f"🛡️ Força da Cobertura (Probabilidade Acumulada): {conf_total:.1f}%")
            
            filtros_ativos = []
            if info_filtros['uni']: filtros_ativos.append(f"Unidades Proibidas: {info_filtros['uni']}")
            if info_filtros['gemeas']: filtros_ativos.append("Anti-Trinca Gêmea")
            if info_filtros['linha']: filtros_ativos.append(f"Anti-Fadiga Linha ({info_filtros['linha']}X)")
            
            if filtros_ativos:
                st.warning(f"🚫 **Filtros Ativos:** {', '.join(filtros_ativos)}")
            else:
                st.success("✅ Nenhum filtro de bloqueio acionado. IA Pura.")
        
        if stats_loss['atual'] >= stats_loss['max'] and stats_loss['max'] > 0:
            st.error(f"🚨 ALERTA: {stats_loss['atual']} Derrotas (Igualou Recorde!)")
        
        with st.container(border=True):
            st.markdown("### 50 Dezenas Selecionadas (Matrix Filter)")
            st.code(", ".join(lista_matrix), language="text")
            
        c1, c2 = st.columns(2)
        c1.metric("Derrotas", f"{stats_loss['atual']}", 
                  f"Recorde: {stats_loss['max']} (Freq: {stats_loss['freq']}x | Ciclo: {stats_loss['ciclo']})", 
                  delta_color="inverse")
        c2.metric("Vitórias", f"{stats_win['atual']}", 
                  f"Recorde: {stats_win['max']} (Freq: {stats_win['freq']}x | Ciclo: {stats_win['ciclo']})")
        
        st.markdown("**Histórico Recente (Matrix):**")
        bt_dez = executar_backtest_recente_matrix(historico)
        cols_bt = st.columns(5)
        for i, res in enumerate(reversed(bt_dez)):
            with cols_bt[i]:
                if res['win']: st.success(res['val'])
                else: st.error(res['val'])
                
        lbl_d, padroes_d = rastreador_padroes(historico, "DEZENA")
        if padroes_d:
            st.caption(f"Padrões após a dezena **{lbl_d}**:")
            st.table(pd.DataFrame(padroes_d))

    with aba_uni:
        st.subheader("Análise: Unidades Finais (0-9)")
        rank_uni, conf_uni = treinar_oraculo_unidades(historico)
        stats_loss_u, stats_win_u = calcular_metricas_unidades_detalhado(historico)
        
        top_base = [str(u) for u, p in rank_uni[:5]]
        
        if stats_loss_u['atual'] >= 2:
            modo = "DEFESA"
            extras = [str(u) for u, p in rank_uni[5:7]]
            lista_final_uni = top_base + extras
            msg_status = f"🛡️ MODO CORREÇÃO ATIVO! (Sequência: {stats_loss_u['atual']} Losses)"
            cor_alerta = "error"
        else:
            modo = "ATAQUE"
            lista_final_uni = top_base
            msg_status = "⚔️ MODO ATAQUE (Top 5)"
            cor_alerta = "info"
            
        if HAS_AI:
            with st.container(border=True):
                st.markdown(f"### 🧠 Confiança IA: {conf_uni:.1f}%")
                if modo == "DEFESA":
                    st.error(msg_status)
                    st.markdown("**Estratégia:** Expandimos para **Top 7**.")
                else:
                    st.success(msg_status)
                    st.markdown("**Estratégia:** Mantemos **Top 5**.")
            
        with st.container(border=True):
            st.markdown(f"### Finais Sugeridos: {', '.join(lista_final_uni)}")
            
        c3, c4 = st.columns(2)
        c3.metric("Derrotas (Dinâmicas)", f"{stats_loss_u['atual']}", 
                  f"Recorde: {stats_loss_u['max']} (Freq: {stats_loss_u['freq']}x | Ciclo: {stats_loss_u['ciclo']})",
                  delta_color="inverse")
        c4.metric("Vitórias", f"{stats_win_u['atual']}", 
                  f"Recorde: {stats_win_u['max']} (Freq: {stats_win_u['freq']}x | Ciclo: {stats_win_u['ciclo']})")
        
        st.markdown("**Histórico Recente (Verificação Rigorosa):**")
        # Usa a nova função corrigida
        bt_uni = executar_backtest_recente_uni_preciso(historico)
        cols_bt_u = st.columns(5)
        for i, res in enumerate(bt_uni):
            with cols_bt_u[i]:
                st.caption(f"{res['modo']}")
                if res['win']: st.success(res['val'])
                else: st.error(res['val'])

        lbl_u, padroes_u = rastreador_padroes(historico, "UNIDADE")
        if padroes_u:
            st.caption(f"Padrões após o **{lbl_u}**:")
            st.table(pd.DataFrame(padroes_u))

else:
    st.warning("⚠️ Base de dados vazia. Utilize o menu lateral para importar resultados.")
