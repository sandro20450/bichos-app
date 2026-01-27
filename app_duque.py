import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, timedelta
import pytz
import time
import re
from bs4 import BeautifulSoup

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E SOM ---
# =============================================================================
st.set_page_config(page_title="Central DUQUE (Tradicional)", page_icon="👑", layout="wide")

CONFIG_BANCA = {
    "display_name": "TRADICIONAL (Duque)",
    "logo_url": "https://cdn-icons-png.flaticon.com/512/1063/1063233.png", 
    "cor_fundo": "#2E004F", 
    "cor_texto": "#ffffff",
    "card_bg": "rgba(255, 255, 255, 0.1)",
    "url_site": "https://www.resultadofacil.com.br/resultados-loteria-tradicional-de-hoje",
    "horarios": "11:20 🔹 12:20 🔹 13:20 🔹 14:20 🔹 18:20 🔹 19:20 🔹 20:20 🔹 21:20 🔹 22:20 🔹 23:20"
}

# Inicialização de Estados
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_g1' not in st.session_state: st.session_state['auto_g1'] = 1
if 'auto_g2' not in st.session_state: st.session_state['auto_g2'] = 2
if 'auto_idx_h' not in st.session_state: st.session_state['auto_idx_h'] = 0

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'apagar':
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    else: return
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

