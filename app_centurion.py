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
st.set_page_config(page_title="CENTURION TRADICIONAL - V26.0 Matrix", page_icon="🎯", layout="wide")

CONFIG_TRADICIONAL = {
    "display": "TRADICIONAL (1º Prêmio)", 
    "aba": "BASE_TRADICIONAL_DEZ", 
    "slug": "loteria-tradicional", 
    "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] 
}

# MAPEAMENTO DE GRUPOS (Para a estratégia Matrix)
GRUPO_TO_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4
    inicio = fim - 3
    dezenas_do_grupo = []
    for n in range(inicio, fim + 1):
        d_str = "00" if n == 100 else f"{n:02}"
        dezenas_do_grupo.append(d_str)
    GRUPO_TO_DEZENAS[g] = dezenas_do_grupo

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
                    d1 = str(row[2]).strip().zfill(2) if len(row) > 2 else "00"
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
# --- 3. CÉREBRO: IA MATRIX (NOVA LÓGICA) ---
# =============================================================================

def get_unidades_improvaveis(historico):
    """
    Detecta a 'Trinca Proibida' sugerida pelo usuário.
    Ex: Se veio final 6, depois final 7 -> O final 8 é improvável (sequência crescente).
    Ex: Se veio final 8, depois final 7 -> O final 6 é improvável (sequência decrescente).
    """
    if len(historico) < 2: return []
    
    try:
        # Pega as duas últimas dezenas REAIS
        u_atual = int(historico[-1]['dezenas'][0][-1]) # Penúltimo (referência atual)
        u_anterior = int(historico[-2]['dezenas'][0][-1]) # Antepenúltimo
        
        proibidas = []
        
        # Sequência Crescente (ex: 6 -> 7 -> [8 proibido])
        if u_atual == (u_anterior + 1) or (u_anterior == 9 and u_atual == 0):
            prox = (u_atual + 1) % 10
            proibidas.append(prox)
            
        # Sequência Decrescente (ex: 8 -> 7 -> [6 proibido])
        if u_atual == (u_anterior - 1) or (u_anterior == 0 and u_atual == 9):
            prox = (u_atual - 1)
            if prox < 0: prox = 9
            proibidas.append(prox)
            
        return list(set(proibidas))
    except:
        return []

def treinar_probabilidade_global(historico):
    """Retorna um dicionário {dezena: probabilidade} para TODAS as 100 dezenas."""
    if not HAS_AI or len(historico) < 30: 
        # Fallback sem IA: Retorna probabilidade igual para todas ou baseada em frequência
        return {f"{i:02}": 0.5 for i in range(100)} # Simplificado

    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    
    try:
        dezenas_alvo = [j['dezenas'][0] for j in historico if 'data_dt' in df.columns]
    except: return {}
    
    df = df.iloc[:len(dezenas_alvo)]
    df['target'] = dezenas_alvo
    df['target_futuro'] = df['target'].shift(-1)
    
    df_treino = df.dropna().tail(150)
    
    if len(df_treino) < 20: return {}
    
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro']
    
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    
    # Probabilidades para todas as classes conhecidas
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    mapa_probs = {c: 0.0 for c in [f"{i:02}" for i in range(100)]}
    for i, prob in enumerate(probs):
        mapa_probs[classes[i]] = prob
        
    return mapa_probs

