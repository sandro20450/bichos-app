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
st.set_page_config(page_title="CENTURION TRADICIONAL - V24.0", page_icon="🎯", layout="wide")

# Configuração Única: TRADICIONAL
CONFIG_TRADICIONAL = {
    "display": "TRADICIONAL (1º Prêmio)", 
    "aba": "BASE_TRADICIONAL_DEZ", 
    "slug": "loteria-tradicional", 
    "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] 
}

# Estilo Visual Nativo (Dark & Clean)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #00ff00 !important; }
    .css-1aumxhk { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (LIVE - SEM CACHE) ---
# =============================================================================

def conectar_planilha():
    """Conecta ao Google Sheets (Conexão Direta/Live)."""
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
    """Baixa o histórico da Tradicional em tempo real."""
    ws = conectar_planilha()
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados = []
            for row in raw[1:]:
                if len(row) >= 3:
                    # Tradicional foca no 1º prêmio (index 2 na planilha, pois 0=data, 1=hora)
                    # Mas a estrutura salva geralmente é [data, hora, p1, p2, p3, p4, p5]
                    # Vamos pegar apenas a primeira dezena
                    d1 = str(row[2]).strip().zfill(2) if len(row) > 2 else "00"
                    
                    # Cria estrutura compatível com as funções de IA (lista de dezenas)
                    # Preenche o resto com 00 para não quebrar lógica antiga
                    dezenas = [d1, "00", "00", "00", "00"]
                    
                    dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
            return dados
        except: return [] 
    return []

def obter_chaves_existentes(ws):
    """Lê chaves (Data|Hora) para evitar duplicidade."""
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
        
        # Variações de horário
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
                            premio_txt = cols[0].get_text().strip() # Ex: "1º Prêmio"
                            numero_txt = cols[1].get_text().strip() # Ex: "1234"
                            
                            # Filtra apenas o 1º Prêmio
                            nums_premio = re.findall(r'\d+', premio_txt)
                            if nums_premio and int(nums_premio[0]) == 1:
                                if numero_txt.isdigit() and len(numero_txt) >= 2:
                                    dezena = numero_txt[-2:] # Pega a dezena (últimos 2)
                                    # Retorna formato lista com padding para compatibilidade
                                    return [dezena, "00", "00", "00", "00"], "Sucesso"
        
        return None, f"Horário {horario_alvo} não encontrado."
    except Exception as e: return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA PURE (DEZENAS & UNIDADES) ---
# =============================================================================

def treinar_oraculo_dezenas(historico):
    """IA focada em Dezenas (00-99)."""
    if not HAS_AI or len(historico) < 30: return [], 0
    
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    
    # Alvo: Dezena do 1º Prêmio (indice 0)
    try:
        dezenas_alvo = [j['dezenas'][0] for j in historico if 'data_dt' in df.columns]
    except: return [], 0
    
    df = df.iloc[:len(dezenas_alvo)]
    df['target'] = dezenas_alvo
    df['target_futuro'] = df['target'].shift(-1)
    
    df_treino = df.dropna().tail(150) # Treino rápido e recente
    if len(df_treino) < 20: return [], 0
    
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro']
    
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    # Previsão
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    ranking = []
    for i, prob in enumerate(probs):
        ranking.append((classes[i], prob))
    ranking.sort(key=lambda x: x[1], reverse=True)
    
    return ranking, (ranking[0][1] * 100)

def treinar_oraculo_unidades(historico):
    """IA focada em Unidades (0-9)."""
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
    
    modelo = RandomForestClassifier(n_estimators=60, random_state=42, n_jobs=-1)
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

def identificar_saturadas(historico):
    """Retorna dezenas que saíram >= 4 vezes nos últimos 40 jogos."""
    if len(historico) < 40: return []
    recorte = historico[-40:]
    dezenas = [j['dezenas'][0] for j in recorte]
    contagem = Counter(dezenas)
    return [d for d, qtd in contagem.items() if qtd >= 4]

def gerar_estrategia_dezenas(historico):
    """Gera as 46 dezenas (AI Pure + Filtro Saturação)."""
    if not historico: return [], [], 0
    ranking, conf = treinar_oraculo_dezenas(historico)
    if not ranking: return [], [], 0
    
    saturadas = identificar_saturadas(historico)
    final = []; cortadas = []
    
    for dezena, prob in ranking:
        if len(final) >= 46: break
        if dezena in saturadas:
            cortadas.append(dezena)
            continue
        final.append(dezena)
        
    # Completa se faltar
    if len(final) < 46:
        for dezena, prob in ranking:
            if len(final) >= 46: break
            if dezena not in final: final.append(dezena)
            
    return sorted(final), cortadas, conf

# --- BACKTESTS OTIMIZADOS ---
def calcular_metricas_dezenas(historico):
    if len(historico) < 20: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(20, total - 50)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    
    for i in range(inicio, total):
        target = historico[i]['dezenas'][0]
        # Simulação rápida (treino parcial)
        hist_p = historico[:i]
        palpite, _, _ = gerar_estrategia_dezenas(hist_p)
        win = target in palpite
        if win:
            seq_loss = 0; seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0; seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    # Atual
    idx = -1; atual_loss = 0; atual_win = 0
    target = historico[idx]['dezenas'][0]
    palpite, _, _ = gerar_estrategia_dezenas(historico[:idx])
    
    if target in palpite:
        atual_win = 1
        # Check backward
        for k in range(2, 10):
            t = historico[-k]['dezenas'][0]
            p, _, _ = gerar_estrategia_dezenas(historico[:-k])
            if t in p: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 10):
            t = historico[-k]['dezenas'][0]
            p, _, _ = gerar_estrategia_dezenas(historico[:-k])
            if t not in p: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

