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
st.set_page_config(page_title="PENTÁGONO V73.0 Radar Avançado", page_icon="👑", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (Dezenas)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "tipo": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    "TRADICIONAL_MILHAR": { "display_name": "👑 TRADICIONAL (Vitorino)", "nome_aba": "TRADICIONAL_MILHAR", "slug": "loteria-tradicional", "tipo": "MILHAR_VIEW", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "base_dez": "BASE_TRADICIONAL_DEZ" },
    
    "LOTEP": { "display_name": "LOTEP (Dezenas)", "nome_aba": "LOTEP_TOP5", "slug": "lotep", "tipo": "DUAL_PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "LOTEP_MILHAR": { "display_name": "👑 LOTEP (Vitorino)", "nome_aba": "LOTEP_MILHAR", "slug": "lotep", "tipo": "MILHAR_VIEW", "horarios": ["10:45", "12:45", "15:45", "18:00"], "base_dez": "LOTEP_TOP5" },
    
    "CAMINHO": { "display_name": "CAMINHO (Dezenas)", "nome_aba": "CAMINHO_TOP5", "slug": "caminho-da-sorte", "tipo": "DUAL_PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "CAMINHO_MILHAR": { "display_name": "👑 CAMINHO (Vitorino)", "nome_aba": "CAMINHO_MILHAR", "slug": "caminho-da-sorte", "tipo": "MILHAR_VIEW", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"], "base_dez": "CAMINHO_TOP5" },
    
    "MONTE": { "display_name": "MONTE CARLOS (Dezenas)", "nome_aba": "MONTE_TOP5", "slug": "nordeste-monte-carlos", "tipo": "DUAL_PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] },
    "MONTE_MILHAR": { "display_name": "👑 MONTE CARLOS (Vitorino)", "nome_aba": "MONTE_MILHAR", "slug": "nordeste-monte-carlos", "tipo": "MILHAR_VIEW", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"], "base_dez": "MONTE_TOP5" }
}

GRUPO_TO_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
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
    h1, h2, h3 { color: #ffd700 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #00ff00; }
    .css-1wivap2 { font-size: 14px !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (DUAL ENGINE + BATCHING) ---
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
                        
                        if normalizar_hora(h_detect) == normalizar_hora(horario_alvo):
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
                                        limite = 5 if config['tipo'] in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW", "PENTA"] else 1
                                        if 1 <= p_idx <= limite:
                                            clean_num = re.sub(r'\D', '', numero_txt)
                                            if len(clean_num) >= 2: 
                                                if config['tipo'] in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]:
                                                    dezenas_encontradas.append(clean_num[-4:].zfill(4))
                                                else:
                                                    dezenas_encontradas.append(clean_num[-2:])
                                                    
                            if config['tipo'] in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]:
                                if len(dezenas_encontradas) >= 1: 
                                    res = dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas))
                                    return res[:5], "Sucesso"
                            else:
                                if config['tipo'] == "SOLO" and len(dezenas_encontradas) >= 1: return [dezenas_encontradas[0], "00", "00", "00", "00"], "Sucesso"
                                elif len(dezenas_encontradas) >= 5: return dezenas_encontradas[:5], "Sucesso"
                            return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: IA ORACLE + CHASER ENGINE ---
# =============================================================================

def get_grupo(dezena):
    try:
        d = int(str(dezena)[-2:])
        if d == 0: return 25
        if d > 99: return 25 
        val = (d - 1) // 4 + 1
        return val
    except: return 1

def analisar_efeito_ima(historico, indice_premio):
    if len(historico) < 10: return [], [], "Dados Insuficientes"
    try:
        ult_dezena = str(historico[-1]['premios'][indice_premio])[-2:]
        ult_grupo = get_grupo(ult_dezena)
        nome_ult = NOME_BICHOS.get(ult_grupo, str(ult_grupo))
    except: return [], [], "Erro Leitura"
    contagem_seguinte = Counter()
    total_ocorrencias = 0
    for i in range(len(historico) - 1):
        try:
            d_atual = str(historico[i]['premios'][indice_premio])[-2:]
            g_atual = get_grupo(d_atual)
            if g_atual == ult_grupo:
                d_prox = str(historico[i+1]['premios'][indice_premio])[-2:]
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
            targets.append(str(row['premios'][indice_premio])[-2:].zfill(2))
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

