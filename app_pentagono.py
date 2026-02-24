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
st.set_page_config(page_title="PENTÁGONO V63.0 Precision", page_icon="💲", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (1º Prêmio)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "tipo": "SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    "LOTEP": { "display_name": "LOTEP (1º ao 5º)", "nome_aba": "LOTEP_TOP5", "slug": "lotep", "tipo": "PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHODASORTE": { "display_name": "CAMINHO (1º ao 5º)", "nome_aba": "CAMINHO_TOP5", "slug": "caminho-da-sorte", "tipo": "PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "MONTECAI": { "display_name": "MONTE CARLOS (1º ao 5º)", "nome_aba": "MONTE_TOP5", "slug": "nordeste-monte-carlos", "tipo": "PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] }
}

GRUPO_TO_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
    dezenas_do_grupo = []
    for n in range(inicio, fim + 1):
        d_str = "00" if n == 100 else f"{n:02}"
        dezenas_do_grupo.append(d_str)
    GRUPO_TO_DEZENAS[g] = dezenas_do_grupo

GEMEAS = ['00', '11', '22', '33', '44', '55', '66', '77', '88', '99']

NOME_BICHOS = {
    1: "Avestruz", 2: "Águia", 3: "Burro", 4: "Borboleta", 5: "Cachorro",
    6: "Cabra", 7: "Carneiro", 8: "Camelo", 9: "Cobra", 10: "Coelho",
    11: "Cavalo", 12: "Elefante", 13: "Galo", 14: "Gato", 15: "Jacaré",
    16: "Leão", 17: "Macaco", 18: "Porco", 19: "Pavão", 20: "Peru",
    21: "Touro", 22: "Tigre", 23: "Urso", 24: "Veado", 25: "Vaca"
}

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #00ff00 !important; }
    div[data-testid="stMetricValue"] { font-size: 20px; font-weight: bold; }
    .css-1wivap2 { font-size: 14px !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (NORMALIZAÇÃO ABSOLUTA) ---
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
        if ':' in h_clean:
            partes = h_clean.split(':')
            return f"{int(partes[0]):02}:{int(partes[1]):02}"
        else:
            return f"{int(h_clean):02}:00"
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
                                if p_str.isdigit(): premios.append(p_str.zfill(2)[-2:])
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
    url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    if data_alvo == date.today(): url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        if ':' in raw: h_detect = raw
                        elif 'h' in raw: h_detect = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: h_detect = raw.strip().zfill(2) + ":00"
                        
                        h_alvo_norm = normalizar_hora(horario_alvo)
                        h_detect_norm = normalizar_hora(h_detect)
                        
                        if h_detect_norm == h_alvo_norm:
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
                                        limite = 1 if config['tipo'] == "SOLO" else 5
                                        if 1 <= p_idx <= limite:
                                            clean_num = re.sub(r'\D', '', numero_txt)
                                            if len(clean_num) >= 2: dezenas_encontradas.append(clean_num[-2:])
                            if config['tipo'] == "SOLO":
                                if len(dezenas_encontradas) >= 1: return [dezenas_encontradas[0], "00", "00", "00", "00"], "Sucesso"
                            else:
                                if len(dezenas_encontradas) >= 5: return dezenas_encontradas[:5], "Sucesso"
                            return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA ORACLE 46 DEZENAS ---
# =============================================================================

def get_grupo(dezena):
    try:
        d = int(dezena)
        if d == 0: return 25
        if d > 99: return 25 
        val = (d - 1) // 4 + 1
        return val
    except: return 1

def analisar_efeito_ima(historico, indice_premio):
    if len(historico) < 10: return [], [], "Dados Insuficientes"
    try:
        ult_dezena = historico[-1]['premios'][indice_premio]
        ult_grupo = get_grupo(ult_dezena)
        nome_ult = NOME_BICHOS.get(ult_grupo, str(ult_grupo))
    except: return [], [], "Erro Leitura"
    contagem_seguinte = Counter()
    total_ocorrencias = 0
    for i in range(len(historico) - 1):
        try:
            d_atual = historico[i]['premios'][indice_premio]
            g_atual = get_grupo(d_atual)
            if g_atual == ult_grupo:
                d_prox = historico[i+1]['premios'][indice_premio]
                g_prox = get_grupo(d_prox)
                contagem_seguinte[g_prox] += 1
                total_ocorrencias += 1
        except: continue
    if total_ocorrencias == 0: return [], [], f"Bicho {nome_ult} é Inédito!"
    imas = [g for g, c in contagem_seguinte.most_common(5)]
    todos_grupos = set(range(1, 26))
    sairam = set(contagem_seguinte.keys())
    repelidos = list(todos_grupos - sairam)
    info_str = f"Último: {nome_ult} (Saiu {total_ocorrencias}x no passado)"
    return imas, repelidos, info_str

def analisar_sequencias_profundas_com_moda(lista_wins):
    if not lista_wins: return 0, 0, 0, 0, 0
    sequencias = []
    atual = 0
    for w in lista_wins:
        if w: atual += 1
        else:
            if atual > 0: sequencias.append(atual)
            atual = 0
    if atual > 0: sequencias.append(atual)
    if not sequencias: return 0, 0, 0, 0, 0
    maximo = max(sequencias)
    ocorrencias_max = sequencias.count(maximo)
    total_ops = len(lista_wins)
    ciclo = int(total_ops / ocorrencias_max) if ocorrencias_max > 0 else 0
    c = Counter(sequencias)
    moda_dados = c.most_common(1)[0]
    moda_valor = moda_dados[0]
    moda_freq = moda_dados[1]
    total_seqs = len(sequencias)
    moda_porc = (moda_freq / total_seqs) * 100
    return maximo, ocorrencias_max, ciclo, moda_valor, moda_porc

def treinar_probabilidade_global(historico, indice_premio):
    if not HAS_AI or len(historico) < 30: return {f"{i:02}": 0.01 for i in range(100)} 
    
    datas = []; horas = []; targets = []
    for row in historico:
        try: 
            dt = pd.to_datetime(row['data'], format='%Y-%m-%d', errors='coerce')
            if pd.isna(dt): continue
            datas.append(dt)
            horas.append(row['horario'])
            targets.append(str(row['premios'][indice_premio]).zfill(2))
        except: pass
        
    if len(datas) < 30: return {f"{i:02}": 0.01 for i in range(100)} 
    
    df = pd.DataFrame({'data_dt': datas, 'horario': horas, 'target': targets})
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['horario'])
    
    df['target_futuro'] = df['target'].shift(-1)
    df_treino = df.dropna(subset=['target_futuro']).tail(150)
    
    if len(df_treino) < 20: return {f"{i:02}": 0.01 for i in range(100)} 
    
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro'].astype(str)
    
    modelo = RandomForestClassifier(n_estimators=60, random_state=42)
    modelo.fit(X, y)
    
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    
    mapa_probs = {c: 0.01 for c in [f"{i:02}" for i in range(100)]}
    for i, prob in enumerate(probs):
        chave = str(classes[i]).zfill(2)
        mapa_probs[chave] = prob
    return mapa_probs

def rankear_grupos(mapa_probs):
    score_grupos = {g: 0.0 for g in range(1, 26)}
    for g in range(1, 26):
        dezenas = list(GRUPO_TO_DEZENAS[g])
        for d in dezenas: score_grupos[g] += mapa_probs.get(d, 0.0)
    return sorted(score_grupos.items(), key=lambda x: x[1], reverse=True)

# LÓGICA REFINADA PARA 46 DEZENAS E ÍMÃS FORÇADOS
def gerar_estrategia_oracle_46(historico, indice_premio):
    if not historico: return [], 0, {}, {}
    mapa_ia = treinar_probabilidade_global(historico, indice_premio)
    ranking_grupos = rankear_grupos(mapa_ia)
    grupos_ima, grupos_repelidos, info_oracle = analisar_efeito_ima(historico, indice_premio)
    
    ranking_final = []
    grupos_ima_selecionados = grupos_ima[:3] # Pega até 3 Ímãs
    grupos_ima_set = set(grupos_ima_selecionados)
    grupos_rep_set = set(grupos_repelidos[:5]) # Pega os piores repelidos
    
    for g, score in ranking_grupos:
        score_final = score
        if g in grupos_ima_set: score_final += 2.0 
        if g in grupos_rep_set: score_final = -999.0 
        ranking_final.append((g, score_final))
        
    ranking_final.sort(key=lambda x: x[1], reverse=True)
    
    palpite_set = set()
    
    # PASSO 1: FORÇA TOTAL NOS ÍMÃS (Coloca as 4 dezenas de cada)
    for g in grupos_ima_selecionados:
        dezenas_g = GRUPO_TO_DEZENAS[g].copy()
        palpite_set.update(dezenas_g)
        
    # PASSO 2: FILTRAR OS RESTANTES 
    # Tira os ímãs da lista para não duplicar, os repelidos ficam no fim com score -999
    remaining_ranked = [g for g, s in ranking_final if g not in grupos_ima_set]
    
    # PASSO 3: PREENCHER ATÉ 46 DEZENAS EXATAS
    idx = 0
    while len(palpite_set) < 46 and idx < len(remaining_ranked):
        g = remaining_ranked[idx]
        dezenas_g = GRUPO_TO_DEZENAS[g].copy()
        # Ordena as dezenas dentro deste grupo da melhor para a pior
        dezenas_g.sort(key=lambda d: mapa_ia.get(d, 0), reverse=True)
        
        # Estratégia de Injeção: Top 8 levam 3 dezenas, os demais levam 2 dezenas.
        adicionar = 3 if idx < 8 else 2
        
        # Trava de Segurança: Não ultrapassar 46 dezenas no total
        falta = 46 - len(palpite_set)
        if adicionar > falta:
            adicionar = falta
            
        for d in dezenas_g[:adicionar]:
            palpite_set.add(d)
            
        idx += 1
        
    palpite_matrix = list(palpite_set)
    palpite_matrix.sort()
    
    # Identificar quem ficou de fora (Abatidos)
    grupos_utilizados = set()
    for d in palpite_matrix:
        grupos_utilizados.add(get_grupo(int(d)))
        
    abate = [g for g in range(1, 26) if g not in grupos_utilizados]
    
    prob_total = sum([mapa_ia.get(d, 0.01) for d in palpite_matrix])
    conf_media = prob_total * 100 
    if conf_media < 1.0: conf_media = 50.0
    if conf_media > 99.9: conf_media = 99.9
    
    info_predator = { "elite": grupos_ima_selecionados, "abate": abate }
    dados_oracle = { "info": info_oracle, "imas": grupos_ima_selecionados, "repelidos": grupos_repelidos[:5] }
    
    return palpite_matrix, conf_media, info_predator, dados_oracle

def treinar_oraculo_unidades(historico, indice_premio):
    if not HAS_AI or len(historico) < 30: return [], 0
    datas = []; horas = []; targets = []
    for row in historico:
        try: 
            dt = pd.to_datetime(row['data'], format='%Y-%m-%d', errors='coerce')
            if pd.isna(dt): continue
            datas.append(dt)
            horas.append(row['horario'])
            targets.append(int(str(row['premios'][indice_premio])[-1]))
        except: pass
    if len(datas) < 30: return [], 0
    df = pd.DataFrame({'data_dt': datas, 'horario': horas, 'target': targets})
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['horario'])
    df['target_futuro'] = df['target'].shift(-1)
    df_treino = df.dropna(subset=['target_futuro']).tail(150)
    if len(df_treino) < 20: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target']]
    y = df_treino['target_futuro']
    
    modelo = RandomForestClassifier(n_estimators=50, random_state=42)
    modelo.fit(X, y)
    
    ultimo = df.iloc[-1]
    X_novo = pd.DataFrame({'dia_semana': [ultimo['dia_semana']], 'hora_code': [ultimo['hora_code']], 'target': [ultimo['target']]})
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking = []
    for i, prob in enumerate(probs): ranking.append((int(classes[i]), prob))
    ranking.sort(key=lambda x: x[1], reverse=True)
    return ranking, (ranking[0][1] * 100)

