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
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    HAS_AI = True
except ImportError:
    HAS_AI = False

# =============================================================================
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V100 - Projeto Skynet", page_icon="🤖", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (Dezenas)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "tipo": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    
    "TRADICIONAL_MILHAR": { "display_name": "👑 TRADICIONAL (Vitorino)", "nome_aba": "TRADICIONAL_MILHAR", "slug": "loteria-tradicional", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "base_dez": "BASE_TRADICIONAL_DEZ" },
    
    "LOTEP_MILHAR": { "display_name": "👑 LOTEP (Vitorino)", "nome_aba": "LOTEP_MILHAR", "slug": "lotep", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"], "base_dez": "LOTEP_TOP5" },
    
    "CAMINHO_MILHAR": { "display_name": "👑 CAMINHO (Vitorino)", "nome_aba": "CAMINHO_MILHAR", "slug": "caminho-da-sorte", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"], "base_dez": "CAMINHO_TOP5" },
    
    "MONTE_MILHAR": { "display_name": "👑 MONTE CARLOS (Vitorino)", "nome_aba": "MONTE_MILHAR", "slug": "nordeste-monte-carlos", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"], "base_dez": "MONTE_TOP5" }
}

def is_repetida(m_str):
    if len(m_str) != 4: return False
    return len(set(m_str)) < 4

def is_simples(m_str):
    if len(m_str) != 4: return False
    return len(set(m_str)) == 4

def is_all_even(m_str):
    if len(m_str) != 4: return False
    return all(d in '02468' for d in m_str)

def is_all_odd(m_str):
    if len(m_str) != 4: return False
    return all(d in '13579' for d in m_str)

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #ffd700 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #00ff00; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .alerta-verde { background-color: #1e4620; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 10px; }
    .alerta-vermelho { background-color: #4a1919; padding: 15px; border-radius: 8px; border-left: 5px solid #dc3545; margin-bottom: 10px; }
    .alerta-cinza { background-color: #2b2b2b; padding: 15px; border-radius: 8px; border-left: 5px solid #888888; margin-bottom: 10px; }
    .alerta-skynet-verde { background-color: #001f3f; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px; border: 1px solid #007bff;}
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
                            return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3A. CÉREBRO: ESQUADRÃO DE 4 GATILHOS EXTREMOS (>= 95%) ---
# =============================================================================

def calcular_radar_esquadrao_sniper(history_slice):
    if len(history_slice) < 50: return []
    resultados_radar = []
    
    for p_idx in range(5):
        if len(history_slice) < 4: continue
            
        m1 = str(history_slice[-1]['premios'][p_idx]).zfill(4) 
        m2 = str(history_slice[-2]['premios'][p_idx]).zfill(4) 
        m3 = str(history_slice[-3]['premios'][p_idx]).zfill(4) 
        m4 = str(history_slice[-4]['premios'][p_idx]).zfill(4) 
        
        if "0000" in [m1, m2, m3, m4]: continue

        gatilhos_armados = []

        if is_repetida(m1) and is_repetida(m2):
            targets_a = []
            for i in range(1, len(history_slice) - 1):
                h1 = str(history_slice[i]['premios'][p_idx]).zfill(4)
                h2 = str(history_slice[i-1]['premios'][p_idx]).zfill(4)
                if h1 != "0000" and h2 != "0000" and is_repetida(h1) and is_repetida(h2):
                    nxt = str(history_slice[i+1]['premios'][p_idx]).zfill(4)
                    if nxt != "0000": targets_a.append(nxt)
            if len(targets_a) >= 3:
                all_digits = "".join(targets_a)
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                s_digits = sorted(counts.items(), key=lambda x: (x[1], x[0]))
                c1, c2 = s_digits[0][0], s_digits[1][0]
                gatilhos_armados.append(("🔥 GATILHO A (Repetição 2x)", targets_a, c1, c2))

        if is_simples(m1) and is_simples(m2) and is_simples(m3):
            targets_b = []
            for i in range(2, len(history_slice) - 1):
                h1 = str(history_slice[i]['premios'][p_idx]).zfill(4)
                h2 = str(history_slice[i-1]['premios'][p_idx]).zfill(4)
                h3 = str(history_slice[i-2]['premios'][p_idx]).zfill(4)
                if "0000" not in [h1, h2, h3] and is_simples(h1) and is_simples(h2) and is_simples(h3):
                    nxt = str(history_slice[i+1]['premios'][p_idx]).zfill(4)
                    if nxt != "0000": targets_b.append(nxt)
            if len(targets_b) >= 3:
                all_digits = "".join(targets_b)
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                s_digits = sorted(counts.items(), key=lambda x: (x[1], x[0]))
                c1, c2 = s_digits[0][0], s_digits[1][0]
                gatilhos_armados.append(("🧊 GATILHO B (Escassez Tripla)", targets_b, c1, c2))

        shared = set(m1) & set(m2) & set(m3) & set(m4)
        if shared:
            digito_chiclete = list(shared)[0]
            targets_c = []
            for i in range(3, len(history_slice) - 1):
                h1 = str(history_slice[i]['premios'][p_idx]).zfill(4)
                h2 = str(history_slice[i-1]['premios'][p_idx]).zfill(4)
                h3 = str(history_slice[i-2]['premios'][p_idx]).zfill(4)
                h4 = str(history_slice[i-3]['premios'][p_idx]).zfill(4)
                if "0000" not in [h1, h2, h3, h4]:
                    if digito_chiclete in h1 and digito_chiclete in h2 and digito_chiclete in h3 and digito_chiclete in h4:
                        nxt = str(history_slice[i+1]['premios'][p_idx]).zfill(4)
                        if nxt != "0000": targets_c.append(nxt)
            if len(targets_c) >= 3:
                all_digits = "".join(targets_c)
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                counts[digito_chiclete] = 9999 
                s_digits = sorted(counts.items(), key=lambda x: (x[1], x[0]))
                c1 = digito_chiclete
                c2 = s_digits[0][0]
                gatilhos_armados.append(("🎯 GATILHO C (Dígito Chiclete 4x)", targets_c, c1, c2))

        paridade_match = ""
        if is_all_even(m1) and is_all_even(m2): paridade_match = "PAR"
        elif is_all_odd(m1) and is_all_odd(m2): paridade_match = "ÍMPAR"

        if paridade_match:
            targets_d = []
            for i in range(1, len(history_slice) - 1):
                h1 = str(history_slice[i]['premios'][p_idx]).zfill(4)
                h2 = str(history_slice[i-1]['premios'][p_idx]).zfill(4)
                if h1 != "0000" and h2 != "0000":
                    if paridade_match == "PAR" and is_all_even(h1) and is_all_even(h2):
                        nxt = str(history_slice[i+1]['premios'][p_idx]).zfill(4)
                        if nxt != "0000": targets_d.append(nxt)
                    elif paridade_match == "ÍMPAR" and is_all_odd(h1) and is_all_odd(h2):
                        nxt = str(history_slice[i+1]['premios'][p_idx]).zfill(4)
                        if nxt != "0000": targets_d.append(nxt)
            if len(targets_d) >= 3:
                all_digits = "".join(targets_d)
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                s_digits = sorted(counts.items(), key=lambda x: (x[1], x[0]))
                c1, c2 = s_digits[0][0], s_digits[1][0]
                gatilhos_armados.append((f"⚖️ GATILHO D (100% {paridade_match} 2x)", targets_d, c1, c2))

        if not gatilhos_armados:
            resultados_radar.append({"premio": p_idx + 1, "status": "REPOUSO"})
            continue

        melhor_gatilho = None
        melhor_taxa = -1
        
        for g_nome, targets, c1, c2 in gatilhos_armados:
            esq_vivo = [str(d) for d in range(10) if str(d) not in [c1, c2]]
            vitorias = 0
            derrotas = 0
            bt_visual = []
            for t in targets:
                if all(d in esq_vivo for d in t):
                    vitorias += 1; bt_visual.append("✅")
                else:
                    derrotas += 1; bt_visual.append("❌")
            taxa = (vitorias / len(targets)) * 100
            if taxa > melhor_taxa:
                melhor_taxa = taxa
                melhor_gatilho = {
                    "premio": p_idx + 1, "status": "ANALISADO", "tipo": g_nome,
                    "cortes": f"{c1} e {c2}", "esquadrao": ",".join([f"{d},{d}" for d in esq_vivo]),
                    "taxa": taxa, "ocorrencias": len(targets), "backtest": bt_visual[-10:]
                }

        if melhor_gatilho: resultados_radar.append(melhor_gatilho)
        else: resultados_radar.append({"premio": p_idx + 1, "status": "REPOUSO"})
            
    return resultados_radar

# =============================================================================
# --- 3B. PROJETO SKYNET: PREVISÃO VIA MACHINE LEARNING (Apenas Lotep/Caminho) ---
# =============================================================================

def executar_conselho_ia(history_slice, p_idx):
    if not HAS_AI or len(history_slice) < 50:
        return None

    records = []
    for i in range(len(history_slice)-1):
        curr = history_slice[i]
        nxt = history_slice[i+1]
        curr_m = str(curr['premios'][p_idx]).zfill(4)
        nxt_m = str(nxt['premios'][p_idx]).zfill(4)
        if curr_m == "0000" or nxt_m == "0000": continue
        
        try: dt_obj = datetime.strptime(curr['data'], '%Y-%m-%d'); dia_semana = dt_obj.weekday()
        except: dia_semana = 0
        try: hora = int(curr['horario'].split(':')[0])
        except: hora = 0

        record = {
            'dia': dia_semana, 'hora': hora,
            'cabeca': int(curr_m[0]), 'final': int(curr_m[-1])
        }
        for d in range(10): record[f't_{d}'] = 1 if str(d) in nxt_m else 0
        records.append(record)

    if len(records) < 30: return None

    df = pd.DataFrame(records)
    X = df[['dia', 'hora', 'cabeca', 'final']]

    ult = history_slice[-1]
    ult_m = str(ult['premios'][p_idx]).zfill(4)
    if ult_m == "0000": return None
    
    try: curr_dia = datetime.strptime(ult['data'], '%Y-%m-%d').weekday()
    except: curr_dia = 0
    try: curr_hora = int(ult['horario'].split(':')[0])
    except: curr_hora = 0
    
    X_curr = pd.DataFrame([{'dia': curr_dia, 'hora': curr_hora, 'cabeca': int(ult_m[0]), 'final': int(ult_m[-1])}])

    probas_rf = {}; probas_lr = {}
    
    try:
        for d in range(10):
            y = df[f't_{d}']
            if len(y.unique()) == 1:
                probas_rf[d] = 1.0 if y.iloc[0] == 1 else 0.0
                probas_lr[d] = 1.0 if y.iloc[0] == 1 else 0.0
                continue

            rf = RandomForestClassifier(n_estimators=30, random_state=42, max_depth=5)
            lr = LogisticRegression(max_iter=300, random_state=42)
            rf.fit(X, y); lr.fit(X, y)

            p_rf = rf.predict_proba(X_curr)[0]; p_lr = lr.predict_proba(X_curr)[0]
            idx_1_rf = list(rf.classes_).index(1); idx_1_lr = list(lr.classes_).index(1)
            
            probas_rf[d] = p_rf[idx_1_rf]
            probas_lr[d] = p_lr[idx_1_lr]
    except Exception as e: return None

    rank_rf = sorted(probas_rf.items(), key=lambda x: x[1])
    rank_lr = sorted(probas_lr.items(), key=lambda x: x[1])

    cortes_rf = [str(rank_rf[0][0]), str(rank_rf[1][0])]; cortes_rf.sort()
    cortes_lr = [str(rank_lr[0][0]), str(rank_lr[1][0])]; cortes_lr.sort()

    consenso = (cortes_rf == cortes_lr)
    esquadrao = [str(d) for d in range(10) if str(d) not in cortes_rf]
    esq_formatado = ",".join([f"{d},{d}" for d in esquadrao])

    return {
        'cortes_rf': cortes_rf, 'cortes_lr': cortes_lr,
        'consenso': consenso, 'cortes_finais': cortes_rf if consenso else None,
        'esquadrao': esq_formatado if consenso else ""
    }

# =============================================================================
# --- 5. INTERFACE NAVEGAÇÃO E TELAS ---
# =============================================================================

if "menu_nav" not in st.session_state:
    st.session_state.menu_nav = "🏠 RADAR GERAL (Home)"

def acionar_teletransporte(destino):
    st.session_state.menu_nav = destino

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
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

if escolha_menu == "🏠 RADAR GERAL (Home)":
    st.title("🛡️ PENTÁGONO - CENTRAL DE ALVOS (V100 Skynet)")
    st.markdown("O sistema processa 4 Gatilhos de Extrema Anomalia simultaneamente. Filtro Absoluto >= 95%.")
    
    alertas_sniper = []
    
    with st.spinner("📡 Escaneando Esquadrão de 4 Gatilhos nas Bancas..."):
        for banca_key, config in CONFIG_BANCAS.items():
            if config['tipo'] == 'MILHAR_VIEW' and "TRADICIONAL" not in banca_key:
                hist_milhar = carregar_dados_hibridos(config['nome_aba'])
                if len(hist_milhar) >= 50:
                    radar_dados = calcular_radar_esquadrao_sniper(hist_milhar)
                    
                    for alvo in radar_dados:
                        nome_banca_limpo = config['display_name'].replace("👑 ", "")
                        if alvo.get('status') == "ANALISADO" and alvo.get('taxa', 0) >= 95.0:
                            alertas_sniper.append({
                                "banca_key": banca_key,
                                "banca": nome_banca_limpo,
                                "premio": alvo['premio'],
                                "tipo": alvo['tipo'],
                                "taxa": f"{alvo['taxa']:.1f}%",
                                "cortes": alvo['cortes']
                            })

    if not alertas_sniper:
        st.info("😴 **Zona Segura:** Nenhum dos 4 gatilhos extremos bateu os 95% de segurança. O mercado está padrão. Arma travada.")
    else:
        st.markdown("### 🎯 SNIPERS AUTORIZADOS ( >= 95% )")
        for a in alertas_sniper:
            with st.container(border=True):
                col_txt, col_btn = st.columns([4, 1])
                with col_txt:
                    st.success(f"**{a['banca']} - {a['premio']}º Prêmio** | {a['tipo']} | Acerto: **{a['taxa']}** | Corte `{a['cortes']}`.")
                with col_btn:
                    st.button("🎯 Abrir Banca", key=f"go_{a['banca_key']}_{a['premio']}", on_click=acionar_teletransporte, args=(a['banca_key'],), use_container_width=True)

else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    
    url_banca = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
    st.sidebar.markdown(f"<a href='{url_banca}' target='_blank'><button style='width: 100%; border-radius: 5px; font-weight: bold; background-color: #007bff; color: white; padding: 8px 10px; border: none; cursor: pointer; margin-bottom: 10px;'>🌐 Visitar Site da Banca</button></a>", unsafe_allow_html=True)
    
    if st.sidebar.button("🧹 EXECUTAR FAXINA NO BANCO DE DADOS"):
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
            
            if st.button("🚀 Baixar & Salvar"):
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
        
        if st.sidebar.button("🚀 INICIAR TURBO"):
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
        st.header(f"👑 Esquadrão 4 Gatilhos (Tolerância >= 95%)")
        
        with st.spinner("Varrendo o globo em busca das 4 maiores anomalias matemáticas..."):
            hist_milhar = carregar_dados_hibridos(config['nome_aba'])
            
        if len(hist_milhar) > 0:
            ult = hist_milhar[-1]
            st.success(f"📅 **Último Sorteio Lido:** {ult['data']} às {ult['horario']}")
            
            # --- CRIAÇÃO DAS ABAS SKYNET PARA LOTEP E CAMINHO ---
            if banca_selecionada in ["LOTEP_MILHAR", "CAMINHO_MILHAR"] and HAS_AI:
                abas_estrategia = st.tabs(["🎯 Radares (V99)", "🧠 Skynet (IAs de Machine Learning)"])
                aba_ativa_radares = abas_estrategia[0]
                aba_ativa_skynet = abas_estrategia[1]
            else:
                aba_ativa_radares = st.container()
                aba_ativa_skynet = None

            with aba_ativa_radares:
                st.markdown("### 🎯 Análise Tática de Extremos")
                st.write("O robô procura por Exaustão de Repetição, Escassez Tripla, Dígito Chiclete (4x) e Colapso de Paridade.")
                
                radar_inv = calcular_radar_esquadrao_sniper(hist_milhar)
                
                for alvo in radar_inv:
                    if alvo.get('status') == "REPOUSO":
                        html_card = (
                            '<div class="alerta-cinza">'
                            f'<h4 style="margin:0; color:white;">🏆 {alvo["premio"]}º Prêmio | 😴 REPOUSO</h4>'
                            '<p style="margin-top:5px; color:#cccccc;">Nenhuma das 4 Anomalias Extremas detectada. Aguardando momento letal.</p>'
                            '</div>'
                        )
                        st.markdown(html_card, unsafe_allow_html=True)
                        continue

                    taxa = alvo['taxa']
                    tipo_g = alvo['tipo']
                    
                    if taxa >= 95.0:
                        cor_classe = "alerta-verde"
                        status_icone = f"🟢 SNIPER AUTORIZADO (Taxa >= 95%)"
                        msg_corpo = f"O algoritmo detectou uma brecha gigante! Cortando os dígitos <b>{alvo['cortes']}</b>, a margem de segurança é de elite."
                        codigo_display = f'<div style="background-color:black; color:#00ff00; padding:10px; border-radius:5px; margin-bottom:10px; font-family:monospace; letter-spacing: 2px;">{alvo["esquadrao"]}</div>'
                    else:
                        cor_classe = "alerta-vermelho"
                        status_icone = f"🚫 ALVO BLOQUEADO (Acerto: {taxa:.1f}%)"
                        msg_corpo = f"O gatilho armou, mas o corte de dígitos <b>{alvo['cortes']}</b> não atinge os 95% de segurança exigidos. Fique fora."
                        codigo_display = f'<div style="background-color:black; color:#ff4444; padding:10px; border-radius:5px; margin-bottom:10px; font-family:monospace;">Cortes: {alvo["cortes"]} (NÃO COPIAR)</div>'

                    html_card = (
                        f'<div class="{cor_classe}">'
                        f'<h4 style="margin:0; color:white;">🏆 {alvo["premio"]}º Prêmio | {tipo_g}</h4>'
                        f'<h5 style="margin:5px 0 0 0; color:#ffd700;">{status_icone}</h5>'
                        f'<p style="margin-top:5px; color:#ffffff;">{msg_corpo}</p>'
                        f'{codigo_display}'
                        f'<div style="font-size:0.9em; color:#ffd700; margin-top:8px;">'
                        f'<b>📊 Histórico da Anomalia:</b> Taxa de Acerto: <b>{taxa:.1f}%</b> | '
                        f'🔁 Ocorrências Lidas: {alvo["ocorrencias"]}<br>'
                        f'<b>🕰️ Backtest:</b> {" | ".join(alvo["backtest"])}'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(html_card, unsafe_allow_html=True)
            
            # --- LÓGICA DA ABA SKYNET ---
            if aba_ativa_skynet is not None:
                with aba_ativa_skynet:
                    st.markdown("### 🧠 Conselho de Generais (Machine Learning)")
                    st.info("Duas Inteligências Artificiais (Floresta Aleatória e Regressão Logística) estão escaneando o banco de dados. Elas só autorizam o tiro se **ambas concordarem** nos 2 números que devem ser cortados.")
                    
                    with st.spinner("Treinando Redes Neurais... Isso pode levar alguns segundos..."):
                        for p_idx in range(5):
                            res_ia = executar_conselho_ia(hist_milhar, p_idx)
                            if res_ia is None:
                                st.markdown(f'<div class="alerta-cinza"><h4 style="margin:0; color:white;">🏆 {p_idx+1}º Prêmio</h4><p style="margin-top:5px; color:#ccc;">Dados insuficientes para treino das IAs neste prêmio.</p></div>', unsafe_allow_html=True)
                            else:
                                if res_ia['consenso']:
                                    html_skynet = (
                                        f'<div class="alerta-skynet-verde">'
                                        f'<h4 style="margin:0; color:white;">🏆 {p_idx+1}º Prêmio | 🟢 CONSENSO DE IA ALCANÇADO</h4>'
                                        f'<p style="margin-top:5px; color:#ffffff;">As duas Redes Neurais (IA 1 e IA 2) cruzaram as variáveis e <b>concordaram</b>. Os dígitos com menor probabilidade matemática de sair são: <b>{res_ia["cortes_finais"][0]} e {res_ia["cortes_finais"][1]}</b>.</p>'
                                        f'<div style="background-color:black; color:#00ff00; padding:10px; border-radius:5px; margin-bottom:10px; font-family:monospace; letter-spacing: 2px;">{res_ia["esquadrao"]}</div>'
                                        f'</div>'
                                    )
                                    st.markdown(html_skynet, unsafe_allow_html=True)
                                else:
                                    html_skynet = (
                                        f'<div class="alerta-vermelho">'
                                        f'<h4 style="margin:0; color:white;">🏆 {p_idx+1}º Prêmio | 🚫 DIVERGÊNCIA NO COMANDO</h4>'
                                        f'<p style="margin-top:5px; color:#ffffff;">As Redes Neurais discordaram. IA 1 mandou cortar <b>{res_ia["cortes_rf"][0]} e {res_ia["cortes_rf"][1]}</b>. IA 2 mandou cortar <b>{res_ia["cortes_lr"][0]} e {res_ia["cortes_lr"][1]}</b>. Operação Abortada por segurança.</p>'
                                        f'</div>'
                                    )
                                    st.markdown(html_skynet, unsafe_allow_html=True)
                                    
            # --- CALCULADORA DE HEDGE ---
            st.markdown("---")
            st.subheader("🛡️ Calculadora de Seguro de Banca")
            
            with st.container(border=True):
                col_calc1, col_calc2 = st.columns(2)
                with col_calc1:
                    valor_milhar = st.number_input("💰 Valor da Invertida 8D (R$):", min_value=1.0, value=40.96, step=1.0)
                
                seguro_recomendado = valor_milhar / 21 
                custo_total = valor_milhar + seguro_recomendado
                retorno_seguro = seguro_recomendado * 23
                
                with col_calc2:
                    st.info(f"**🛡️ Jogue no Grupo da Milhar:** R$ {seguro_recomendado:.2f}")
                    st.caption(f"Custo Total: R$ {custo_total:.2f} | Prêmio Grupo: R$ {retorno_seguro:.2f}")
                    
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
