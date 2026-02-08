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
st.set_page_config(page_title="CENTURION 75 - V15.0 Sniper Test", page_icon="🛡️", layout="wide")

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

# Mapeamento Grupos
GRUPOS_BICHOS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
    dezenas = [("00" if n == 100 else f"{n:02}") for n in range(inicio, fim + 1)]
    GRUPOS_BICHOS[g] = dezenas 

# Mapeamento Reverso
DEZENA_TO_GRUPO = {}
for g, nums in GRUPOS_BICHOS.items():
    for n in nums: DEZENA_TO_GRUPO[n] = g

# Estilo Visual
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    .box-centurion {
        background: linear-gradient(135deg, #5c0000, #2b0000);
        border: 2px solid #ffd700; padding: 20px; border-radius: 12px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 0 25px rgba(255, 215, 0, 0.15);
    }
    .box-ai {
        background: linear-gradient(135deg, #2b005c, #1a0033);
        border: 1px solid #b300ff; padding: 15px; border-radius: 10px;
        margin-bottom: 15px; text-align: left;
    }
    .ai-title { color: #b300ff; font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 10px; }
    
    /* BOX UNIDADE ESPECIAL (AZUL) */
    .box-unidade {
        background: linear-gradient(135deg, #003366, #004080);
        border: 2px solid #0099ff; padding: 15px; border-radius: 10px;
        margin-bottom: 15px; text-align: center;
        box-shadow: 0 0 15px rgba(0, 153, 255, 0.2);
    }
    .uni-title { color: #0099ff; font-weight: 900; font-size: 18px; text-transform: uppercase; margin-bottom: 5px; }
    .uni-nums { font-size: 22px; color: #fff; font-weight: bold; letter-spacing: 3px; }
    
    .box-alert {
        background-color: #4a0000; border: 2px solid #ff0000;
        padding: 15px; border-radius: 10px; text-align: center;
        margin: 15px 0; animation: pulse 2s infinite; font-size: 18px; font-weight: bold;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
    }
    .titulo-gold { color: #ffd700; font-weight: 900; font-size: 26px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }
    .subtitulo { color: #cccccc; font-size: 14px; margin-bottom: 20px; font-style: italic; }
    .nums-destaque { font-size: 20px; color: #ffffff; font-weight: bold; word-wrap: break-word; line-height: 1.8; letter-spacing: 1px; }
    .lucro-info { background-color: rgba(0, 255, 0, 0.05); border: 1px solid #00ff00; padding: 10px; border-radius: 8px; color: #00ff00; font-weight: bold; margin-top: 20px; font-size: 16px; }
    .info-pill { padding: 5px 15px; border-radius: 5px; font-weight: bold; font-size: 13px; display: inline-block; margin: 5px; }
    .pill-sat { background-color: #330000; color: #ff4b4b; border: 1px solid #ff4b4b; }
    .pill-ai { background-color: #2b005c; color: #d900ff; border: 1px solid #d900ff; }
    .pill-final { background-color: #4a004a; color: #ff00ff; border: 1px solid #ff00ff; }
    .pill-pent { background-color: #003366; color: #00ccff; border: 1px solid #00ccff; }
    
    .backtest-container { display: flex; justify-content: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
    .bt-card { background-color: rgba(30, 30, 30, 0.9); border-radius: 8px; padding: 10px; width: 90px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 20px; margin-bottom: 2px; }
    .bt-num { font-size: 14px; font-weight: bold; }
    .bt-label { font-size: 10px; opacity: 0.8; text-transform: uppercase; }
    .max-loss-pill { background-color: rgba(255, 0, 0, 0.15); border: 1px solid #ff4b4b; color: #ffcccc; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 15px; }
    .max-win-pill { background-color: rgba(0, 255, 0, 0.15); border: 1px solid #00ff00; color: #ccffcc; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 15px; margin-left: 10px; }
    
    .dash-card { padding: 10px 5px; border-radius: 8px; margin-bottom: 8px; text-align: center; border-left: 4px solid #fff; }
    .dash-critico { background-color: #4a0000; border-color: #ff0000; }
    .dash-perigo { background-color: #662200; border-color: #ff5500; }
    .dash-atencao { background-color: #4a3b00; border-color: #ffcc00; }
    .dash-vitoria { background-color: #003300; border-color: #00ff00; }
    .dash-title { font-size: 13px; font-weight: 900; margin-bottom: 0px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dash-subtitle { font-size: 11px; opacity: 0.8; margin-bottom: 2px; }
    .dash-metric { font-size: 20px; font-weight: bold; margin: 2px 0; line-height: 1.2; }
    .dash-footer { font-size: 10px; opacity: 0.7; margin: 0; }
    .dash-badge { font-size: 10px; font-weight: bold; margin-top: 2px; display: block; }

    div[data-testid="stTable"] table { color: white; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (V14.5 ANTI-CLONE) ---
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
# --- 3. CÉREBRO: IA + ESTATÍSTICA (V15.0) ---
# =============================================================================

def oraculo_ia(historico, indice_premio):
    if not HAS_AI or len(historico) < 50: return [], 0 
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'])
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['hora'])
    grupos_saiu = []
    for d_lista in df['dezenas']:
        try:
            d = d_lista[indice_premio]
            g = DEZENA_TO_GRUPO.get(d, 0)
            grupos_saiu.append(g)
        except: grupos_saiu.append(0)
    df['target_grupo'] = grupos_saiu
    df['target_futuro'] = df['target_grupo'].shift(-1)
    df_treino = df.dropna().tail(200) 
    if len(df_treino) < 30: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target_grupo']]
    y = df_treino['target_futuro']
    modelo = RandomForestClassifier(n_estimators=50, random_state=42) 
    modelo.fit(X, y)
    ultimo_real = df.iloc[-1]
    X_novo = pd.DataFrame({
        'dia_semana': [ultimo_real['dia_semana']],
        'hora_code': [ultimo_real['hora_code']],
        'target_grupo': [ultimo_real['target_grupo']]
    })
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking_ia = []
    for i, prob in enumerate(probs):
        grupo = int(classes[i])
        ranking_ia.append((grupo, prob))
    ranking_ia.sort(key=lambda x: x[1], reverse=True)
    top_3_grupos = [x[0] for x in ranking_ia[:3]]
    confianca = ranking_ia[0][1] * 100 
    return top_3_grupos, confianca

def calcular_radar_pentagono(historico, indice_premio):
    if not historico: return []
    ultima_aparicao = {}
    total_jogos = len(historico)
    for i in range(total_jogos - 1, -1, -1):
        try:
            dz = historico[i]['dezenas'][indice_premio]
            if dz in DEZENA_TO_GRUPO:
                grp = DEZENA_TO_GRUPO[dz]
                if grp not in ultima_aparicao: ultima_aparicao[grp] = i
        except: pass
        if len(ultima_aparicao) == 25: break
    atrasos = []
    for g in range(1, 26):
        atraso = (total_jogos - 1) - ultima_aparicao.get(g, -1)
        atrasos.append((g, atraso))
    atrasos.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in atrasos[:5]]

def gerar_matriz_hibrida_ai(historico, indice_premio, usar_ia=True):
    if not historico:
        padrao = []
        for g in range(1, 26): padrao.extend(GRUPOS_BICHOS[g][:3])
        return padrao, [], None, [], None, [], 0

    ultimo_jogo = historico[-1]
    try: ultima_dezena = ultimo_jogo['dezenas'][indice_premio]
    except: ultima_dezena = "99"
    final_bloqueado = ultima_dezena[-1] 

    tamanho_analise = 50
    if len(historico) < 50: tamanho_analise = len(historico)
    recorte = historico[-tamanho_analise:]
    dezenas_historico = []
    for jogo in recorte:
        try: dezenas_historico.append(jogo['dezenas'][indice_premio])
        except: pass
    contagem_dezenas = Counter(dezenas_historico)

    contagem_grupos = {}
    for g, dzs in GRUPOS_BICHOS.items():
        soma = 0
        for d in dzs: soma += contagem_dezenas.get(d, 0)
        contagem_grupos[g] = soma
    
    rank_grupos_sat = sorted(contagem_grupos.items(), key=lambda x: x[1], reverse=True)
    grupo_saturado = rank_grupos_sat[0][0]
    freq_saturado = rank_grupos_sat[0][1]

    grupos_atrasados = calcular_radar_pentagono(historico, indice_premio)
    
    if usar_ia:
        grupos_ia, confianca_ia = oraculo_ia(historico, indice_premio)
    else:
        grupos_ia, confianca_ia = [], 0
    
    grupos_imunes = list(set(grupos_atrasados + grupos_ia))

    palpite_inicial = []
    reservas_disponiveis = []
    dezenas_cortadas_log = []

    for grupo, lista_dezenas in GRUPOS_BICHOS.items():
        if grupo in grupos_imunes:
            palpite_inicial.extend(lista_dezenas)
            continue

        if grupo == grupo_saturado:
            for d in lista_dezenas: reservas_disponiveis.append(d)
            dezenas_cortadas_log.append(f"G{grupo} (Saturado)")
            continue 
            
        rank_dz = []
        for d in lista_dezenas:
            freq = contagem_dezenas.get(d, 0)
            rank_dz.append((d, freq))
        rank_dz.sort(key=lambda x: x[1])
        dezena_removida = rank_dz[0][0]
        dezenas_vencedoras = [x[0] for x in rank_dz[1:]]
        
        palpite_inicial.extend(dezenas_vencedoras)
        reservas_disponiveis.append(dezena_removida)

    palpite_filtrado = []
    for d in palpite_inicial:
        grp = DEZENA_TO_GRUPO.get(d)
        if d.endswith(final_bloqueado) and grp not in grupos_imunes:
            pass 
        else:
            palpite_filtrado.append(d)
    
    vagas_abertas = 75 - len(palpite_filtrado)
    reservas_validas = [d for d in reservas_disponiveis if not d.endswith(final_bloqueado)]
    reservas_rank = []
    for d in reservas_validas: reservas_rank.append((d, contagem_dezenas.get(d, 0)))
    reservas_rank.sort(key=lambda x: x[1], reverse=True)
    
    for i in range(min(vagas_abertas, len(reservas_rank))):
        palpite_filtrado.append(reservas_rank[i][0])
        
    palpite_final = sorted(list(set(palpite_filtrado)))
    dados_sat = (grupo_saturado, freq_saturado, tamanho_analise)
    
    return palpite_final, dezenas_cortadas_log, dados_sat, grupos_atrasados, final_bloqueado, grupos_ia, confianca_ia

def calcular_metricas_completas(historico, indice_premio, usar_ia_no_backtest=False):
    if len(historico) < 10: return 0, 0, 0, 0
    offset_treino = 50
    total_disponivel = len(historico)
    inicio_simulacao = max(offset_treino, total_disponivel - 50)
    
    max_derrotas = 0; seq_derrotas = 0
    max_vitorias = 0; seq_vitorias = 0
    
    for i in range(inicio_simulacao, total_disponivel):
        target_game = historico[i]
        target_dezena = target_game['dezenas'][indice_premio]
        palpite, _, _, _, _, _, _ = gerar_matriz_hibrida_ai(historico[:i], indice_premio, usar_ia=usar_ia_no_backtest) 
        win = target_dezena in palpite
        
        if win:
            seq_derrotas = 0
            seq_vitorias += 1
            if seq_vitorias > max_vitorias: max_vitorias = seq_vitorias
        else:
            seq_vitorias = 0
            seq_derrotas += 1
            if seq_derrotas > max_derrotas: max_derrotas = seq_derrotas

    atual_derrotas = 0
    atual_vitorias = 0
    
    for i in range(1, 20): 
        idx = -i
        target_game = historico[idx]
        target_dezena = target_game['dezenas'][indice_premio]
        palpite, _, _, _, _, _, _ = gerar_matriz_hibrida_ai(historico[:idx], indice_premio, usar_ia=usar_ia_no_backtest)
        win = target_dezena in palpite
        
        if i == 1 and not win:
            atual_derrotas = 1
        elif i == 1 and win:
            atual_vitorias = 1
        
        elif atual_derrotas > 0:
            if not win: atual_derrotas += 1
            else: break 
        elif atual_vitorias > 0:
            if win: atual_vitorias += 1
            else: break 

    return atual_derrotas, max_derrotas, atual_vitorias, max_vitorias

# --- BACKTEST NORMAL (DEZENAS) ---
def executar_backtest_centurion(historico, indice_premio):
    if len(historico) < 60: return []
    resultados = []
    for i in range(1, 5):
        target_idx = -i
        target_game = historico[target_idx]
        target_dezena = target_game['dezenas'][indice_premio]
        palpite, _, _, _, _, _, _ = gerar_matriz_hibrida_ai(historico[:target_idx], indice_premio, usar_ia=True)
        vitoria = target_dezena in palpite
        resultados.append({'index': i, 'dezena': target_dezena, 'win': vitoria})
    return resultados

# --- NOVO: BACKTEST SNIPER (UNIDADES) ---
def executar_backtest_unidade(historico):
    if len(historico) < 60: return []
    resultados = []
    for i in range(1, 5):
        target_idx = -i
        target_game = historico[target_idx]
        
        # Pega a unidade real do 1º prêmio
        try:
            target_dezena = target_game['dezenas'][0]
            target_unidade = target_dezena[-1]
        except: continue

        # Gera previsão com dados passados
        hist_treino = historico[:target_idx]
        lista_final, _, _, _, _, _, _ = gerar_matriz_hibrida_ai(hist_treino, 0, usar_ia=True)
        
        # Lógica Sniper (Top 3 Finais)
        finais = [d[-1] for d in lista_final]
        top_finais = [x[0] for x in Counter(finais).most_common(3)]
        
        win = target_unidade in top_finais
        resultados.append({'index': i, 'real': target_unidade, 'win': win})
    
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
                    stress, max_stress, wins, max_wins = calcular_metricas_completas(historico, i, usar_ia_no_backtest=False)
                    
                    if max_stress > 0:
                        percentual_stress = stress / max_stress
                        if stress >= max_stress:
                            alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": stress, "rec": max_stress, "tipo": "CRITICO"})
                        elif stress == (max_stress - 1):
                            alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": stress, "rec": max_stress, "tipo": "PERIGO"})
                        elif percentual_stress >= 0.7:
                            alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": stress, "rec": max_stress, "tipo": "ATENCAO"})
                    
                    if max_wins > 2 and wins > 0:
                        if wins == (max_wins - 1):
                             alertas_criticos.append({"banca": config['display'], "premio": f"{i+1}º Prêmio", "val": wins, "rec": max_wins, "tipo": "VITORIA"})

    col2.metric("Sinais no Radar", f"{len(alertas_criticos)}", "Win/Loss")
    col3.metric("Status Base", "Online", "Google Sheets")
    st.markdown("---")
    
    if alertas_criticos:
        st.subheader("🚨 Zonas de Interesse Identificadas")
        cols = st.columns(4) 
        for idx, alerta in enumerate(alertas_criticos):
            if alerta['tipo'] == "CRITICO":
                classe = "dash-critico"; titulo = "🚨 RECORDE!"; texto = "Loss"
            elif alerta['tipo'] == "PERIGO":
                classe = "dash-perigo"; titulo = "⚠️ POR 1"; texto = "Loss"
            elif alerta['tipo'] == "ATENCAO":
                classe = "dash-atencao"; titulo = "⚠️ ATENÇÃO"; texto = "Loss"
            else: # VITORIA
                classe = "dash-vitoria"; titulo = "🤑 RECORD WIN!"; texto = "Wins"

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

            lista_final, cortadas, sat, gps_atrasados, final_bloq, gps_ia, confianca_ia = gerar_matriz_hibrida_ai(historico, i, usar_ia=True)
            stress, max_stress, wins, max_wins = calcular_metricas_completas(historico, i, usar_ia_no_backtest=True)
            
            if banca_selecionada == "TRADICIONAL":
                finais = [d[-1] for d in lista_final]
                top_finais = [x[0] for x in Counter(finais).most_common(3)]
                st.markdown(f"""
                <div class='box-unidade'>
                    <div class='uni-title'>🎯 UNIDADE SNIPER (9.20x)</div>
                    <div class='uni-nums'>Finais Fortes: {', '.join(top_finais)}</div>
                    <div style='font-size:12px; opacity:0.8;'>Baseado nas dezenas geradas</div>
                </div>
                """, unsafe_allow_html=True)
                
                # --- BACKTEST SNIPER (NOVO) ---
                bt_sniper = executar_backtest_unidade(historico)
                if bt_sniper:
                    cards_sniper = ""
                    for res in reversed(bt_sniper):
                        c_res = "bt-win" if res['win'] else "bt-loss"
                        ico = "🟢" if res['win'] else "🔴"
                        lbl = "WIN" if res['win'] else "LOSS"
                        # Mostra qual foi o final real que saiu
                        cards_sniper += f"<div class='bt-card {c_res}'><div class='bt-icon'>{ico}</div><div class='bt-num'>F{res['real']}</div><div class='bt-label'>{lbl}</div></div>"
                    st.markdown(f"<div class='backtest-container'>{cards_sniper}</div>", unsafe_allow_html=True)
                # -------------------------------

            if HAS_AI and gps_ia:
                st.markdown(f"""
                <div class='box-ai'>
                    <div class='ai-title'>🧠 Oráculo IA (Random Forest)</div>
                    <div style='color:#e0e0e0; margin-bottom:5px;'>Previsão de Grupos Fortes: <b>{', '.join(map(str, gps_ia))}</b></div>
                    <div style='font-size:12px; color:#b300ff;'>Confiança do Modelo: {confianca_ia:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            elif not HAS_AI:
                st.caption("⚠️ IA desativada (Scikit-learn carregando...).")

            aviso_alerta = ""
            if stress >= max_stress and max_stress > 0:
                aviso_alerta = f"<div class='box-alert'>🚨 <b>ALERTA MÁXIMO:</b> {stress} Derrotas Seguidas (Recorde Atingido!)</div>"
            
            info_sat = f"<span class='info-pill pill-sat'>🚫 SATURADO: G{sat[0]} ({sat[1]}x)</span>" if sat else ""
            
            todos_imunes = list(set(gps_atrasados + gps_ia))
            info_imunes = f"<span class='info-pill pill-ai'>🛡️ IMUNIZADOS (IA+P): {', '.join(map(str, todos_imunes))}</span>" if todos_imunes else ""
            
            info_final = f"<span class='info-pill pill-final'>🛑 FINAL: {final_bloq}</span>" if final_bloq else ""
            
            qtd_final = len(lista_final) 
            
            html_content = f"""
            {aviso_alerta}
            <div class='box-centurion'>
                {info_sat} {info_imunes} {info_final}
                <div class='titulo-gold'>LEGIÃO {qtd_final} - {i+1}º PRÊMIO</div>
                <div class='subtitulo'>Estratégia V15: Tradicional + Unidade Sniper</div>
                <div class='nums-destaque'>{', '.join(lista_final)}</div>
                <div class='lucro-info'>💰 Custo: R$ {qtd_final},00 | Retorno: R$ 92,00 | Lucro: R$ {92 - qtd_final},00</div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)
            
            cor_stress = "#ff4b4b" if stress >= max_stress else "#ffffff"
            cor_wins = "#00ff00" if wins >= (max_wins - 1) else "#ffffff"

            st.markdown(f"""
            <div style='text-align: center; margin-bottom:10px;'>
                <span class='max-loss-pill'>📉 Derrotas: Max {max_stress} | <b>Atual: <span style='color:{cor_stress}'>{stress}</span></b></span>
                <span class='max-win-pill'>📈 Vitórias: Max {max_wins} | <b>Atual: <span style='color:{cor_wins}'>{wins}</span></b></span>
            </div>
            """, unsafe_allow_html=True)

            bt_results = executar_backtest_centurion(historico, i)
            
            if bt_results:
                st.markdown("### ⏪ Performance Recente")
                cards_html = ""
                for res in reversed(bt_results):
                    c_res = "bt-win" if res['win'] else "bt-loss"
                    ico = "🟢" if res['win'] else "🔴"
                    lbl = "WIN" if res['win'] else "LOSS"
                    num = res['dezena']
                    cards_html += f"<div class='bt-card {c_res}'><div class='bt-icon'>{ico}</div><div class='bt-num'>{num}</div><div class='bt-label'>{lbl}</div></div>"
                
                st.markdown(f"<div class='backtest-container'>{cards_html}</div>", unsafe_allow_html=True)
            else:
                st.caption("ℹ️ Baixe mais resultados (mínimo 60) para ver o Backtest e Risco.")

            st.markdown("---")
            with st.expander("✂️ Ver Detalhes (Grupos e Cortes)"):
                st.write(f"Grupos Cortados: {', '.join(cortadas)}")