# =============================================================================
# --- 4. BACKTESTS ---
# =============================================================================

def analisar_padrao_futuro(lista_wins):
    if not lista_wins or len(lista_wins) < 10: return 0, 0, False
    streak_atual = 0; eh_vitoria = lista_wins[-1]
    for w in reversed(lista_wins):
        if w == eh_vitoria: streak_atual += 1
        else: break
    ocorrencias_total = 0; proxima_foi_win = 0; i = 0
    while i < len(lista_wins) - streak_atual:
        match = True
        for k in range(streak_atual):
            if lista_wins[i+k] != eh_vitoria:
                match = False; break
        if match:
            if i > 0 and lista_wins[i-1] == eh_vitoria: pass 
            idx_pos = i + streak_atual
            if idx_pos < len(lista_wins):
                ocorrencias_total += 1
                if lista_wins[idx_pos] == True: proxima_foi_win += 1
        i += 1
    if ocorrencias_total == 0: return 0, 0, eh_vitoria
    probabilidade_win = (proxima_foi_win / ocorrencias_total) * 100
    return probabilidade_win, ocorrencias_total, eh_vitoria

def calcular_metricas_oracle_detalhado(historico, indice_premio):
    if len(historico) < 20: return {}, {}, 0, 0, False
    total = len(historico); inicio = max(20, total - 50)
    historico_wins = []
    for i in range(inicio, total):
        target = historico[i]['premios'][indice_premio]
        hist_p = historico[:i]
        palpite, _, _, _ = gerar_estrategia_oracle_46(hist_p, indice_premio)
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
                
    max_w, count_w, ciclo_w, moda_w, porc_w = analisar_sequencias_profundas_com_moda([x for x in historico_wins])
    max_l, count_l, ciclo_l, moda_l, porc_l = analisar_sequencias_profundas_com_moda([not x for x in historico_wins])
    prob_win_futura, amostra, em_streak_vitoria = analisar_padrao_futuro(historico_wins)
    
    stats_loss = { 
        "atual": seq_atual_loss, 
        "max": max_l, 
        "freq": count_l, 
        "ciclo": ciclo_l,
        "moda": moda_l,
        "moda_porc": porc_l
    }
    stats_win = { 
        "atual": seq_atual_win, 
        "max": max_w, 
        "freq": count_w, 
        "ciclo": ciclo_w,
        "moda": moda_w,
        "moda_porc": porc_w
    }
    return stats_loss, stats_win, prob_win_futura, amostra, em_streak_vitoria