def gerar_estrategia_matrix_50(historico):
    """
    Gera 50 dezenas cobrindo TODOS os 25 grupos (2 dezenas por grupo).
    Usa IA + Filtro de Unidade Proibida para escolher as 2 melhores.
    """
    if not historico: return [], 0
    
    # 1. Pega probabilidades da IA para tudo
    mapa_ia = treinar_probabilidade_global(historico)
    if not mapa_ia: return [], 0
    
    # 2. Detecta unidades "proibidas" pela lógica de sequência
    unidades_ruins = get_unidades_improvaveis(historico)
    
    palpite_matrix = []
    
    # 3. Itera sobre cada grupo (1 a 25)
    for g in range(1, 26):
        dezenas_candidatas = GRUPO_TO_DEZENAS[g] # As 4 dezenas do grupo
        
        # Rankeia as 4 dezenas do grupo
        ranking_grupo = []
        for d in dezenas_candidatas:
            score = mapa_ia.get(d, 0.0)
            
            # APLICA O FILTRO DO USUÁRIO
            uni_d = int(d[-1])
            if uni_d in unidades_ruins:
                score -= 0.5 # Penalidade pesada para evitar essa dezena
            
            ranking_grupo.append((d, score))
        
        # Pega as 2 melhores deste grupo
        ranking_grupo.sort(key=lambda x: x[1], reverse=True)
        top_2 = [x[0] for x in ranking_grupo[:2]]
        palpite_matrix.extend(top_2)
        
    # Confiança média das escolhidas
    conf_media = sum([mapa_ia.get(d, 0) for d in palpite_matrix]) / len(palpite_matrix) * 100 if palpite_matrix else 0
    
    return sorted(palpite_matrix), conf_media

# --- IA UNIDADES (Mantida a lógica V25.2 para esta aba) ---
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
# --- 4. BACKTESTS (ADAPTADO PARA MATRIX 50) ---
# =============================================================================

def calcular_metricas_matrix(historico):
    """Backtest da estratégia Matrix (2 dezenas por grupo)."""
    if len(historico) < 20: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(20, total - 50)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    
    for i in range(inicio, total):
        target = historico[i]['dezenas'][0]
        hist_p = historico[:i]
        
        # Gera a lista de 50 dezenas usando a lógica Matrix
        palpite, _ = gerar_estrategia_matrix_50(hist_p)
        
        win = target in palpite
        if win:
            seq_loss = 0; seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0; seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    # Atual (Próximo jogo não sorteado ou último sorteado se for apenas checagem)
    # Como não temos o futuro, vamos ver o estado atual baseado no ultimo jogo conhecido
    # Se o ultimo jogo (idx=-1) foi win, estamos em win streak.
    
    # Recalcula apenas os streaks atuais
    idx = -1; atual_loss = 0; atual_win = 0
    target = historico[idx]['dezenas'][0]
    palpite, _ = gerar_estrategia_matrix_50(historico[:idx])
    
    if target in palpite:
        atual_win = 1
        for k in range(2, 10):
            t = historico[-k]['dezenas'][0]
            p, _ = gerar_estrategia_matrix_50(historico[:-k])
            if t in p: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 10):
            t = historico[-k]['dezenas'][0]
            p, _ = gerar_estrategia_matrix_50(historico[:-k])
            if t not in p: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

def calcular_metricas_unidades_dinamicas_reais(historico):
    if len(historico) < 30: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(30, total - 50)
    max_loss = 0; max_win = 0; current_loss_streak = 0; current_win_streak = 0
    
    for i in range(inicio, total):
        target = int(historico[i]['dezenas'][0][-1])
        hist_parcial = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_parcial)
        
        if current_loss_streak >= 2: palpite = [u for u, p in rank[:7]]
        else: palpite = [u for u, p in rank[:5]]
            
        if target in palpite:
            current_loss_streak = 0; current_win_streak += 1
            if current_win_streak > max_win: max_win = current_win_streak
        else:
            current_win_streak = 0; current_loss_streak += 1
            if current_loss_streak > max_loss: max_loss = current_loss_streak
            
    return current_loss_streak, max_loss, current_win_streak, max_win

def executar_backtest_recente_matrix(historico):
    results = []
    for i in range(1, 6):
        idx = -i
        target = historico[idx]['dezenas'][0]
        palp, _ = gerar_estrategia_matrix_50(historico[:idx])
        win = target in palp
        results.append({"val": target, "win": win})
    return results