st.markdown(f"""
<style>
    [data-testid="stAppViewContainer"] {{ background-color: {CONFIG_BANCA['cor_fundo']}; }}
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {CONFIG_BANCA['cor_texto']} !important; }}
    .stNumberInput input {{ color: white !important; }}
    [data-testid="stTable"] {{ color: white !important; background-color: transparent !important; }}
    .bola-s1 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    .bola-s2 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    .bola-s3 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    .bola-duque {{ display: inline-block; width: 60px; height: 35px; line-height: 35px; border-radius: 15px; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }}
    .metric-box-loss {{ background-color: #583b00; border: 1px solid #d4af37; color: #ffd700; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 5px; font-weight: bold; }}
    .metric-box-win {{ background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 5px; font-weight: bold; }}
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

def salvar_duque(b1, b2, horario):
    worksheet = conectar_planilha()
    if worksheet:
        try:
            data = datetime.now().strftime("%Y-%m-%d")
            worksheet.append_row([int(b1), int(b2), str(horario), data])
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

# --- FUNÇÃO NOVA: SCRAPING POR HORÁRIO ESPECÍFICO (V110) ---
def raspar_dupla_por_horario(url, horario_alvo):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200: return None, None, "Erro Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        for tabela in tabelas:
            if "1º" in tabela.get_text() or "Pri" in tabela.get_text():
                horario_encontrado = None
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev: 
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario_encontrado = m.group(1)
                
                if horario_encontrado == horario_alvo:
                    bicho1 = None
                    bicho2 = None
                    linhas = tabela.find_all('tr')
                    for linha in linhas:
                        colunas = linha.find_all('td')
                        if len(colunas) >= 3:
                            premio = colunas[0].get_text().strip()
                            grp_txt = colunas[2].get_text().strip()
                            if grp_txt.isdigit():
                                grp = int(grp_txt)
                                if (any(x in premio for x in ['1º', '1', 'Pri']) and "10" not in premio):
                                    bicho1 = grp
                                elif any(x in premio for x in ['2º', '2', 'Seg']):
                                    bicho2 = grp
                    if bicho1 and bicho2: return bicho1, bicho2, "Sucesso"
                    else: return None, None, "Horário encontrado, mas falta 1º ou 2º prêmio"
        return None, None, "Horário ainda não saiu"
    except Exception as e: return None, None, f"Erro: {e}"

# =============================================================================
# --- 3. LÓGICA DE SIMULAÇÃO (V112) ---
# =============================================================================
def gerar_universo_duques():
    todos = []
    for i in range(1, 26):
        for j in range(i, 26): todos.append((i, j))
    setor1 = [d for k, d in enumerate(todos) if k % 3 == 0]
    setor2 = [d for k, d in enumerate(todos) if k % 3 == 1]
    setor3 = [d for k, d in enumerate(todos) if k % 3 == 2]
    return todos, {"S1": setor1, "S2": setor2, "S3": setor3}

def formatar_palpite(lista_tuplas):
    lista_ordenada = sorted(lista_tuplas)
    texto = ""
    for p in lista_ordenada: texto += f"[{p[0]:02},{p[1]:02}], "
    return texto.rstrip(", ")

def calcular_inverso_otimizado(palpite_atual, historico):
    todos, _ = gerar_universo_duques()
    set_palpite = set(palpite_atual)
    pool_inverso = [d for d in todos if d not in set_palpite]
    hist_rev = historico[::-1]
    scores = {d: 0 for d in pool_inverso}
    c_curto = Counter(hist_rev[:20])
    c_medio = Counter(hist_rev[:50])
    for d in pool_inverso:
        scores[d] = (c_curto[d] * 3.0) + (c_medio[d] * 1.0)
    rank = sorted(pool_inverso, key=lambda x: scores[x], reverse=True)
    return rank[:126]

# --- ESTRATÉGIAS ---
def estrategia_bma(historico_slice):
    if len(historico_slice) < 10: return []
    _, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico_slice)
    atrasos = {"S1": 0, "S2": 0, "S3": 0}
    for nome, lista in mapa_setores.items():
        for i, sorteio in enumerate(reversed(historico_slice)):
            if sorteio in lista: atrasos[nome] = i; break
    recorte = historico_slice[-20:]
    freqs = {"S1": 0, "S2": 0, "S3": 0}
    for sorteio in recorte:
        for nome, lista in mapa_setores.items():
            if sorteio in lista: freqs[nome] += 1; break
    s_crise = max(atrasos, key=atrasos.get)
    s_trend = max(freqs, key=freqs.get)
    def get_best(lista, n): return sorted(lista, key=lambda x: c_duques[x], reverse=True)[:n]
    if s_crise == s_trend: return get_best(mapa_setores[s_crise], 126)
    else:
        p1 = get_best(mapa_setores[s_crise], 63)
        p2 = get_best(mapa_setores[s_trend], 63)
        return list(set(p1 + p2))

def estrategia_setorizada(historico_slice):
    if len(historico_slice) < 10: return []
    _, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico_slice)
    def get_best(lista, n): return sorted(lista, key=lambda x: c_duques[x], reverse=True)[:n]
    p1 = get_best(mapa_setores["S1"], 42); p2 = get_best(mapa_setores["S2"], 42); p3 = get_best(mapa_setores["S3"], 42)
    return list(set(p1 + p2 + p3))

def estrategia_dinamica(historico_slice):
    hist_rev = historico_slice[::-1]
    scores = {d: 0 for d in gerar_universo_duques()[0]}
    c_curto = Counter(hist_rev[:20]); c_medio = Counter(hist_rev[:50])
    for d, f in c_curto.items(): scores[d] += (f * 3.0)
    for d, f in c_medio.items(): scores[d] += (f * 1.0)
    return [d for d, s in sorted(scores.items(), key=lambda x: -x[1])][:126]

def estrategia_bunker(historico_slice):
    return [d for d, qtd in Counter(historico_slice).most_common()][:126]

def estrategia_iceberg(historico_slice):
    todos, _ = gerar_universo_duques()
    ultima_vez = {d: -1 for d in todos}
    for i, sorteio in enumerate(historico_slice):
        ultima_vez[sorteio] = i
    rank = sorted(ultima_vez.items(), key=lambda x: x[1])
    return [d for d, idx in rank][:126]

def rodar_simulacao_real(historico_completo, func_estrategia, n_jogos=50):
    if len(historico_completo) < n_jogos + 10: return pd.DataFrame(), 0, 0, 0, 0
    resultados = []
    max_loss = 0; temp_loss = 0; max_win = 0; temp_win = 0
    start_idx = len(historico_completo) - n_jogos
    for i in range(start_idx, len(historico_completo)):
        hist_momento = historico_completo[:i]
        res_real = historico_completo[i]
        palpite = func_estrategia(hist_momento)
        if res_real in palpite:
            status = "💚"; temp_win += 1
            if temp_loss > max_loss: max_loss = temp_loss
            temp_loss = 0 
        else:
            status = "❌"; temp_loss += 1
            if temp_win > max_win: max_win = temp_win
            temp_win = 0 
        if i >= len(historico_completo) - 20:
            resultados.append({"JOGO": f"#{len(historico_completo)-i}", "SAIU": f"{res_real[0]:02}-{res_real[1]:02}", "RES": status})
    if temp_loss > max_loss: max_loss = temp_loss
    if temp_win > max_win: max_win = temp_win
    curr_streak_loss = 0; curr_streak_win = 0
    df_res = pd.DataFrame(resultados[::-1])
    if not df_res.empty:
        for r in df_res.to_dict('records'):
            if r["RES"] == "❌": curr_streak_loss += 1
            else: break
        for r in df_res.to_dict('records'):
            if r["RES"] == "💚": curr_streak_win += 1
            else: break
    return df_res, max_loss, curr_streak_loss, max_win, curr_streak_win

def calcular_tabela_stress(historico):
    _, mapa = gerar_universo_duques()
    recorte = historico[-20:]
    tabela = []; atrasos = {}; freqs = {}
    for nome, lista in mapa.items():
        atraso = 0
        for x in reversed(historico):
            if x in lista: break
            atraso += 1
        atrasos[nome] = atraso
        count = sum(1 for x in recorte if x in lista)
        freqs[nome] = count
        max_atraso = 0; tmp_atraso = 0; max_win = 0; tmp_win = 0
        for x in historico:
            if x in lista:
                tmp_win += 1
                if tmp_atraso > max_atraso: max_atraso = tmp_atraso
                tmp_atraso = 0 
            else:
                tmp_atraso += 1
                if tmp_win > max_win: max_win = tmp_win
                tmp_win = 0 
        if tmp_atraso > max_atraso: max_atraso = tmp_atraso
        if tmp_win > max_win: max_win = tmp_win
        tabela.append({"SETOR": nome, "ATRASO": atraso, "REC. ATRASO": max_atraso, "REC. SEQ. (V)": max_win})
    return pd.DataFrame(tabela), max(atrasos, key=atrasos.get), max(freqs, key=freqs.get)

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image(CONFIG_BANCA['logo_url'], width=100)
    st.title("MENU DUQUE")
    
    st.link_button("🔗 Ver Site Oficial", CONFIG_BANCA['url_site'])
    st.markdown("---")

    horarios_list = [h.strip() for h in CONFIG_BANCA['horarios'].split('🔹')]
    h_sel = st.selectbox("Horário:", horarios_list, index=st.session_state['auto_idx_h'])
    
    if st.button(f"🔍 Checar {h_sel}"):
        with st.spinner(f"Buscando 1º e 2º prêmios das {h_sel}..."):
            b1, b2, msg = raspar_dupla_por_horario(CONFIG_BANCA['url_site'], h_sel)
            if b1 and b2:
                st.session_state['auto_g1'] = b1
                st.session_state['auto_g2'] = b2
                st.success(f"Encontrado: {b1}-{b2}")
            else:
                st.error(f"Erro: {msg}")

    c1, c2 = st.columns(2)
    with c1: b1_in = st.number_input("1º Bicho", 1, 25, st.session_state['auto_g1'])
    with c2: b2_in = st.number_input("2º Bicho", 1, 25, st.session_state['auto_g2'])
    
    if st.button("💾 SALVAR DUQUE", type="primary"):
        if salvar_duque(b1_in, b2_in, h_sel):
            st.session_state['tocar_som_salvar'] = True
            st.toast("Salvo!", icon="✅"); time.sleep(0.5); st.rerun()
            
    if st.button("🗑️ APAGAR ÚLTIMO"):
        if deletar_ultimo():
            st.session_state['tocar_som_apagar'] = True
            st.toast("Apagado!", icon="🗑️"); time.sleep(0.5); st.rerun()

historico, ultimo_horario_salvo = carregar_dados()
st.title(f"👑 {CONFIG_BANCA['display_name']}")

if len(historico) > 0:
    ult = historico[-1]
    st.info(f"📊 Jogos: {len(historico)} | 🏁 Último: {ult[0]:02}-{ult[1]:02} ({ultimo_horario_salvo})")
    
    df_stress, s_crise, s_trend = calcular_tabela_stress(historico)
    
    palp_bma = estrategia_bma(historico)
    palp_set = estrategia_setorizada(historico)
    palp_din = estrategia_dinamica(historico)
    palp_bun = estrategia_bunker(historico)
    palp_ice = estrategia_iceberg(historico)
    
    with st.spinner("Processando Simulação Real..."):
        bt_bma, ml_bma, cl_bma, mw_bma, cw_bma = rodar_simulacao_real(historico, estrategia_bma)
        bt_set, ml_set, cl_set, mw_set, cw_set = rodar_simulacao_real(historico, estrategia_setorizada)
        bt_din, ml_din, cl_din, mw_din, cw_din = rodar_simulacao_real(historico, estrategia_dinamica)
        bt_bun, ml_bun, cl_bun, mw_bun, cw_bun = rodar_simulacao_real(historico, estrategia_bunker)
        bt_ice, ml_ice, cl_ice, mw_ice, cw_ice = rodar_simulacao_real(historico, estrategia_iceberg)
    
    # --- CENTRAL DE ALERTAS (V114 - UI MATCHING) ---
    lista_alertas = []
    alertas_inversos = [] # Tuplas (Nome, Palpite)

    # Coleta de Alertas de Derrota
    if cl_bma >= (ml_bma - 1): lista_alertas.append(f"🔥 BMA: Derrotas ({cl_bma}) perto do Recorde ({ml_bma})!")
    if cl_set >= (ml_set - 1): lista_alertas.append(f"⚖️ SETOR: Derrotas ({cl_set}) perto do Recorde ({ml_set})!")
    if cl_din >= (ml_din - 1): lista_alertas.append(f"🚀 DINÂMICA: Derrotas ({cl_din}) perto do Recorde ({ml_din})!")
    if cl_bun >= (ml_bun - 1): lista_alertas.append(f"🧬 BUNKER: Derrotas ({cl_bun}) perto do Recorde ({ml_bun})!")
    if cl_ice >= (ml_ice - 1): lista_alertas.append(f"🥶 ICEBERG: Derrotas ({cl_ice}) perto do Recorde ({ml_ice})!")
    
    # Coleta de Alertas de Vitória (Inverso)
    if cw_bma >= (mw_bma - 1) and cw_bma > 0: alertas_inversos.append(("BMA", cw_bma, mw_bma, palp_bma))
    if cw_set >= (mw_set - 1) and cw_set > 0: alertas_inversos.append(("SETORIZADA", cw_set, mw_set, palp_set))
    if cw_din >= (mw_din - 1) and cw_din > 0: alertas_inversos.append(("DINÂMICA", cw_din, mw_din, palp_din))
    if cw_bun >= (mw_bun - 1) and cw_bun > 0: alertas_inversos.append(("BUNKER", cw_bun, mw_bun, palp_bun))
    if cw_ice >= (mw_ice - 1) and cw_ice > 0: alertas_inversos.append(("ICEBERG", cw_ice, mw_ice, palp_ice))

    # Exibição Unificada (Igual App Bichos)
    if lista_alertas or alertas_inversos:
        with st.expander("🚨 CENTRO DE ALERTAS", expanded=True):
            for alerta in lista_alertas:
                st.error(alerta)
            
            for nome, curr, max_w, palp in alertas_inversos:
                st.warning(f"🛑 CUIDADO {nome}: {curr} Vitórias. Perto do Recorde ({max_w}). Inverso Recomendado!")
                inv = calcular_inverso_otimizado(palp, historico)
                st.info(f"👻 Inverso {nome} (Top 126):")
                st.code(formatar_palpite(inv), language="text")
    
    # --- PAINEL PRINCIPAL ---
    tab1, tab2 = st.tabs(["📊 Setores & Estratégias", "🆚 Comparativo (3 Mesas)"])
    
    with tab1:
        _, mapa_vis = gerar_universo_duques()
        html_b = "<div>"
        for d in reversed(historico[-12:]):
            if d in mapa_vis["S1"]: c, s = "bola-s1", "S1"
            elif d in mapa_vis["S2"]: c, s = "bola-s2", "S2"
            else: c, s = "bola-s3", "S3"
            html_b += f"<div class='{c}'>{s}</div>"
        html_b += "</div>"
        st.markdown(html_b, unsafe_allow_html=True)
        
        with st.expander("🔍 Ver Composição dos Setores (S1, S2, S3)"):
            _, mapa_copy = gerar_universo_duques()
            st.caption("Copie os duques de cada setor para seus jogos:")
            st.text("🔵 Setor 1 (S1):")
            st.code(formatar_palpite(mapa_copy["S1"]), language="text")
            st.text("🟠 Setor 2 (S2):")
            st.code(formatar_palpite(mapa_copy["S2"]), language="text")
            st.text("🔴 Setor 3 (S3):")
            st.code(formatar_palpite(mapa_copy["S3"]), language="text")
            
        st.markdown("---")

        st.subheader("📡 Radar de Setores (Equilibrado)")
        st.table(df_stress)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🔥 BMA (Crise + Tendência)")
            st.caption(f"Mix: {s_crise} + {s_trend}")
            st.table(bt_bma)
            st.markdown(f'<div class="metric-box-loss">⚠️ Derrotas Recorde: {ml_bma}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Vitórias Recorde: {mw_bma}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE"): st.code(formatar_palpite(palp_bma), language="text")
        with c2:
            st.markdown("### ⚖️ Setorizada (42x3)")
            st.caption("Equilíbrio dos 3 setores")
            st.table(bt_set)
            st.markdown(f'<div class="metric-box-loss">⚠️ Derrotas Recorde: {ml_set}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Vitórias Recorde: {mw_set}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE"): st.code(formatar_palpite(palp_set), language="text")

    with tab2:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🚀 Dinâmica")
            st.caption("Os Quentes do Momento")
            st.table(bt_din)
            st.markdown(f'<div class="metric-box-loss">⚠️ Max Loss: {ml_din}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Max Win: {mw_din}</div>', unsafe_allow_html=True)
            with st.expander("Ver Dinâmica"): st.code(formatar_palpite(palp_din), language="text")
        with c2:
            st.markdown("### 🧬 Bunker")
            st.caption("Força Histórica (Fixa)")
            st.table(bt_bun)
            st.markdown(f'<div class="metric-box-loss">⚠️ Max Loss: {ml_bun}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Max Win: {mw_bun}</div>', unsafe_allow_html=True)
            with st.expander("Ver Bunker"): st.code(formatar_palpite(palp_bun), language="text")
        with c3:
            st.markdown("### 🥶 Iceberg")
            st.caption("Os 126 Mais Atrasados")
            st.table(bt_ice)
            st.markdown(f'<div class="metric-box-loss">⚠️ Max Loss: {ml_ice}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Max Win: {mw_ice}</div>', unsafe_allow_html=True)
            with st.expander("Ver Iceberg"): st.code(formatar_palpite(palp_ice), language="text")

    st.markdown("---")
    with st.expander("🛠️ Ferramentas Extras (Inverso Manual)"):
        st.write("Gere o **Inverso Otimizado** manualmente.")
        strat_choice = st.selectbox("Escolha a Estratégia Base:", ["DINÂMICA", "BUNKER", "ICEBERG"])
        if st.button("🔄 Gerar Inverso"):
            base = []
            if strat_choice == "DINÂMICA": base = palp_din
            elif strat_choice == "BUNKER": base = palp_bun
            elif strat_choice == "ICEBERG": base = palp_ice
            inv = calcular_inverso_otimizado(base, historico)
            st.info(f"Top 126 Jogando CONTRA {strat_choice}:")
            st.code(formatar_palpite(inv), language="text")

    st.markdown("---")
    with st.expander("🕒 Grade de Horários"):
        st.table(pd.DataFrame({"HORÁRIOS": [CONFIG_BANCA['horarios']]}))
else:
    st.warning("⚠️ Adicione os primeiros resultados na barra lateral.")