def calcular_metricas_unidades_detalhado(historico, indice_premio):
    if len(historico) < 30: return {}, {}
    total = len(historico); inicio = max(30, total - 50)
    historico_wins = []
    streak_no_momento = 0
    for i in range(inicio, total):
        target = int(historico[i]['premios'][indice_premio][-1])
        hist_parcial = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_parcial, indice_premio)
        if streak_no_momento >= 2: palpite = [u for u, p in rank[:7]]
        else: palpite = [u for u, p in rank[:5]]
        if target in palpite:
            historico_wins.append(True); streak_no_momento = 0
        else:
            historico_wins.append(False); streak_no_momento += 1
    seq_atual_loss = streak_no_momento; seq_atual_win = 0
    if historico_wins and historico_wins[-1]:
        for w in reversed(historico_wins):
            if w: seq_atual_win += 1
            else: break
    max_w, count_w, ciclo_w, moda_w, porc_w = analisar_sequencias_profundas_com_moda([x for x in historico_wins])
    max_l, count_l, ciclo_l, moda_l, porc_l = analisar_sequencias_profundas_com_moda([not x for x in historico_wins])
    stats_loss = { "atual": seq_atual_loss, "max": max_l, "freq": count_l, "ciclo": ciclo_l, "moda": moda_l, "moda_porc": porc_l }
    stats_win = { "atual": seq_atual_win, "max": max_w, "freq": count_w, "ciclo": ciclo_w, "moda": moda_w, "moda_porc": porc_w }
    return stats_loss, stats_win