def executar_backtest_recente_uni(historico):
    results = []
    for i in range(1, 6):
        idx = -i
        target = int(historico[idx]['dezenas'][0][-1])
        rank, _ = treinar_oraculo_unidades(historico[:idx])
        top7 = [u for u, p in rank[:7]]
        win = target in top7
        results.append({"val": f"Final {target}", "win": win})
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

# --- SIDEBAR ---
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
                    st.sidebar.warning("Resultado já existe na planilha!")
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

# --- MAIN PAGE ---
st.title("🎯 CENTURION (Tradicional Exclusive)")

historico = carregar_historico()

if len(historico) > 0:
    ult = historico[-1]
    st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['hora']} | **Resultado:** {ult['dezenas'][0]}")
    
    aba_dez, aba_uni = st.tabs(["🎲 Matrix 50 (2/Grupo)", "🎯 IA Unidades (Dinâmico)"])
    
    # --- ABA MATRIX 50 (NOVA ESTRATÉGIA) ---
    with aba_dez:
        st.subheader("Análise: Matrix 50 (Cobertura Total 2x25)")
        
        # Gera lista com a nova lógica
        lista_matrix, conf_dez = gerar_estrategia_matrix_50(historico)
        loss_d, max_loss_d, win_d, max_win_d = calcular_metricas_matrix(historico)
        
        # Verifica se há unidade proibida ativa
        unidades_proibidas = get_unidades_improvaveis(historico)
        
        if HAS_AI:
            st.info(f"🧠 Confiança Média IA: {conf_dez:.1f}%")
            if unidades_proibidas:
                st.warning(f"🚫 **Filtro de Sequência Ativo:** Dezenas com final **{unidades_proibidas}** foram penalizadas (Padrão 3-step).")
            else:
                st.success("✅ Nenhuma sequência de bloqueio detectada. IA pura.")
        
        if loss_d >= max_loss_d and max_loss_d > 0:
            st.error(f"🚨 ALERTA: {loss_d} Derrotas (Recorde!)")
        
        with st.container(border=True):
            st.markdown("### 50 Dezenas Selecionadas (2 Melhores de cada Grupo)")
            st.code(", ".join(lista_matrix), language="text")
            
        c1, c2 = st.columns(2)
        c1.metric("Derrotas", f"{loss_d}", f"Max: {max_loss_d}", delta_color="inverse")
        c2.metric("Vitórias", f"{win_d}", f"Max: {max_win_d}")
        
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

    # --- ABA UNIDADES (Dinâmica) ---
    with aba_uni:
        st.subheader("Análise: Unidades Finais (0-9)")
        rank_uni, conf_uni = treinar_oraculo_unidades(historico)
        u_loss_real, u_max_loss_real, u_win_real, u_max_win_real = calcular_metricas_unidades_dinamicas_reais(historico)
        
        top_base = [str(u) for u, p in rank_uni[:5]]
        
        if u_loss_real >= 2:
            modo = "DEFESA"
            extras = [str(u) for u, p in rank_uni[5:7]]
            lista_final_uni = top_base + extras
            msg_status = f"🛡️ MODO CORREÇÃO ATIVO! (Sequência: {u_loss_real} Losses)"
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
        c3.metric("Derrotas (Dinâmicas)", f"{u_loss_real}", f"Max: {u_max_loss_real}", delta_color="inverse")
        c4.metric("Vitórias", f"{u_win_real}", f"Max: {u_max_win_real}")
        
        st.markdown("**Histórico Recente:**")
        bt_uni = executar_backtest_recente_uni(historico)
        cols_bt_u = st.columns(5)
        for i, res in enumerate(reversed(bt_uni)):
            with cols_bt_u[i]:
                if res['win']: st.success(res['val'])
                else: st.error(res['val'])

        lbl_u, padroes_u = rastreador_padroes(historico, "UNIDADE")
        if padroes_u:
            st.caption(f"Padrões após o **{lbl_u}**:")
            st.table(pd.DataFrame(padroes_u))

else:
    st.warning("⚠️ Base de dados vazia. Utilize o menu lateral para importar resultados.")