def calcular_metricas_unidades(historico):
    if len(historico) < 20: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(20, total - 50)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    
    for i in range(inicio, total):
        target = int(historico[i]['dezenas'][0][-1])
        hist_p = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_p)
        top5 = [u for u, p in rank[:5]]
        
        if target in top5:
            seq_loss = 0; seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0; seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    # Atual
    idx = -1; atual_loss = 0; atual_win = 0
    target = int(historico[idx]['dezenas'][0][-1])
    rank, _ = treinar_oraculo_unidades(historico[:idx])
    top5 = [u for u, p in rank[:5]]
    
    if target in top5:
        atual_win = 1
        for k in range(2, 10):
            t = int(historico[-k]['dezenas'][0][-1])
            r, _ = treinar_oraculo_unidades(historico[:-k])
            t5 = [u for u, p in r[:5]]
            if t in t5: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 10):
            t = int(historico[-k]['dezenas'][0][-1])
            r, _ = treinar_oraculo_unidades(historico[:-k])
            t5 = [u for u, p in r[:5]]
            if t not in t5: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

def executar_backtest_recente(historico, tipo="DEZENA"):
    results = []
    for i in range(1, 6): # Últimos 5 jogos
        idx = -i
        if tipo == "DEZENA":
            target = historico[idx]['dezenas'][0]
            palp, _, _ = gerar_estrategia_dezenas(historico[:idx])
            win = target in palp
            results.append({"val": target, "win": win})
        else:
            target = int(historico[idx]['dezenas'][0][-1])
            rank, _ = treinar_oraculo_unidades(historico[:idx])
            top5 = [u for u, p in rank[:5]]
            win = target in top5
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
                encontrados.append({
                    "Data": historico[i+1]['data'],
                    "Veio": historico[i+1]['dezenas'][0]
                })
                if len(encontrados) >= 5: break
    else:
        ultimo_real = historico[-1]['dezenas'][0][-1]
        label = f"Final {ultimo_real}"
        for i in range(len(historico)-2, -1, -1):
            if historico[i]['dezenas'][0][-1] == ultimo_real:
                encontrados.append({
                    "Data": historico[i+1]['data'],
                    "Veio": f"Final {historico[i+1]['dezenas'][0][-1]}"
                })
                if len(encontrados) >= 5: break
                
    return label, encontrados

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================