def executar_backtest_recente_oracle(historico, indice_premio):
    results = []
    for i in range(1, 6):
        idx = -i
        target = historico[idx]['premios'][indice_premio]
        palp, _, _, _ = gerar_estrategia_oracle_46(historico[:idx], indice_premio)
        win = target in palp
        results.append({"val": target, "win": win})
    return results

def executar_backtest_recente_uni_preciso(historico, indice_premio):
    total = len(historico); start = max(30, total - 60)
    streak_no_momento = 0; resultados_reais = []
    for i in range(start, total):
        target = int(historico[i]['premios'][indice_premio][-1])
        hist_parcial = historico[:i]
        rank, _ = treinar_oraculo_unidades(hist_parcial, indice_premio)
        is_defense = False
        if streak_no_momento >= 2: palpite = [u for u, p in rank[:7]]; is_defense = True
        else: palpite = [u for u, p in rank[:5]]
        win = target in palpite
        if i >= total - 5:
            modo_str = "🛡️(7)" if is_defense else "⚔️(5)"
            resultados_reais.append({ "val": f"Final {target}", "win": win, "modo": modo_str })
        if win: streak_no_momento = 0
        else: streak_no_momento += 1
    return reversed(resultados_reais)

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
# --- 5. INTERFACE ---
# =============================================================================

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
            if lista_final:
                ws.append_rows(lista_final)
            return f"Sucesso! Reduzido de {len(raw)-1} para {len(lista_final)} registros."
        except Exception as e: return f"Erro: {e}"
    return "Erro Conexão"

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    st.title("🛡️ PENTÁGONO - PRECISION 46")
    col1, col2 = st.columns(2)
    col1.metric("Matriz", "46 Dezenas Exatas")
    col2.metric("Regra", "Ímãs com 4 Dezenas Forçadas")
    st.info("Sistema agora foca em 46 dezenas, extraindo 100% da força dos grupos Ímãs e aniquilando os Repelidos.")

