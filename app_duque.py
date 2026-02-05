import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, date, timedelta
import time
import re
from bs4 import BeautifulSoup
import altair as alt

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="Central DUQUE V8.0 - Sniper Sequência", page_icon="👑", layout="wide")

CONFIG_BANCA = {
    "display_name": "TRADICIONAL (Duque)",
    "slug": "loteria-tradicional",
    "logo_url": "https://cdn-icons-png.flaticon.com/512/1063/1063233.png", 
    "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"]
}

# Inicialização de Estados
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_g1' not in st.session_state: st.session_state['auto_g1'] = 1
if 'auto_g2' not in st.session_state: st.session_state['auto_g2'] = 2

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'apagar':
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    else: return
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

# --- CSS ESTILO PENTÁGONO V29 ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #1a002e 0%, #2E004F 100%); color: #ffffff; }
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown { color: #ffffff !important; }
    .stNumberInput input { color: white !important; background-color: rgba(255,255,255,0.1) !important; }
    [data-testid="stTable"] { color: white !important; background-color: transparent !important; }
    
    /* CAIXAS DE ALERTA */
    .box-alerta { background-color: #580000; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; color: #ffcccc; }
    .box-aviso { background-color: #584e00; padding: 15px; border-radius: 8px; border-left: 5px solid #ffd700; margin-bottom: 15px; color: #fffacd; }
    .box-inverso-critico { background-color: #2e004f; padding: 15px; border-radius: 8px; border-left: 5px solid #d000ff; margin-bottom: 15px; color: #e0b0ff; font-weight: bold; }
    .box-inverso-atencao { background-color: #1a002e; padding: 15px; border-radius: 8px; border-left: 5px solid #9932cc; margin-bottom: 15px; color: #dda0dd; }

    /* Bolinhas dos Setores */
    .bola-s1 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); }
    .bola-s2 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); }
    .bola-s3 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); }
    
    /* Box do SNIPER DUQUE (VERDE) */
    .sniper-box { 
        background: linear-gradient(135deg, #004d00, #002b00); 
        border: 2px solid #00ff00; 
        padding: 20px; 
        border-radius: 15px; 
        margin-bottom: 20px; 
        text-align: center;
        box-shadow: 0px 0px 25px rgba(0, 255, 0, 0.3);
    }
    
    /* Box do SNIPER SEQUÊNCIA (ROXO - MODO ESPECIAL) */
    .sniper-box-seq { 
        background: linear-gradient(135deg, #4b0082, #240b36); 
        border: 2px solid #da70d6; 
        padding: 20px; 
        border-radius: 15px; 
        margin-bottom: 20px; 
        text-align: center;
        box-shadow: 0px 0px 25px rgba(218, 112, 214, 0.5);
    }
    
    .sniper-title { font-size: 24px; font-weight: 900; color: #ffffff; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; text-shadow: 0 0 10px rgba(255,255,255,0.5); }
    .sniper-desc { font-size: 14px; color: #ddd; font-style: italic; margin-bottom: 15px; }
    
    /* BACKTEST STYLES */
    .backtest-container { display: flex; justify-content: center; gap: 15px; margin-top: 5px; margin-bottom: 30px; flex-wrap: wrap; }
    .bt-card { background-color: rgba(30, 30, 30, 0.8); border-radius: 10px; padding: 10px; width: 100px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 24px; margin-bottom: 5px; }
    .bt-num { font-size: 14px; font-weight: bold; margin-bottom: 2px; }
    .bt-label { font-size: 11px; opacity: 0.8; }
    
    .max-loss-info {
        text-align: center;
        background-color: rgba(255, 0, 0, 0.1);
        border: 1px solid rgba(255, 0, 0, 0.3);
        color: #ffaaaa;
        padding: 5px 15px;
        border-radius: 20px;
        display: inline-block;
        margin-top: 10px;
        font-size: 14px;
        font-weight: bold;
    }
    
    div[data-testid="stTable"] table { color: white; }
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)

if st.session_state['tocar_som_salvar']: reproduzir_som('sucesso'); st.session_state['tocar_som_salvar'] = False
if st.session_state['tocar_som_apagar']: reproduzir_som('apagar'); st.session_state['tocar_som_apagar'] = False

# =============================================================================
# --- 2. CONEXÃO & SCRAPING ---
# =============================================================================
def conectar_planilha():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        try:
            sh = gc.open("CentralBichos")
            return sh.worksheet("TRADICIONAL")
        except: return None
    return None

def carregar_dados():
    worksheet = conectar_planilha()
    if worksheet:
        dados = worksheet.get_all_values()
        lista_duques = []
        ultimo_horario = "--:--"
        try:
            for row in dados:
                if len(row) >= 2 and row[0].isdigit() and row[1].isdigit():
                    g1, g2 = int(row[0]), int(row[1])
                    lista_duques.append(tuple(sorted((g1, g2))))
                    if len(row) >= 3: ultimo_horario = row[2]
        except: pass
        return lista_duques, ultimo_horario
    return [], "--:--"

def salvar_duque(b1, b2, horario, data_ref):
    worksheet = conectar_planilha()
    if worksheet:
        try:
            data_str = data_ref.strftime("%Y-%m-%d")
            worksheet.append_row([int(b1), int(b2), str(horario), data_str])
            return True
        except: return False
    return False

def deletar_ultimo():
    worksheet = conectar_planilha()
    if worksheet:
        try:
            total = len(worksheet.get_all_values())
            if total > 0: worksheet.delete_rows(total); return True
        except: return False
    return False

def montar_url_correta(slug, data_alvo):
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_duque_avancado(data_alvo, horario_alvo):
    url = montar_url_correta(CONFIG_BANCA['slug'], data_alvo)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, None, f"Erro HTTP {r.status_code}"
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        for tabela in tabelas:
            cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
            if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
            horario_encontrado = None
            prev = tabela.find_previous(string=padrao_hora)
            if prev:
                m = re.search(padrao_hora, prev)
                if m:
                    raw = m.group(1).strip()
                    if ':' in raw: horario_encontrado = raw
                    elif 'h' in raw: horario_encontrado = raw.replace('h', '').strip().zfill(2) + ":00"
                    else: horario_encontrado = raw.strip().zfill(2) + ":00"
            h_alvo_clean = horario_alvo.replace('h','').strip()
            if horario_encontrado == h_alvo_clean:
                bicho1 = None; bicho2 = None
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 3:
                        premio_txt = colunas[0].get_text().strip()
                        grp_txt = colunas[2].get_text().strip()
                        if grp_txt.isdigit():
                            grp = int(grp_txt)
                            nums = re.findall(r'\d+', premio_txt)
                            if nums:
                                pos = int(nums[0])
                                if pos == 1: bicho1 = grp
                                elif pos == 2: bicho2 = grp
                if bicho1 and bicho2: return bicho1, bicho2, "Sucesso"
                else: return None, None, "Horário encontrado, mas incompleto."
        return None, None, "Horário não encontrado nesta data."
    except Exception as e: return None, None, f"Erro: {e}"

# =============================================================================
# --- 3. LÓGICA V8.0 (SNIPER SEQUÊNCIA - 275 PARES) ---
# =============================================================================
def gerar_universo_duques():
    todos = []
    for i in range(1, 26):
        for j in range(i, 26): todos.append((i, j))
    setor1 = [d for k, d in enumerate(todos) if k % 3 == 0]
    setor2 = [d for k, d in enumerate(todos) if k % 3 == 1]
    setor3 = [d for k, d in enumerate(todos) if k % 3 == 2]
    return todos, {"SETOR 1 (S1)": setor1, "SETOR 2 (S2)": setor2, "SETOR 3 (S3)": setor3}

def formatar_palpite_texto(lista_tuplas):
    lista_ordenada = sorted(list(set(lista_tuplas)))
    texto = ""
    for i, p in enumerate(lista_ordenada):
        texto += f"[{p[0]:02}-{p[1]:02}] "
        if (i + 1) % 10 == 0: texto += "\n" 
    return texto.strip()

# --- VERIFICA SE É UMA SEQUÊNCIA ---
def verificar_sequencia_bichos(duque):
    b1, b2 = sorted(duque)
    if b2 - b1 == 1: return True # Ex: 1-2, 2-3
    if b1 == 1 and b2 == 25: return True # Ex: 25-1
    return False

# --- GERA UNIVERSO LIMPO (SEM SEQUÊNCIAS E SEM DUPLOS) ---
def gerar_universo_limpo_275():
    todos, _ = gerar_universo_duques()
    universo_limpo = []
    for d in todos:
        # Remove duplos (bichos iguais)
        if d[0] == d[1]: continue
        # Remove sequências
        if verificar_sequencia_bichos(d): continue
        universo_limpo.append(d)
    return universo_limpo

# --- ALGORITMO SNIPER SEQUÊNCIA V8 (MODO ESPECIAL) ---
def gerar_sniper_sequencia_v8(historico_slice):
    hist_rev = historico_slice[::-1]
    pool_275 = gerar_universo_limpo_275() # Começa com os 275 limpos
    
    # Critério de corte: Eliminar os 75 piores (Frios)
    # Pontua com base em frequência média (últimos 50 jogos)
    c_medio = Counter(hist_rev[:50])
    
    # Ordena do mais frequente para o menos frequente
    # Queremos manter os 200 melhores (Top 200)
    rank_final = sorted(pool_275, key=lambda x: c_medio[x], reverse=True)
    
    # Pega os 200 primeiros (elimina os 75 últimos)
    top_200 = rank_final[:200]
    return sorted(top_200)

# --- ALGORITMO CAMALEÃO V6 (MODO NORMAL) ---
def gerar_sniper_top200_v6(historico_slice):
    hist_rev = historico_slice[::-1]
    todos_duques, _ = gerar_universo_duques()
    c_curto = Counter(hist_rev[:15])
    c_longo = Counter(hist_rev[:100])
    
    if len(historico_slice) > 0:
        ultimo = historico_slice[-1]
        bichos_vicio = set([ultimo[0], ultimo[1]])
        for b in list(bichos_vicio):
            bichos_vicio.add(b + 1 if b < 25 else 1)
            bichos_vicio.add(b - 1 if b > 1 else 25)
    else:
        bichos_vicio = set()

    scores = {}
    for d in todos_duques:
        score = 0
        score += c_curto[d] * 5.0
        score += c_longo[d] * 1.0
        if d[0] in bichos_vicio or d[1] in bichos_vicio:
            score += 500.0
        scores[d] = score
        
    rank_final = sorted(scores.items(), key=lambda x: -x[1])
    top_200 = [d for d, s in rank_final][:200]
    return sorted(top_200)

# --- FUNÇÃO DE BACKTEST DINÂMICA (DETECTA QUAL SNIPER USAR) ---
def executar_backtest_duque(historico):
    resultados_backtest = []
    for i in range(1, 5):
        if len(historico) <= i + 50: break 
        
        target_duque = tuple(sorted(historico[-i]))
        hist_treino = historico[:-i] 
        ultimo_jogo_treino = hist_treino[-1]
        
        # Decide qual Sniper usar no passado
        if verificar_sequencia_bichos(ultimo_jogo_treino):
            # Se no passado deu sequência, o robô teria ativado o V8
            sniper_past = gerar_sniper_sequencia_v8(hist_treino)
            tipo = "SEQUÊNCIA"
        else:
            # Senão, teria usado o V6 Normal
            sniper_past = gerar_sniper_top200_v6(hist_treino)
            tipo = "NORMAL"
        
        win = target_duque in sniper_past
        
        resultados_backtest.append({
            "index": i,
            "duque_real": target_duque,
            "vitoria": win,
            "tipo": tipo
        })
    return resultados_backtest

# --- CALCULAR RECORDE DE DERROTAS ---
def calcular_max_derrotas_duque(historico):
    max_derrotas = 0
    derrotas_consecutivas_temp = 0
    range_analise = min(50, len(historico) - 50)
    start_idx = len(historico) - range_analise
    
    for i in range(start_idx, len(historico)):
        target_duque = tuple(sorted(historico[i]))
        hist_treino = historico[:i]
        ultimo_jogo_treino = hist_treino[-1]
        
        if verificar_sequencia_bichos(ultimo_jogo_treino):
            sniper_past = gerar_sniper_sequencia_v8(hist_treino)
        else:
            sniper_past = gerar_sniper_top200_v6(hist_treino)
            
        win = target_duque in sniper_past
        if not win:
            derrotas_consecutivas_temp += 1
        else:
            if derrotas_consecutivas_temp > max_derrotas:
                max_derrotas = derrotas_consecutivas_temp
            derrotas_consecutivas_temp = 0
    if derrotas_consecutivas_temp > max_derrotas:
        max_derrotas = derrotas_consecutivas_temp
    return max_derrotas

# --- TABELA DE STRESS ---
def calcular_tabela_stress_duque(historico):
    _, mapa = gerar_universo_duques()
    tabela = []
    total_jogos = len(historico)
    for nome_setor, lista_duques in mapa.items():
        atraso = 0
        for jogo in reversed(historico):
            if tuple(sorted(jogo)) in lista_duques: break
            atraso += 1
        seq_atual_real = 0
        last_duque = tuple(sorted(historico[-1]))
        if last_duque in lista_duques:
            for jogo in reversed(historico):
                if tuple(sorted(jogo)) in lista_duques: seq_atual_real += 1
                else: break
        vitorias_total = 0; max_atraso = 0; curr_atraso = 0; max_seq = 0; curr_seq = 0
        for jogo in historico:
            duque = tuple(sorted(jogo))
            if duque in lista_duques:
                vitorias_total += 1
                curr_seq += 1
                if curr_atraso > max_atraso: max_atraso = curr_atraso
                curr_atraso = 0
            else:
                if curr_seq > max_seq: max_seq = curr_seq
                curr_seq = 0
                curr_atraso += 1
        if curr_atraso > max_atraso: max_atraso = curr_atraso
        if curr_seq > max_seq: max_seq = curr_seq
        porcentagem = (vitorias_total / total_jogos * 100) if total_jogos > 0 else 0
        tabela.append({
            "SETOR": nome_setor, 
            "% PRESENÇA": porcentagem, 
            "ATRASO": atraso, 
            "REC. ATRASO": max_atraso, 
            "SEQ. ATUAL": seq_atual_real,
            "REC. SEQ. (V)": max_seq
        })
    return pd.DataFrame(tabela)

# --- VISUAL BOLINHAS ---
def gerar_bolinhas_recentes_duque(historico):
    _, mapa = gerar_universo_duques()
    html = "<div>"
    for duque in reversed(historico[-12:]):
        duque_sorted = tuple(sorted(duque))
        classe = ""
        letra = ""
        if duque_sorted in mapa["SETOR 1 (S1)"]: classe = "bola-s1"; letra = "S1"
        elif duque_sorted in mapa["SETOR 2 (S2)"]: classe = "bola-s2"; letra = "S2"
        elif duque_sorted in mapa["SETOR 3 (S3)"]: classe = "bola-s3"; letra = "S3"
        else: classe = "bola-s1"; letra = "?"
        html += f"<div class='{classe}'>{letra}</div>"
    html += "</div>"
    return html

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================
with st.sidebar:
    st.image(CONFIG_BANCA['logo_url'], width=100)
    st.title("MENU DUQUE")
    st.link_button("🔗 Ver Site Oficial", "https://www.resultadofacil.com.br")
    st.markdown("---")

    with st.expander("📥 Importar Resultado", expanded=True):
        opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
        if opcao_data == "Hoje": data_busca = date.today()
        elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
        else: data_busca = st.sidebar.date_input("Escolha:", date.today())
        horario_busca = st.selectbox("Horário:", CONFIG_BANCA['horarios'])
        
        if st.button("🚀 Baixar & Salvar"):
            with st.spinner(f"Buscando {horario_busca}..."):
                b1, b2, msg = raspar_duque_avancado(data_busca, horario_busca)
                if b1 and b2:
                    st.session_state['auto_g1'] = b1; st.session_state['auto_g2'] = b2
                    if salvar_duque(b1, b2, horario_busca, data_busca):
                        st.session_state['tocar_som_salvar'] = True
                        st.success(f"Salvo: {b1}-{b2}"); time.sleep(1); st.rerun()
                else: st.error(f"Erro: {msg}")

    st.markdown("---")
    st.write("🔧 **Ajuste Manual**")
    c1, c2 = st.columns(2)
    with c1: b1_in = st.number_input("1º Bicho", 1, 25, st.session_state['auto_g1'])
    with c2: b2_in = st.number_input("2º Bicho", 1, 25, st.session_state['auto_g2'])
    if st.button("💾 GRAVAR MANUAL"):
        if salvar_duque(b1_in, b2_in, horario_busca, data_busca):
            st.session_state['tocar_som_salvar'] = True
            st.toast("Salvo Manualmente!", icon="✅"); time.sleep(0.5); st.rerun()
            
    if st.button("🗑️ APAGAR ÚLTIMO"):
        if deletar_ultimo():
            st.session_state['tocar_som_apagar'] = True
            st.toast("Apagado!", icon="🗑️"); time.sleep(0.5); st.rerun()

historico, ultimo_horario_salvo = carregar_dados()
st.title(f"👑 {CONFIG_BANCA['display_name']}")

if len(historico) > 50:
    ult = historico[-1]
    st.caption(f"📅 Último Registro: {ult[0]:02}-{ult[1]:02} ({ultimo_horario_salvo}) | Total Jogos: {len(historico)}")
    
    # --- GERAR DADOS ---
    # Verifica se o último jogo foi sequência
    is_sequencia = verificar_sequencia_bichos(ult)
    
    if is_sequencia:
        # ATIVA MODO SNIPER SEQUÊNCIA V8
        sniper_200 = gerar_sniper_sequencia_v8(historico)
        modo_sniper = "SEQUÊNCIA (V8)"
        css_sniper = "sniper-box-seq" # Roxo
        desc_sniper = "⚠️ Padrão Raro Detectado! Eliminando 75 duques improváveis."
    else:
        # ATIVA MODO NORMAL V6
        sniper_200 = gerar_sniper_top200_v6(historico)
        modo_sniper = "NORMAL (V6)"
        css_sniper = "sniper-box" # Verde
        desc_sniper = "Estratégia Camaleão: Adaptação ao último resultado."

    df_stress_real = calcular_tabela_stress_duque(historico)
    bt_results = executar_backtest_duque(historico)
    max_loss_rec = calcular_max_derrotas_duque(historico)

    # --- BOX DO SNIPER (DINÂMICO) ---
    st.markdown(f"""
    <div class="{css_sniper}">
        <div class="sniper-title">🎯 SNIPER DUQUE ({modo_sniper})</div>
        <div class="sniper-desc">{desc_sniper}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<div style='text-align:center;'><span class='max-loss-info'>📉 Pior Sequência (50 Jogos): {max_loss_rec} Derrotas</span></div>", unsafe_allow_html=True)
    
    if bt_results:
        cards_html = ""
        for res in reversed(bt_results):
            classe_res = "bt-win" if res['vitoria'] else "bt-loss"
            icon = "🟢" if res['vitoria'] else "❌"
            duque_str = f"{res['duque_real'][0]:02}-{res['duque_real'][1]:02}"
            # Adiciona ícone especial se foi um jogo de sequência
            extra_icon = "🔁" if res['tipo'] == "SEQUÊNCIA" else ""
            cards_html += f"<div class='bt-card {classe_res}'><div class='bt-icon'>{icon} {extra_icon}</div><div class='bt-num'>D: {duque_str}</div><div class='bt-label'>-{res['index']} Jogos</div></div>"
        final_html = f"<div class='backtest-container'>{cards_html}</div>"
        st.markdown(final_html, unsafe_allow_html=True)

    with st.expander("📋 Ver Lista de Jogos (200 Pares)", expanded=False):
        st.code(formatar_palpite_texto(sniper_200), language="text")

    st.markdown("---")
    
    # --- CENTRAL DE AVISOS (RADAR) ---
    st.subheader("🚨 Radar de Oportunidades (Setores)")
    cols_warnings = st.columns(2)
    warning_buffer = []

    for index, row in df_stress_real.iterrows():
        atraso = row['ATRASO']; rec_atraso = row['REC. ATRASO']; seq_atual = row['SEQ. ATUAL']; rec_seq = row['REC. SEQ. (V)']; setor = row['SETOR']
        
        if (rec_atraso - atraso) <= 1 and rec_atraso >= 5:
            msg = "**ESTOURADO!**" if atraso >= rec_atraso else "⚠️ Quase no Recorde"
            classe = "box-alerta" if atraso >= rec_atraso else "box-aviso"
            warning_buffer.append(f"<div class='{classe}'><h3>{setor}</h3><p>🕰️ Atraso: {atraso} (Rec: {rec_atraso}) - {msg}</p></div>")

        if (rec_seq - seq_atual) <= 1 and rec_seq >= 2:
            msg = "**ESTOURADO!**" if seq_atual >= rec_seq else "⚠️ Sequência Alta"
            classe = "box-inverso-critico" if seq_atual >= rec_seq else "box-inverso-atencao"
            warning_buffer.append(f"<div class='{classe}'><h3>{setor}</h3><p>🔥 Sequência: {seq_atual} (Rec: {rec_seq}) - {msg}</p></div>")

    if warning_buffer:
        for i, w in enumerate(warning_buffer):
            with cols_warnings[i % 2]: st.markdown(w, unsafe_allow_html=True)
    else: st.success("✅ Nenhum setor em estado crítico no momento.")

    st.markdown("---")
    
    st.subheader("📡 Gráfico de Setores")
    st.markdown("**Visual Recente (⬅️ Mais Novo):**")
    st.markdown(gerar_bolinhas_recentes_duque(historico), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_chart = df_stress_real.rename(columns={"% PRESENÇA": "PRESENCA", "SETOR": "CATEGORIA"})
    base = alt.Chart(df_chart).encode(theta=alt.Theta("PRESENCA", stack=True))
    pie = base.mark_arc(outerRadius=120, innerRadius=60).encode(
        color=alt.Color("CATEGORIA",
            scale=alt.Scale(domain=['SETOR 1 (S1)', 'SETOR 2 (S2)', 'SETOR 3 (S3)'], range=['#17a2b8', '#fd7e14', '#dc3545']),
            legend=None 
        ),
        order=alt.Order("PRESENCA", sort="descending"),
        tooltip=["CATEGORIA", alt.Tooltip("PRESENCA", format=".1f", title="% Presença")]
    )
    text = base.mark_text(radius=140).encode(
        text=alt.Text("PRESENCA", format=".1f"),
        order=alt.Order("PRESENCA", sort="descending"),
        color=alt.value("white")  
    )
    st.altair_chart(pie + text, use_container_width=True)
    
    st.markdown("**📉 Tabela de Stress:**")
    st.table(df_stress_real.set_index("SETOR"))

else:
    st.warning("⚠️ Base de dados insuficiente para o Sniper e Backtest. Adicione pelo menos 50 resultados na barra lateral.")