def gerar_estrategia_oracle_46(historico, indice_premio):
    if not historico: return [], 0, {}, {}
    mapa_ia = treinar_probabilidade_global(historico, indice_premio)
    ranking_grupos = rankear_grupos(mapa_ia)
    grupos_ima, grupos_repelidos, info_oracle = analisar_efeito_ima(historico, indice_premio)
    ranking_final = []
    grupos_ima_selecionados = grupos_ima[:3]
    grupos_ima_set = set(grupos_ima_selecionados)
    grupos_rep_set = set(grupos_repelidos[:5])
    for g, score in ranking_grupos:
        score_final = score
        if g in grupos_ima_set: score_final += 2.0 
        if g in grupos_rep_set: score_final = -999.0 
        ranking_final.append((g, score_final))
    ranking_final.sort(key=lambda x: x[1], reverse=True)
    palpite_set = set()
    for g in grupos_ima_selecionados:
        dezenas_g = GRUPO_TO_DEZENAS[g].copy()
        palpite_set.update(dezenas_g)
    remaining_ranked = [g for g, s in ranking_final if g not in grupos_ima_set]
    idx = 0
    while len(palpite_set) < 46 and idx < len(remaining_ranked):
        g = remaining_ranked[idx]
        dezenas_g = GRUPO_TO_DEZENAS[g].copy()
        dezenas_g.sort(key=lambda d: mapa_ia.get(d, 0), reverse=True)
        adicionar = 3 if idx < 8 else 2
        falta = 46 - len(palpite_set)
        if adicionar > falta: adicionar = falta
        for d in dezenas_g[:adicionar]: palpite_set.add(d)
        idx += 1
    palpite_matrix = list(palpite_set)
    palpite_matrix.sort()
    grupos_utilizados = set()
    for d in palpite_matrix: grupos_utilizados.add(get_grupo(int(d)))
    abate = [g for g in range(1, 26) if g not in grupos_utilizados]
    prob_total = sum([mapa_ia.get(d, 0.01) for d in palpite_matrix])
    conf_media = prob_total * 100 
    if conf_media < 1.0: conf_media = 50.0
    if conf_media > 99.9: conf_media = 99.9
    info_predator = { "elite": grupos_ima_selecionados, "abate": abate }
    dados_oracle = { "info": info_oracle, "imas": grupos_ima_selecionados, "repelidos": grupos_repelidos[:5] }
    return palpite_matrix, conf_media, info_predator, dados_oracle

def rastrear_estado_chaser(historico, indice_premio=0):
    unidades = []
    for row in historico:
        try:
            dezena = str(row['premios'][indice_premio]).zfill(2)
            if dezena != "00": unidades.append(int(dezena[-1]))
        except: pass
    if len(unidades) < 50: return {"status": "inativo", "target": None, "attempts": 0, "prob": 0, "occ": 0}
    def calc_best(hist_slice):
        gatilho = hist_slice[-1]
        sucessos = {u: 0 for u in range(10)}
        ocorrencias = 0
        for i in range(len(hist_slice) - 1):
            if hist_slice[i] == gatilho:
                janela = hist_slice[i+1 : i+9]
                if not janela: continue
                ocorrencias += 1
                for u in set(janela): sucessos[u] += 1
        if ocorrencias == 0: return None, 0, 0
        rank = [(u, (sucessos[u]/ocorrencias)*100) for u in range(10)]
        rank.sort(key=lambda x: x[1], reverse=True)
        return rank[0][0], rank[0][1], ocorrencias
    start_idx = max(50, len(unidades) - 100)
    chase_active = False
    target_unit = None
    attempts_made = 0
    ouro_prob_saved = 0
    occ_saved = 0
    for i in range(start_idx, len(unidades)):
        current_unit = unidades[i]
        if chase_active:
            attempts_made += 1
            if current_unit == target_unit: chase_active = False 
            elif attempts_made >= 8: chase_active = False 
        else:
            best_u, best_prob, occ = calc_best(unidades[:i])
            if best_u is not None:
                chase_active = True
                target_unit = best_u
                attempts_made = 1
                ouro_prob_saved = best_prob
                occ_saved = occ
                if current_unit == target_unit: chase_active = False 
    if chase_active:
        return {"status": "ativo", "target": target_unit, "attempts": attempts_made, "prob": ouro_prob_saved, "occ": occ_saved}
    else:
        best_u, best_prob, occ = calc_best(unidades)
        return {"status": "novo", "target": best_u, "attempts": 0, "prob": best_prob, "occ": occ}