else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🧹 EXECUTAR FAXINA NO BANCO DE DADOS"):
        with st.spinner("Limpando e reescrevendo planilha..."):
            res = acao_limpar_banco(config['nome_aba'])
            if "Sucesso" in res: st.sidebar.success(res)
            else: st.sidebar.error(res)
            time.sleep(2)
            st.rerun()
            
    st.sidebar.markdown("---")
    
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)"])
    
    if modo_extracao == "🎯 Unitária":
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.sidebar.date_input("Escolha:", date.today())
            horario_busca = st.selectbox("Horário:", config['horarios'])
            if st.button("🚀 Baixar & Salvar"):
                ws = conectar_planilha(config['nome_aba'])
                if ws:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try: 
                            existentes = ws.get_all_values()
                            chaves = []
                            for row in existentes:
                                if len(row) >= 2:
                                    d = normalizar_data(row[0])
                                    h = normalizar_hora(row[1])
                                    if d: chaves.append(f"{d.strftime('%Y-%m-%d')}|{h}")
                        except: chaves = []
                        
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe!")
                        else:
                            premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                            if premios:
                                row = [data_busca.strftime('%Y-%m-%d'), horario_busca] + premios
                                ws.append_row(row); st.toast(f"Sucesso! {premios}", icon="✅"); time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro Planilha")
                
    else: 
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        if st.sidebar.button("🚀 INICIAR TURBO"):
            ws = conectar_planilha(config['nome_aba'])
            if ws:
                status = st.sidebar.empty(); bar = st.sidebar.progress(0)
                try: 
                    existentes = ws.get_all_values()
                    chaves = []
                    for row in existentes:
                        if len(row) >= 2:
                            d = normalizar_data(row[0])
                            h = normalizar_hora(row[1])
                            if d: chaves.append(f"{d.strftime('%Y-%m-%d')}|{h}")
                except: chaves = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config['horarios']); op_atual = 0; sucessos = 0
                for dia in lista_datas:
                    for hora in config['horarios']:
                        op_atual += 1; 
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{normalizar_hora(hora)}"
                        if chave_atual in chaves: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue
                        premios, msg = raspar_dados_hibrido(banca_selecionada, dia, hora)
                        if premios:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + premios); sucessos += 1; chaves.append(chave_atual)
                        time.sleep(1.0)
                bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos."); time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão")

    # --- PÁGINA DA BANCA ---
    st.header(f"🔭 {config['display_name']} - Oracle 46")
    
    with st.spinner("Carregando e Limpando dados..."):
        historico = carregar_dados_hibridos(config['nome_aba'])

    if len(historico) > 0:
        ult = historico[-1]
        if config['tipo'] == "SOLO": st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **1º Prêmio:** {ult['premios'][0]}")
        else: st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **P1:** {ult['premios'][0]} ... **P5:** {ult['premios'][4]}")
        
        range_abas = [0, 1] if config['tipo'] == "SOLO" else range(5)
        abas = st.tabs(["🔮 Oracle 46", "🎯 Unidades"] if config['tipo'] == "SOLO" else [f"{i+1}º Prêmio" for i in range(5)])
        
        for idx_aba in range_abas:
            with abas[idx_aba]:
                if config['tipo'] == "SOLO" and idx_aba == 1:
                    rank_uni, conf_uni = treinar_oraculo_unidades(historico, 0)
                    stats_loss_u, stats_win_u = calcular_metricas_unidades_detalhado(historico, 0)
                    top_base = [str(u) for u, p in rank_uni[:5]]
                    if stats_loss_u['atual'] >= 2: st.error(f"🛡️ MODO DEFESA (Top 7)")
                    else: st.info("⚔️ MODO ATAQUE (Top 5)")
                    with st.container(border=True): st.markdown(f"### Finais: {', '.join(top_base)}")
                    c3, c4 = st.columns(2)
                    c3.metric("Derrotas", f"{stats_loss_u['atual']}", f"Rec: {stats_loss_u['max']} | Padrão: {stats_loss_u['moda']} ({stats_loss_u['moda_porc']:.0f}%)", delta_color="inverse")
                    c4.metric("Vitórias", f"{stats_win_u['atual']}", f"Rec: {stats_win_u['max']} | Padrão: {stats_win_u['moda']} ({stats_win_u['moda_porc']:.0f}%)")
                    bt_uni = executar_backtest_recente_uni_preciso(historico, 0)
                    cols_bt_u = st.columns(5)
                    for i, res in enumerate(bt_uni):
                        with cols_bt_u[i]:
                            st.caption(res['modo']); 
                            if res['win']: st.success(res['val'])
                            else: st.error(res['val'])
                else:
                    lista_matrix, conf_total, info_predator, dados_oracle = gerar_estrategia_oracle_46(historico, idx_aba)
                    stats_loss, stats_win, prob_win_futura, amostra, em_streak_vitoria = calcular_metricas_oracle_detalhado(historico, idx_aba)
                    if HAS_AI:
                        st.info(f"🔮 {dados_oracle['info']}")
                        c_ima, c_rep = st.columns(2)
                        with c_ima: st.success(f"🧲 **ÍMÃS:** {dados_oracle['imas']}")
                        with c_rep: st.error(f"⛔ **REPELIDOS:** {dados_oracle['repelidos']}")
                        st.markdown("---")
                        st.markdown(f"### 📊 Análise de Padrão (Histórico de {amostra} casos)")
                        col_prob, col_msg = st.columns([1, 3])
                        col_prob.metric("Chance Próximo Win", f"{prob_win_futura:.1f}%")
                        if prob_win_futura >= 80:
                            if em_streak_vitoria: col_msg.success(f"💎 **DIAMANTE (SURFER)!** Tendência forte de CONTINUAR ganhando.")
                            else: col_msg.success(f"💎 **DIAMANTE (SNIPER)!** Tendência forte de REVERTER derrota.")
                        elif prob_win_futura <= 40: col_msg.error("🛑 **NÃO JOGUE.** Probabilidade baixa.")
                        else: col_msg.warning("⚠️ **NEUTRO.** Mercado indefinido.")
                    with st.container(border=True):
                        st.code(", ".join(lista_matrix), language="text")
                    c1, c2 = st.columns(2)
                    c1.metric("Derrotas", f"{stats_loss['atual']}", f"Rec: {stats_loss['max']} | Padrão: {stats_loss['moda']} ({stats_loss['moda_porc']:.0f}%)", delta_color="inverse")
                    c2.metric("Vitórias", f"{stats_win['atual']}", f"Rec: {stats_win['max']} | Padrão: {stats_win['moda']} ({stats_win['moda_porc']:.0f}%)")
                    bt_dez = executar_backtest_recente_oracle(historico, idx_aba)
                    cols_bt = st.columns(5)
                    for i, res in enumerate(reversed(bt_dez)):
                        with cols_bt[i]:
                            if res['win']: st.success(res['val'])
                            else: st.error(res['val'])
                    lbl, padroes = rastreador_padroes(historico, idx_aba)
                    if padroes:
                        st.caption(f"Padrões após {lbl}:")
                        st.table(pd.DataFrame(padroes))

    else:
        st.warning("⚠️ Base vazia.")