# --- SIDEBAR (EXTRAÇÃO) ---
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
                    else:
                        st.sidebar.error(f"Erro: {msg}")
        else:
            st.sidebar.error("Erro Conexão")

else: # Turbo
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
                        chaves.append(key) # Atualiza lista local
                        success += 1
                    time.sleep(0.5)
            
            st.sidebar.success(f"Finalizado! {success} novos.")
            time.sleep(2); st.rerun()

st.sidebar.markdown("---")
st.sidebar.link_button("🛡️ Ir para PENTÁGONO", "https://seu-app-pentagono.streamlit.app")

# --- MAIN PAGE (ANÁLISE) ---
st.title("🎯 CENTURION (Tradicional Exclusive)")

historico = carregar_historico()

if len(historico) > 0:
    ult = historico[-1]
    st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['hora']} | **Resultado:** {ult['dezenas'][0]}")
    
    # ---------------------------------------------------------
    # COLUNA 1: IA DEZENAS (LEGIÃO 46)
    # ---------------------------------------------------------
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🎲 IA Dezenas (Legião 46)")
        
        lista_46, cortadas, conf_dez = gerar_estrategia_dezenas(historico)
        loss_d, max_loss_d, win_d, max_win_d = calcular_metricas_dezenas(historico)
        
        if HAS_AI:
            st.info(f"🧠 Confiança do Modelo: {conf_dez:.1f}%")
        
        if loss_d >= max_loss_d and max_loss_d > 0:
            st.error(f"🚨 ALERTA: {loss_d} Derrotas (Recorde!)")
        
        with st.container(border=True):
            if cortadas: st.warning(f"🚫 {len(cortadas)} Saturadas Cortadas")
            st.code(", ".join(lista_46), language="text")
            
        m1, m2 = st.columns(2)
        m1.metric("Derrotas", f"{loss_d}", f"Max: {max_loss_d}", delta_color="inverse")
        m2.metric("Vitórias", f"{win_d}", f"Max: {max_win_d}")
        
        st.markdown("**Histórico Recente:**")
        bt_dez = executar_backtest_recente(historico, "DEZENA")
        cols_bt = st.columns(5)
        for i, res in enumerate(reversed(bt_dez)):
            with cols_bt[i]:
                if res['win']: st.success(res['val'])
                else: st.error(res['val'])
                
        lbl_d, padroes_d = rastreador_padroes(historico, "DEZENA")
        if padroes_d:
            st.caption(f"Padrões após a dezena **{lbl_d}**:")
            st.table(pd.DataFrame(padroes_d))

    # ---------------------------------------------------------
    # COLUNA 2: IA UNIDADES (TOP 5)
    # ---------------------------------------------------------
    with c2:
        st.subheader("🎯 IA Unidades (Top 5)")
        
        rank_uni, conf_uni = treinar_oraculo_unidades(historico)
        top5_uni = [str(u) for u, p in rank_uni[:5]]
        loss_u, max_loss_u, win_u, max_win_u = calcular_metricas_unidades(historico)
        
        if HAS_AI:
            st.info(f"🧠 Confiança do Modelo: {conf_uni:.1f}%")
            
        if loss_u >= max_loss_u and max_loss_u > 0:
            st.error(f"🚨 ALERTA: {loss_u} Derrotas (Recorde!)")
            
        with st.container(border=True):
            st.markdown(f"### Finais: {', '.join(top5_uni)}")
            
        m3, m4 = st.columns(2)
        m3.metric("Derrotas", f"{loss_u}", f"Max: {max_loss_u}", delta_color="inverse")
        m4.metric("Vitórias", f"{win_u}", f"Max: {max_win_u}")
        
        st.markdown("**Histórico Recente:**")
        bt_uni = executar_backtest_recente(historico, "UNIDADE")
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