def rastrear_estado_chaser_dezenas(historico, indice_premio=0):
    dezenas = []
    for row in historico:
        try:
            d = str(row['premios'][indice_premio])[-2:].zfill(2)
            dezenas.append(d)
        except: pass
    if len(dezenas) < 50: return {"status": "inativo", "target": [], "attempts": 0, "prob": 0, "occ": 0}
    def calc_best_10(hist_slice):
        gatilho = hist_slice[-1]
        sucessos = Counter()
        ocorrencias = 0
        for i in range(len(hist_slice) - 1):
            if hist_slice[i] == gatilho:
                janela = hist_slice[i+1 : i+9]
                if not janela: continue
                ocorrencias += 1
                for d in set(janela): sucessos[d] += 1
        if ocorrencias == 0: return [], 0, 0
        top_10 = [x[0] for x in sucessos.most_common(10)]
        hit_windows = 0
        for i in range(len(hist_slice) - 1):
            if hist_slice[i] == gatilho:
                janela = set(hist_slice[i+1 : i+9])
                if any(d in janela for d in top_10): hit_windows += 1
        prob = (hit_windows / ocorrencias) * 100 if ocorrencias > 0 else 0
        return top_10, prob, ocorrencias
    start_idx = max(50, len(dezenas) - 100)
    chase_active = False
    target_10 = []
    attempts_made = 0
    saved_prob = 0
    saved_occ = 0
    for i in range(start_idx, len(dezenas)):
        curr = dezenas[i]
        if chase_active:
            attempts_made += 1
            if curr in target_10: chase_active = False 
            elif attempts_made >= 8: chase_active = False 
        else:
            t10, prob, occ = calc_best_10(dezenas[:i])
            if t10:
                chase_active = True
                target_10 = t10
                attempts_made = 1
                saved_prob = prob
                saved_occ = occ
                if curr in target_10: chase_active = False 
    if chase_active:
        return {"status": "ativo", "target": target_10, "attempts": attempts_made, "prob": saved_prob, "occ": saved_occ}
    else:
        t10, prob, occ = calc_best_10(dezenas)
        return {"status": "novo", "target": t10, "attempts": 0, "prob": prob, "occ": occ}


def calcular_3_estrategias_unidade(historico, indice_premio=0):
    unidades = []
    for row in historico:
        try: unidades.append(int(str(row['premios'][indice_premio]).zfill(2)[-1]))
        except: pass
    if not unidades: return "-", "-", "-"
    gatilho = unidades[-1]
    sucessos = Counter()
    for i in range(len(unidades)-1):
        if unidades[i] == gatilho:
            janela = set(unidades[i+1:i+9])
            for u in janela: sucessos[u] += 1
    markov_u = sucessos.most_common(1)[0][0] if sucessos else "-"
    ultimas_posicoes = {}
    for i, u in enumerate(unidades): ultimas_posicoes[u] = i
    atrasada_u = "-"
    min_idx = float('inf')
    for u in range(10):
        if u not in ultimas_posicoes:
            atrasada_u = u; break
        elif ultimas_posicoes[u] < min_idx:
            min_idx = ultimas_posicoes[u]; atrasada_u = u
    recentes = unidades[-15:] if len(unidades) >= 15 else unidades
    quente_u = Counter(recentes).most_common(1)[0][0] if recentes else "-"
    return markov_u, atrasada_u, quente_u


# =============================================================================
# --- 4. MÓDULOS VITORINO (MILHAR & CENTENA INVERTIDA) ---
# =============================================================================

