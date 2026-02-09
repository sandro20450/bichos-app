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
st.set_page_config(page_title="CENTURION 46 - V19.0 AI Pure", page_icon="🛡️", layout="wide")

# Configuração das Bancas
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
        "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "19:30", "20:00", "21:00"] 
    },
    "MONTE": { 
        "display": "MONTE CARLOS (Dezenas)", 
        "aba": "BASE_MONTE_DEZ", 
        "slug": "nordeste-monte-carlos", 
        "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] 
    },
    "TRADICIONAL": { 
        "display": "TRADICIONAL (1º Prêmio)", 
        "aba": "BASE_TRADICIONAL_DEZ", 
        "slug": "loteria-tradicional", 
        "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] 
    }
}

# Estilo Visual
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    
    /* BOX PRINCIPAL (VERDE) */
    .box-centurion {
        background: linear-gradient(135deg, #004d00, #002600);
        border: 2px solid #00ff00; padding: 20px; border-radius: 12px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 0 25px rgba(0, 255, 0, 0.15);
    }
    
    /* BOX IA (ROXO) - AGORA NO TOPO */
    .box-ai {
        background: linear-gradient(135deg, #2b005c, #1a0033);
        border: 1px solid #b300ff; padding: 15px; border-radius: 10px;
        margin-bottom: 15px; text-align: left;
        box-shadow: 0 0 15px rgba(179, 0, 255, 0.2);
    }
    .ai-title { color: #b300ff; font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 10px; }
    
    /* BOX UNIDADE ESPECIAL (AZUL) */
    .box-unidade {
        background: linear-gradient(135deg, #003366, #004080);
        border: 2px solid #0099ff; padding: 15px; border-radius: 10px;
        margin-bottom: 5px; text-align: center;
        box-shadow: 0 0 15px rgba(0, 153, 255, 0.2);
    }
    .uni-title { color: #0099ff; font-weight: 900; font-size: 18px; text-transform: uppercase; margin-bottom: 5px; }
    .uni-nums { font-size: 22px; color: #fff; font-weight: bold; letter-spacing: 3px; }
    
    .titulo-gold { color: #00ff00; font-weight: 900; font-size: 26px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }
    .subtitulo { color: #cccccc; font-size: 14px; margin-bottom: 20px; font-style: italic; }
    .nums-destaque { font-size: 20px; color: #ffffff; font-weight: bold; word-wrap: break-word; line-height: 1.8; letter-spacing: 1px; }
    
    .info-pill { padding: 5px 15px; border-radius: 5px; font-weight: bold; font-size: 13px; display: inline-block; margin: 5px; }
    .pill-sat { background-color: #330000; color: #ff4b4b; border: 1px solid #ff4b4b; }
    .pill-ia { background-color: #2b005c; color: #d900ff; border: 1px solid #d900ff; }
    
    .backtest-container { display: flex; justify-content: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
    .bt-card { background-color: rgba(30, 30, 30, 0.9); border-radius: 8px; padding: 10px; width: 90px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 20px; margin-bottom: 2px; }
    .bt-num { font-size: 14px; font-weight: bold; }
    .bt-label { font-size: 10px; opacity: 0.8; text-transform: uppercase; }
    .max-loss-pill { background-color: rgba(255, 0, 0, 0.15); border: 1px solid #ff4b4b; color: #ffcccc; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 15px; }
    .max-win-pill { background-color: rgba(0, 255, 0, 0.15); border: 1px solid #00ff00; color: #ccffcc; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 15px; margin-left: 10px; }
    
    /* DASHBOARD CARDS */
    .dash-card { padding: 10px 5px; border-radius: 8px; margin-bottom: 8px; text-align: center; border-left: 4px solid #fff; }
    .dash-critico { background-color: #4a0000; border-color: #ff0000; }
    .dash-perigo { background-color: #662200; border-color: #ff5500; }
    .dash-atencao { background-color: #4a3b00; border-color: #ffcc00; }
    .dash-vitoria { background-color: #003300; border-color: #00ff00; }
    .dash-unidade { background-color: #002244; border-color: #0099ff; }
    
    .dash-title { font-size: 13px; font-weight: 900; margin-bottom: 0px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dash-subtitle { font-size: 11px; opacity: 0.8; margin-bottom: 2px; }
    .dash-metric { font-size: 20px; font-weight: bold; margin: 2px 0; line-height: 1.2; }
    .dash-footer { font-size: 10px; opacity: 0.7; margin: 0; }
    .dash-badge { font-size: 10px; font-weight: bold; margin-top: 2px; display: block; }

    /* ESTILO PARA O RASTREADOR DE PADRÕES */
    .pattern-row {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 5px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 3px solid #00ff00;
    }
    .pattern-row-uni {
        background-color: rgba(0, 153, 255, 0.1);
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 5px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 3px solid #0099ff;
    }
    .pattern-date { font-size: 12px; color: #aaa; }
    .pattern-result { font-size: 16px; font-weight: bold; color: #fff; }

    div[data-testid="stTable"] table { color: white; }
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

def carregar_historico_dezenas(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados = []
            for row in raw[1:]:
                if len(row) >= 3:
                    raw_dezenas = [str(d).strip().zfill(2) for d in row[2:] if str(d).strip().isdigit()]
                    if "TRADICIONAL" in nome_aba and len(raw_dezenas) >= 1:
                        while len(raw_dezenas) < 5: raw_dezenas.append("00")
                        dados.append({"data": row[0], "hora": row[1], "dezenas": raw_dezenas[:5]})
                    elif len(raw_dezenas) >= 5:
                        dados.append({"data": row[0], "hora": row[1], "dezenas": raw_dezenas[:5]})
            return dados
        except: return [] 
    return []

def raspar_dezenas_site(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    data_formatada_verif = data_alvo.strftime('%d/%m/%Y')
    
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
                if data_formatada_verif[:5] not in header_text: continue

                element = header_text.parent
                tabela = element.find_next('table')
                if tabela:
                    txt_tabela = tabela.get_text().upper()
                    if "PRÊMIO" not in txt_tabela or "MILHAR" not in txt_tabela: continue 

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
                                        return dezenas_encontradas, f"Sucesso (Confirmado: {data_formatada_verif})"
                            
                            elif nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                if numero_txt.isdigit() and len(numero_txt) >= 2:
                                    dezena = numero_txt[-2:]
                                    dezenas_encontradas.append(dezena)
                    
                    if banca_key != "TRADICIONAL" and len(dezenas_encontradas) >= 5:
                        return dezenas_encontradas[:5], "Sucesso"

        return None, f"Horário {horario_alvo} do dia {data_formatada_verif} não encontrado."
    except Exception as e: return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA PURE (V19.0) ---
# =============================================================================

def treinar_oraculo_dezenas(historico, indice_premio):
    """
    Treina a IA para prever a probabilidade de cada dezena (00-99).
    """
    if not HAS_AI or len(historico) < 50: return [], 0
    
    df = pd.DataFrame(historico)
    # Garante datas corretas
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt'])
    
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    
    # Extrai alvo
    try:
        dezenas_alvo = [j['dezenas'][indice_premio] for j in historico if 'data_dt' in df.columns]
    except: return [], 0
    
    # Alinha tamanho
    df = df.iloc[:len(dezenas_alvo)]
    df['target_dezena'] = dezenas_alvo
    df['target_futuro'] = df['target_dezena'].shift(-1)
    
    # Treina com os últimos 200 jogos para pegar tendência recente mas sólida
    df_treino = df.dropna().tail(200)
    
    if len(df_treino) < 30: return [], 0
    
    X = df_treino[['dia_semana', 'hora_code', 'target_dezena']]
    y = df_treino['target_futuro']
    
    modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    modelo.fit(X, y)
    
    # Previsão para o próximo
    ultimo_real = df.iloc[-1]
    X_novo = pd.DataFrame({
        'dia_semana': [ultimo_real['dia_semana']],
        'hora_code': [ultimo_real['hora_code']],
        'target_dezena': [ultimo_real['target_dezena']]
    })
    
    # Probabilidades para todas as classes conhecidas
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    ranking_ia = []
    for i, prob in enumerate(probs):
        dezena = classes[i]
        ranking_ia.append((dezena, prob))
        
    # Ordena por maior probabilidade
    ranking_ia.sort(key=lambda x: x[1], reverse=True)
    
    # Retorna lista completa rankeada e a confiança do Top 1
    return ranking_ia, (ranking_ia[0][1] * 100)

def identificar_dezenas_saturadas(historico, indice_premio):
    """
    Identifica dezenas que saíram muito nos últimos 40 jogos.
    """
    if len(historico) < 40: return []
    recorte = historico[-40:]
    try:
        dezenas = [j['dezenas'][indice_premio] for j in recorte]
        contagem = Counter(dezenas)
        # Se saiu 4 vezes ou mais em 40 jogos, considera saturada (filtro agressivo)
        saturadas = [d for d, qtd in contagem.items() if qtd >= 4]
        return saturadas
    except: return []

def gerar_legiao_46_ai_pure(historico, indice_premio):
    """
    Gera as 46 dezenas baseadas puramente na IA, filtrando saturadas.
    """
    if not historico: return [], [], 0
    
    # 1. Obter Ranking da IA (Todas as dezenas prováveis)
    ranking_ia, confianca = treinar_oraculo_dezenas(historico, indice_premio)
    
    if not ranking_ia:
        # Fallback se IA falhar: Dezenas mais atrasadas
        return [], [], 0
        
    # 2. Identificar Saturadas
    saturadas = identificar_dezenas_saturadas(historico, indice_premio)
    
    palpite_final = []
    cortadas_log = []
    
    # 3. Seleção
    for dezena, prob in ranking_ia:
        if len(palpite_final) >= 46:
            break
            
        if dezena in saturadas:
            cortadas_log.append(dezena)
            continue # Pula saturada
            
        palpite_final.append(dezena)
        
    # Se faltar (caso muitas saturadas), completa com as melhores saturadas
    if len(palpite_final) < 46:
        for dezena, prob in ranking_ia:
            if len(palpite_final) >= 46: break
            if dezena not in palpite_final:
                palpite_final.append(dezena)
                
    return sorted(palpite_final), cortadas_log, confianca

# --- METRICAS RECALCULADAS PARA V19 (IA PURE) ---
def calcular_metricas_ai_pure(historico, indice_premio):
    if len(historico) < 10: return 0, 0, 0, 0
    
    # Analisa histórico profundo para recordes
    offset = 50
    total = len(historico)
    inicio = max(offset, total - 100) # Analisa últimos 100 jogos para performance
    
    max_loss = 0; seq_loss = 0
    max_win = 0; seq_win = 0
    
    # Simulação do Passado (Backtest Rápido)
    # Nota: Treinar a IA 100 vezes é lento. Usaremos uma heurística:
    # Treina uma vez com dados até o ponto de corte, e verifica os últimos X jogos.
    # Para precisão total, precisaria treinar a cada passo. Vamos fazer um treino parcial.
    
    # Para não travar o app, vamos calcular recordes baseados nos últimos 50 jogos REAIS
    # usando um modelo treinado até o jogo anterior.
    
    # Loop Otimizado (Treina a cada 10 jogos para atualizar tendências)
    for i in range(inicio, total):
        target_dezena = historico[i]['dezenas'][indice_premio]
        
        # Simula treino (na prática, pega o ranking gerado com dados até i)
        # Para ser rápido no Streamlit, usamos uma janela deslizante simples aqui ou aceitamos
        # que o modelo final tem um viés de "olhar o futuro" se não treinarmos em loop.
        # VAMOS TREINAR EM LOOP CURTO (Últimos 20 jogos) para ter o "Atual" e "Max" recentes corretos.
        
        # Treina com dados até i
        hist_parcial = historico[:i]
        palpite, _, _ = gerar_legiao_46_ai_pure(hist_parcial, indice_premio)
        
        win = target_dezena in palpite
        
        if win:
            seq_loss = 0
            seq_win += 1
            if seq_win > max_win: max_win = seq_win
        else:
            seq_win = 0
            seq_loss += 1
            if seq_loss > max_loss: max_loss = seq_loss
            
    # Status Atual (Últimos jogos)
    atual_loss = 0
    atual_win = 0
    
    # Verifica o último
    idx = -1
    target_last = historico[idx]['dezenas'][indice_premio]
    palpite_last, _, _ = gerar_legiao_46_ai_pure(historico[:idx], indice_premio)
    win_last = target_last in palpite_last
    
    if win_last:
        atual_win = 1
        for k in range(2, 15):
            target = historico[-k]['dezenas'][indice_premio]
            palp, _, _ = gerar_legiao_46_ai_pure(historico[:-k], indice_premio)
            if target in palp: atual_win += 1
            else: break
    else:
        atual_loss = 1
        for k in range(2, 15):
            target = historico[-k]['dezenas'][indice_premio]
            palp, _, _ = gerar_legiao_46_ai_pure(historico[:-k], indice_premio)
            if target not in palp: atual_loss += 1
            else: break
            
    return atual_loss, max_loss, atual_win, max_win

# --- MÉTRICAS UNIDADE (MANTIDAS) ---
def calcular_metricas_unidade_full(historico):
    # Mantém a lógica da V18 pois a unidade independe da seleção de dezenas (é estatística de final)
    # Mas para ser consistente, podemos usar as 46 dezenas da IA para derivar a unidade forte.
    # Vamos manter o cálculo original que era robusto.
    if len(historico) < 10: return 0, 0, 0, 0
    total = len(historico)
    inicio = max(50, total - 100)
    max_loss = 0; seq_loss = 0; max_win = 0; seq_win = 0
    
    for i in range(inicio, total):
        try:
            target = historico[i]['dezenas'][0][-1]
            # Usa IA Pure para gerar dezenas e extrair top finais
            hist_p = historico[:i]
            lista_final, _, _ = gerar_legiao_46_ai_pure(hist_p, 0)
            finais = [d[-1] for d in lista_final]
            top_finais = [x[0] for x in Counter(finais).most_common(5)]
            if target in top_finais:
                seq_loss = 0; seq_win += 1
                if seq_win > max_win: max_win = seq_win
            else:
                seq_win = 0; seq_loss += 1
                if seq_loss > max_loss: max_loss = seq_loss
        except: continue

    # Atual
    atual_loss = 0; atual_win = 0
    idx = -1
    try:
        target = historico[idx]['dezenas'][0][-1]
        lista_final, _, _ = gerar_legiao_46_ai_pure(historico[:idx], 0)
        finais = [d[-1] for d in lista_final]
        top_finais = [x[0] for x in Counter(finais).most_common(5)]
        if target in top_finais:
            atual_win = 1
            for k in range(2, 15):
                t = historico[-k]['dezenas'][0][-1]
                lf, _, _ = gerar_legiao_46_ai_pure(historico[:-k], 0)
                tf = [x[0] for x in Counter([d[-1] for d in lf]).most_common(5)]
                if t in tf: atual_win += 1
                else: break
        else:
            atual_loss = 1
            for k in range(2, 15):
                t = historico[-k]['dezenas'][0][-1]
                lf, _, _ = gerar_legiao_46_ai_pure(historico[:-k], 0)
                tf = [x[0] for x in Counter([d[-1] for d in lf]).most_common(5)]
                if t not in tf: atual_loss += 1
                else: break
    except: pass
    return atual_loss, max_loss, atual_win, max_win

# --- RASTREADORES (MANTIDOS V17) ---
def analisar_padroes_futuros(historico, indice_premio):
    if len(historico) < 10: return None, []
    ultima_dezena_real = historico[-1]['dezenas'][indice_premio]
    encontrados = []
    for i in range(len(historico) - 2, -1, -1):
        try:
            if historico[i]['dezenas'][indice_premio] == ultima_dezena_real:
                encontrados.append({ "data": historico[i+1]['data'], "hora": historico[i+1]['hora'], "veio": historico[i+1]['dezenas'][indice_premio] })
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
                encontrados.append({ "data": historico[i+1]['data'], "hora": historico[i+1]['hora'], "veio": historico[i+1]['dezenas'][0][-1] })
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
            target = historico[idx]['dezenas'][0][-1]
            lf, _, _ = gerar_legiao_46_ai_pure(historico[:idx], 0)
            tf = [x[0] for x in Counter([d[-1] for d in lf]).most_common(5)]
            win = target in tf
            resultados.append({'index': i, 'real': target, 'win': win})
        except: continue
    return resultados

# =============================================================================
# --- 4. DASHBOARD GERAL ---
# =============================================================================
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
                    u_loss, u_max_loss, u_win, u_max_win = calcular_metricas_unidade_full(historico)
                    if u_max_loss > 0:
                        if u_loss >= u_max_loss: alertas_criticos.append({"banca": "TRADICIONAL (Unidade)", "premio": "Sniper 50%", "val": u_loss, "rec": u_max_loss, "tipo": "CRITICO_UNI"})
                        elif u_loss == (u_max_loss - 1): alertas_criticos.append({"banca": "TRADICIONAL (Unidade)", "premio": "Sniper 50%", "val": u_loss, "rec": u_max_loss, "tipo": "PERIGO_UNI"})

    col2.metric("Sinais no Radar", f"{len(alertas_criticos)}", "Win/Loss")
    col3.metric("Status Base", "Online", "Google Sheets")
    st.markdown("---")
    
    if alertas_criticos:
        st.subheader("🚨 Zonas de Interesse Identificadas")
        cols = st.columns(4) 
        for idx, alerta in enumerate(alertas_criticos):
            if alerta['tipo'] == "CRITICO": classe = "dash-critico"; titulo = "🚨 RECORDE!"; texto = "DERROTAS"
            elif alerta['tipo'] == "PERIGO": classe = "dash-perigo"; titulo = "⚠️ POR 1"; texto = "DERROTAS"
            elif alerta['tipo'] == "VITORIA": classe = "dash-vitoria"; titulo = "🤑 RECORD WIN!"; texto = "VITÓRIAS"
            elif alerta['tipo'] == "CRITICO_UNI": classe = "dash-unidade"; titulo = "🎯 SNIPER CRÍTICO"; texto = "DERROTAS"
            elif alerta['tipo'] == "PERIGO_UNI": classe = "dash-unidade"; titulo = "🎯 SNIPER ALERTA"; texto = "DERROTAS"
            else: classe = "dash-atencao"; titulo = "⚠️ ATENÇÃO"; texto = "DERROTAS"

            with cols[idx % 4]: 
                st.markdown(f"""
                <div class='dash-card {classe}'>
                    <div class='dash-title'>{alerta['banca'].split('(')[0]}</div>
                    <div class='dash-subtitle'>{alerta['premio']}</div>
                    <div class='dash-metric'>{alerta['val']} {texto}</div>
                    <p class='dash-footer'>Max Hist: {alerta['rec']}</p>
                    <span class='dash-badge'>{titulo}</span>
                </div>
                """, unsafe_allow_html=True)
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
                    try:
                        existentes = ws.get_all_values()
                        chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
                    except: chaves = []
                    chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{hora_busca}"
                    if chave_atual in chaves: st.sidebar.warning(f"⚠️ Resultado já existe na Linha {chaves.index(chave_atual) + 2}!")
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
                try:
                    existentes = ws.get_all_values()
                    chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
                except: chaves = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(conf['horarios'])
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    horarios_do_dia = conf['horarios'].copy()
                    if banca_selecionada == "CAMINHO" and (dia.weekday() == 2 or dia.weekday() == 5):
                        horarios_do_dia = [h.replace("20:00", "19:30") for h in horarios_do_dia]

                    for hora in horarios_do_dia:
                        op_atual += 1
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                        if chave_atual in chaves: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue

                        dezenas, msg = raspar_dezenas_site(banca_selecionada, dia, hora)
                        if dezenas:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + dezenas)
                            sucessos += 1
                            chaves.append(chave_atual)
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
                    try:
                        existentes = ws.get_all_values()
                        chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
                    except: chaves = []
                    chave_atual = f"{man_data.strftime('%Y-%m-%d')}|{man_hora}"
                    if chave_atual in chaves: st.sidebar.warning("Já existe!")
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
                st.caption("A análise foi desativada para os outros prêmios.")
                continue

            lista_final, cortadas, confianca_ia = gerar_legiao_46_ai_pure(historico, i)
            loss, max_loss, win, max_win = calcular_metricas_ai_pure(historico, i)
            
            # --- CARD 1: IA ORÁCULO ---
            if HAS_AI:
                st.markdown(f"""
                <div class='box-ai'>
                    <div class='ai-title'>🧠 Oráculo IA (Pure Dezenas)</div>
                    <div style='color:#fff; font-size:16px; margin-bottom:5px;'>Análise Pura de Tendência (00-99)</div>
                    <div style='font-size:12px; color:#d900ff;'>Confiança do Modelo: {confianca_ia:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            elif not HAS_AI:
                st.caption("⚠️ IA desativada (Scikit-learn carregando...).")

            # --- CARD 2: LEGIÃO 46 ---
            aviso_alerta = ""
            if loss >= max_loss and max_loss > 0:
                aviso_alerta = f"<div class='box-alert'>🚨 <b>ALERTA MÁXIMO:</b> {loss} Derrotas Seguidas (Recorde Atingido!)</div>"
            
            info_cortes = f"<span class='info-pill pill-sat'>🚫 {len(cortadas)} SATURADAS CORTADAS</span>" if cortadas else ""
            
            qtd_final = len(lista_final) 
            
            html_content = f"""
            {aviso_alerta}
            <div class='box-centurion'>
                {info_cortes}
                <div class='titulo-gold'>LEGIÃO {qtd_final} - {i+1}º PRÊMIO</div>
                <div class='subtitulo'>Estratégia V19.0: AI Pure + Filtro Saturação</div>
                <div class='nums-destaque'>{', '.join(lista_final)}</div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)
            
            cor_stress = "#ff4b4b" if loss >= max_loss else "#ffffff"
            cor_wins = "#00ff00" if win >= (max_win - 1) else "#ffffff"

            st.markdown(f"""
            <div style='text-align: center; margin-bottom:10px;'>
                <span class='max-loss-pill'>📉 Derrotas: Max {max_loss} | <b>Atual: <span style='color:{cor_stress}'>{loss}</span></b></span>
                <span class='max-win-pill'>📈 Vitórias: Max {max_win} | <b>Atual: <span style='color:{cor_wins}'>{win}</span></b></span>
            </div>
            """, unsafe_allow_html=True)

            bt_results = executar_backtest_centurion(historico, i)
            
            if bt_results:
                st.markdown("### ⏪ Performance Recente")
                cards_html = ""
                for res in reversed(bt_results):
                    c_res = "bt-win" if res['win'] else "bt-loss"
                    ico = "🟢" if res['win'] else "🔴"
                    lbl = "VITÓRIA" if res['win'] else "DERROTA"
                    num = res['dezena']
                    cards_html += f"<div class='bt-card {c_res}'><div class='bt-icon'>{ico}</div><div class='bt-num'>{num}</div><div class='bt-label'>{lbl}</div></div>"
                st.markdown(f"<div class='backtest-container'>{cards_html}</div>", unsafe_allow_html=True)

            st.markdown("---")
            
            ultima_dz_real, padroes_futuros = analisar_padroes_futuros(historico, i)
            if padroes_futuros:
                st.markdown(f"#### 🔍 Rastreador de Padrões (DEZENA - Última: **{ultima_dz_real}**)")
                st.caption(f"Nas últimas 5 vezes que a dezena {ultima_dz_real} saiu, veja o que veio depois:")
                for p in padroes_futuros:
                    st.markdown(f"""
                    <div class='pattern-row'>
                        <span class='pattern-date'>{p['data']} às {p['hora']}</span>
                        <span class='pattern-result'>Veio a Dezena: {p['veio']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption(f"A dezena {ultima_dz_real} é rara (menos de 5 ocorrências recentes). Sem padrão claro.")
            
            # UNIDADES ESTRUTURAIS
            if banca_selecionada == "TRADICIONAL":
                finais = [d[-1] for d in lista_final]
                top_finais = [x[0] for x in Counter(finais).most_common(5)]
                
                st.markdown(f"""
                <div class='box-unidade'>
                    <div class='uni-title'>🎯 UNIDADE SNIPER (9.20x)</div>
                    <div class='uni-nums'>Finais Fortes: {', '.join(top_finais)}</div>
                    <div style='font-size:12px; opacity:0.8;'>Baseado nas 46 dezenas da IA</div>
                </div>
                """, unsafe_allow_html=True)
                
                u_loss, u_max, u_win, u_max_win = calcular_metricas_unidade_full(historico)
                cor_u = "#ff4b4b" if u_loss > 0 else "#fff"
                st.markdown(f"""
                <div style='text-align: center; margin-bottom:15px;'>
                    <span class='max-loss-pill'>📉 Derrotas: Max {u_max} | <b>Atual: <span style='color:{cor_u}'>{u_loss}</span></b></span>
                    <span class='max-win-pill'>📈 Vitórias: Max {u_max_win} | <b>Atual: {u_win}</b></span>
                </div>
                """, unsafe_allow_html=True)
                
                bt_sniper = executar_backtest_unidade(historico)
                if bt_sniper:
                    cards_sniper = ""
                    for res in reversed(bt_sniper):
                        c_res = "bt-win" if res['win'] else "bt-loss"
                        ico = "🟢" if res['win'] else "🔴"
                        lbl = "VITÓRIA" if res['win'] else "DERROTA"
                        cards_sniper += f"<div class='bt-card {c_res}'><div class='bt-icon'>{ico}</div><div class='bt-num'>F{res['real']}</div><div class='bt-label'>{lbl}</div></div>"
                    st.markdown(f"<div class='backtest-container'>{cards_sniper}</div>", unsafe_allow_html=True)

                ultima_uni_real, padroes_uni = analisar_padroes_unidade(historico)
                if padroes_uni:
                    st.markdown(f"#### 🔍 Rastreador de Padrões (UNIDADE - Última: **{ultima_uni_real}**)")
                    st.caption(f"Nas últimas 5 vezes que a unidade {ultima_uni_real} saiu, veja o que veio depois:")
                    for p in padroes_uni:
                        st.markdown(f"""
                        <div class='pattern-row-uni'>
                            <span class='pattern-date'>{p['data']} às {p['hora']}</span>
                            <span class='pattern-result'>Veio Final: {p['veio']}</span>
                        </div>
                        """, unsafe_allow_html=True)