def gerar_estrategia_vitorino(hist_milhar, hist_dezena):
    if len(hist_dezena) < 30 or len(hist_milhar) < 10:
        return [], []
    mapa_probs = treinar_probabilidade_global(hist_dezena, 0)
    ranking = sorted(mapa_probs.items(), key=lambda x: x[1], reverse=True)
    top_3_dezenas = [x[0] for x in ranking[:3]]
    
    ultimo_sorteio_premios = hist_milhar[-1]['premios']
    todos_digitos_ultimo = "".join([str(p).zfill(4) for p in ultimo_sorteio_premios if str(p) != "0000"])
    digitos_ocultos = [str(d) for d in range(10) if str(d) not in todos_digitos_ultimo]
    
    if not digitos_ocultos:
        contagem = Counter(todos_digitos_ultimo)
        menor_freq = min(contagem.values())
        digitos_ocultos = [str(d) for d, f in contagem.items() if f == menor_freq]
        digitos_ocultos.sort()
        msg_radar = f"🎲 **Radar Vitorino (Modo Escassez):** Todos os dígitos saíram no último sorteio! O sistema caçou os mais fracos (que só apareceram {menor_freq}x) para formar a nova Coroa: `{', '.join(digitos_ocultos)}`."
    else:
        digitos_ocultos.sort()
        msg_radar = f"🔍 **Radar Vitorino (Modo Ausência):** Os dígitos `{', '.join(digitos_ocultos)}` não apareceram no último sorteio. Eles serão a Coroa da próxima Milhar."
    
    milhares_vitorino = []
    detalhes = []
    for i, dezena in enumerate(top_3_dezenas):
        coroa = digitos_ocultos[i % len(digitos_ocultos)]
        centenas_aliadas = []
        for r in hist_milhar:
            for p in r['premios']:
                m_str = str(p).zfill(4)
                if m_str[-2:] == dezena and m_str != "0000":
                    centenas_aliadas.append(m_str[1]) 
        if not centenas_aliadas: corpo = "0"
        else: corpo = Counter(centenas_aliadas).most_common(1)[0][0]
        milhar_final = f"{coroa}{corpo}{dezena}"
        milhares_vitorino.append(milhar_final)
        detalhes.append({ "dezena": dezena, "corpo": corpo, "coroa": coroa, "msg_radar": msg_radar })
    return milhares_vitorino, detalhes

def gerar_esquadrao_8_digitos(hist_centenas):
    if not hist_centenas: return [str(x) for x in range(8)]
    ult_centena = hist_centenas[-1]
    
    ult_digitos_set = set(ult_centena)
    markov_c = Counter()
    for i in range(len(hist_centenas) - 1):
        if any(d in hist_centenas[i] for d in ult_digitos_set):
            for d_next in hist_centenas[i+1]: markov_c[d_next] += 1
    rank_markov = [x[0] for x in markov_c.most_common()]
    
    last_seen = {}
    for i, c in enumerate(hist_centenas):
        for d in c: last_seen[d] = i
    rank_atrasados = sorted([str(d) for d in range(10)], key=lambda x: last_seen.get(x, -1))
    
    recentes = "".join(hist_centenas[-15:])
    rank_quentes = [x[0] for x in Counter(recentes).most_common()]
    
    esquadrao = []
    for d in rank_markov:
        if d not in esquadrao and len(esquadrao) < 3: esquadrao.append(d)
    for d in rank_atrasados:
        if d not in esquadrao and len(esquadrao) < 6: esquadrao.append(d)
    for d in rank_quentes:
        if d not in esquadrao and len(esquadrao) < 8: esquadrao.append(d)
    for d in [str(x) for x in range(10)]:
        if d not in esquadrao and len(esquadrao) < 8: esquadrao.append(d)
        
    esquadrao.sort()
    return esquadrao

def calcular_radar_invertidas(hist_milhar):
    if len(hist_milhar) < 30: return []
    resultados_radar = []
    
    for p_idx in range(5):
        centenas_do_premio = []
        for row in hist_milhar:
            try:
                m = str(row['premios'][p_idx]).zfill(4)
                if m != "0000": centenas_do_premio.append(m[-3:])
            except: pass
            
        if len(centenas_do_premio) < 30: continue
            
        ult_centena = centenas_do_premio[-1]
        penult_centena = centenas_do_premio[-2]
        
        rep_ult = len(set(ult_centena)) < 3
        rep_penult = len(set(penult_centena)) < 3
        
        # Detector de Alvo
        if rep_ult and rep_penult:
            status = "🚨 SNIPER MÁXIMO"
            cor = "error"
            alerta = "Bote agora! Vieram 2 centenas repetidas seguidas."
        elif rep_ult:
            status = "🔥 ALVO QUENTE"
            cor = "warning"
            alerta = "Atenção! A última centena veio com repetição."
        else:
            status = "⏸️ Neutro"
            cor = "info"
            alerta = "A última centena foi normal."
            
        # NOVA MÉTRICA: Max Sequência Repetidas (Últimos 25 Jogos)
        ultimas_25 = centenas_do_premio[-25:]
        max_seq = 0
        seq_atual = 0
        for c in ultimas_25:
            if len(set(c)) < 3: # É uma centena repetida
                seq_atual += 1
                if seq_atual > max_seq: max_seq = seq_atual
            else:
                seq_atual = 0 # Zerou a sequência
                
        # Gera o esquadrão atual para o próximo sorteio
        esquadrao_atual = gerar_esquadrao_8_digitos(centenas_do_premio)
        
        # BACKTEST (AGORA OS ÚLTIMOS 6 SORTEIOS)
        backtest_placar = []
        for i in range(6, 0, -1):
            hist_corte = centenas_do_premio[:-i] 
            alvo_real = centenas_do_premio[-i]   
            esquadrao_simulado = gerar_esquadrao_8_digitos(hist_corte)
            
            if len(set(alvo_real)) < 3: backtest_placar.append("❌")
            else:
                if all(d in esquadrao_simulado for d in alvo_real): backtest_placar.append("✅")
                else: backtest_placar.append("❌")
        
        resultados_radar.append({
            "premio": p_idx + 1,
            "status": status,
            "cor": cor,
            "alerta": alerta,
            "ult_centena": ult_centena,
            "esquadrao": esquadrao_atual,
            "backtest": backtest_placar,
            "max_seq_rep": max_seq
        })
    return resultados_radar


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
            if lista_final: ws.append_rows(lista_final)
            return f"Sucesso! Reduzido de {len(raw)-1} para {len(lista_final)} registros."
        except Exception as e: return f"Erro: {e}"
    return "Erro Conexão"

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    st.title("🛡️ PENTÁGONO - RADAR AVANÇADO")
    col1, col2 = st.columns(2)
    col1.metric("Bancas Sincronizadas", "TODAS AS BANCAS (100%)")
    col2.metric("Inteligência Tática", "Tracker de Anomalias Ativo")
    st.info("Sistema atualizado: Adicionado rastreador de Limite de Repetição (Max 25 Jogos) e Backtest estendido para 6 jogos. Informação máxima para caçar as Invertidas.")

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
    
    if config['tipo'] == "MILHAR_VIEW":
        nome_aba_extracao = banca_selecionada.replace("_MILHAR", "")
        st.sidebar.info(f"⚠️ **Aviso:** A extração de milhares é feita na aba '{CONFIG_BANCAS.get(nome_aba_extracao, {}).get('display_name', 'Principal')}'.")
    else:
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
                                chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                            except: chaves = []
                            chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                            if chave_atual in chaves: st.warning("Resultado já existe na aba principal!")
                            else:
                                premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                                if premios:
                                    if config['tipo'] == "DUAL_SOLO":
                                        row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca, premios[0][-2:], "00", "00", "00", "00"]
                                        ws.append_row(row_dez)
                                        ws_milhar = conectar_planilha(f"{banca_selecionada}_MILHAR")
                                        if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                        st.toast(f"Duplo Sucesso! Dezena e Milhar salvas.", icon="✅")
                                    elif config['tipo'] == "DUAL_PENTA":
                                        row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios]
                                        ws.append_row(row_dez)
                                        ws_milhar = conectar_planilha(f"{banca_selecionada}_MILHAR")
                                        if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                        st.toast(f"Duplo Sucesso Penta! 5 Dezenas e Milhares salvas.", icon="✅")
                                    else:
                                        row = [data_busca.strftime('%Y-%m-%d'), horario_busca] + premios
                                        ws.append_row(row)
                                        st.toast(f"Sucesso! {premios}", icon="✅")
                                    time.sleep(1); st.rerun()
                                else: st.error(msg)
                    else: st.error("Erro Planilha")
                    
        else: 
            st.sidebar.subheader("🌪️ Extração Turbo")
            col1, col2 = st.sidebar.columns(2)
            with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
            with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
            if st.sidebar.button("🚀 INICIAR TURBO"):
                ws = conectar_planilha(config['nome_aba'])
                ws_milhar = conectar_planilha(f"{banca_selecionada}_MILHAR") if config['tipo'] in ["DUAL_SOLO", "DUAL_PENTA"] else None
                if ws:
                    status = st.sidebar.empty(); bar = st.sidebar.progress(0)
                    try: chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws.get_all_values() if len(r) >= 2 and normalizar_data(r[0])]
                    except: chaves = []
                    try: chaves_m = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_milhar.get_all_values() if len(r) >= 2 and normalizar_data(r[0])] if ws_milhar else []
                    except: chaves_m = []
                    delta = data_fim - data_ini
                    lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                    total_ops = len(lista_datas) * len(config['horarios']); op_atual = 0; sucessos = 0
                    buffer_principal = []
                    buffer_milhar = []
                    for dia in lista_datas:
                        for hora in config['horarios']:
                            op_atual += 1; bar.progress(op_atual / total_ops)
                            status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                            chave_atual = f"{dia.strftime('%Y-%m-%d')}|{normalizar_hora(hora)}"
                            if chave_atual in chaves: continue
                            if dia > date.today(): continue
                            if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue
                            premios, msg = raspar_dados_hibrido(banca_selecionada, dia, hora)
                            if premios:
                                if config['tipo'] == "DUAL_SOLO":
                                    buffer_principal.append([dia.strftime('%Y-%m-%d'), hora, premios[0][-2:], "00", "00", "00", "00"])
                                    if ws_milhar and (chave_atual not in chaves_m):
                                        buffer_milhar.append([dia.strftime('%Y-%m-%d'), hora] + premios)
                                        chaves_m.append(chave_atual)
                                elif config['tipo'] == "DUAL_PENTA":
                                    buffer_principal.append([dia.strftime('%Y-%m-%d'), hora] + [p[-2:] for p in premios])
                                    if ws_milhar and (chave_atual not in chaves_m):
                                        buffer_milhar.append([dia.strftime('%Y-%m-%d'), hora] + premios)
                                        chaves_m.append(chave_atual)
                                else: buffer_principal.append([dia.strftime('%Y-%m-%d'), hora] + premios)
                                sucessos += 1; chaves.append(chave_atual)
                            time.sleep(1.0)
                    status.text("🚚 Enviando lote de dados para o Google Sheets...")
                    if buffer_principal: ws.append_rows(buffer_principal)
                    if buffer_milhar and ws_milhar: ws_milhar.append_rows(buffer_milhar)
                    bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos registros."); time.sleep(2); st.rerun()
                else: st.sidebar.error("Erro Conexão")

    # --- PÁGINA DA BANCA ---
    
    if config['tipo'] == "MILHAR_VIEW":
        st.header(f"👑 Estratégia Vitorino & Cerco Invertido")
        
        with st.spinner("Analisando matrizes dimensionais e construindo milhares..."):
            hist_milhar = carregar_dados_hibridos(config['nome_aba'])
            hist_dez = carregar_dados_hibridos(config['base_dez'])
            
        if len(hist_milhar) > 0 and len(hist_dez) > 0:
            ult = hist_milhar[-1]
            st.success(f"📅 **Último Sorteio Lido:** {ult['data']} às {ult['horario']}")
            
            # --- MÓDULO 1: MILHARES SECAS ---
            milhares, detalhes = gerar_estrategia_vitorino(hist_milhar, hist_dez)
            if milhares:
                st.markdown(detalhes[0]['msg_radar'])
                st.markdown("### 🎯 As 3 Milhares de Ouro (Secas 1º Prêmio)")
                cols = st.columns(3)
                for i, m in enumerate(milhares):
                    with cols[i]:
                        with st.container(border=True):
                            st.metric(f"🥇 Milhar Vitorino {i+1}", m)
                            det = detalhes[i]
                            st.caption(f"⚙️ **Base:** {det['dezena']} (IA) <br> **Corpo:** {det['corpo']} (Hist) <br> **Coroa:** {det['coroa']} (Captura)", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- MÓDULO 2: RADAR DE CENTENA INVERTIDA (8 DÍGITOS) ---
            st.markdown("### 🎯 Radar de Centena Invertida (Cerco 8 Dígitos)")
            st.write("O sistema rastreia os 5 prêmios procurando onde a Banca soltou centenas com números repetidos para dar o bote estatístico.")
            
            radar_inv = calcular_radar_invertidas(hist_milhar)
            
            for alvo in radar_inv:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 2, 2])
                    
                    with c1:
                        st.subheader(f"🏆 {alvo['premio']}º Prêmio")
                        st.write(f"Última: `{alvo['ult_centena']}`")
                        st.caption(f"🚨 Max Seq Repetidas (25 jg): **{alvo['max_seq_rep']}x**")
                        
                    with c2:
                        if alvo['cor'] == "error": st.error(f"{alvo['status']}\n\n{alvo['alerta']}")
                        elif alvo['cor'] == "warning": st.warning(f"{alvo['status']}\n\n{alvo['alerta']}")
                        else: st.info(f"{alvo['status']}\n\n{alvo['alerta']}")
                        st.markdown(f"**Histórico (Últimos 6):** {' | '.join(alvo['backtest'])}")
                        
                    with c3:
                        st.markdown("**🛡️ Esquadrão 8 Dígitos:**")
                        str_esquadrao = " - ".join(alvo['esquadrao'])
                        st.code(str_esquadrao, language="text")
                        
            with st.expander("💸 Calculadora da Invertida (8 Dígitos)"):
                st.markdown("""
                - **Como Jogar:** Escolha o prêmio que está com status de ALVO (Quente ou Sniper). Marque os 8 dígitos na modalidade "Centena Invertida".
                - **Quantidade de Combinações:** 336 centenas.
                - **Custo Recomendado:** R$ 336,00 (R$ 1,00 por combinação).
                - **Retorno da Banca:** R$ 920,00.
                - **Lucro Líquido:** R$ 584,00 (Direto para o bolso com alta taxa de conversão).
                """)

            st.markdown("---")
            st.markdown("### 📊 Banco de Dados Bruto (Milhares 1º ao 5º)")
            df_show = pd.DataFrame(hist_milhar)
            st.dataframe(df_show.tail(10))

        else:
            st.warning("⚠️ Base vazia. Extraia os dados primeiro.")

    # ==========================================
    # PAINEL NORMAL (ORACLE E CHASER DEZENA)
    # ==========================================
    else:
        st.header(f"🔭 {config['display_name']} - Oracle 46")
        with st.spinner("Carregando e Limpando dados..."):
            historico = carregar_dados_hibridos(config['nome_aba'])
        if len(historico) > 0:
            ult = historico[-1]
            if config['tipo'] == "DUAL_SOLO": st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **1º Prêmio:** {str(ult['premios'][0])[-2:]}")
            else: st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **P1:** {ult['premios'][0]} ... **P5:** {ult['premios'][4]}")
            
            range_abas = [0, 1] if config['tipo'] == "DUAL_SOLO" else range(5)
            abas = st.tabs(["🔮 Oracle 46", "🎯 Unidades"] if config['tipo'] == "DUAL_SOLO" else [f"{i+1}º Prêmio" for i in range(5)])
            
            for idx_aba in range_abas:
                with abas[idx_aba]:
                    if config['tipo'] == "DUAL_SOLO" and idx_aba == 1:
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
                        if config['tipo'] in ["DUAL_SOLO", "DUAL_PENTA"]:
                            st.markdown("---")
                            st.markdown("### 🦅 Esquadrão Chaser (Perseguição de 10 Dezenas)")
                            estado_dez = rastrear_estado_chaser_dezenas(historico, idx_aba)
                            if estado_dez['target']:
                                st.markdown(f"**As 10 Dezenas:** `{', '.join(estado_dez['target'])}`")
                                if estado_dez['status'] == 'ativo': st.warning(f"🔒 **EM ANDAMENTO (TENTATIVA {estado_dez['attempts']+1} DE 8)**")
                                else: st.success(f"🎯 **NOVO CICLO (TENTATIVA 1 DE 8)**")
        else:
            st.warning("⚠️ Base vazia.")
