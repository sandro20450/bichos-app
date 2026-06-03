import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# --- 1. CONFIGURAÇÕES E CSS DA INTERFACE ---
# =============================================================================
st.set_page_config(page_title="Pentágono V65.45 - Teto Histórico 10D", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; border: 1px solid #444; background-color: #111; }
.rodape-tatico { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #000; color: #ffcc00; text-align: center; padding: 10px; font-size: 14px; border-top: 2px solid #ff4b4b; z-index: 9999; font-weight: bold;}
.block-container { padding-bottom: 80px; }
div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; border: 1px solid #555; }
.alerta-verde { background-color: rgba(0,255,0,0.1); border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.sniper-titulo { font-size: 13px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); }
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; }
.sniper-valor { font-weight: bold; font-size: 15px; color: #fff; }
</style>
""", unsafe_allow_html=True)

def aplicar_estilos_ui(cor_neon):
    st.markdown(f"""
    <style>
        .titulo-container {{ display: flex; align-items: center; gap: 15px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;}}
        .titulo-texto {{ margin: 0; font-size: 34px; font-weight: bold; color: #ffffff; }}
        .radar-container {{ position: relative; width: 34px; height: 34px; display: flex; justify-content: center; align-items: center; }}
        .radar-core {{ position: absolute; width: 10px; height: 10px; background-color: {cor_neon}; border-radius: 50%; box-shadow: 0 0 10px {cor_neon}; z-index: 2; }}
        .radar-pulse {{ position: absolute; width: 10px; height: 10px; border: 2px solid {cor_neon}; border-radius: 50%; z-index: 1; animation: radar-ping 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite; }}
        @keyframes radar-ping {{ 0% {{ width: 10px; height: 10px; opacity: 1; }} 100% {{ width: 45px; height: 45px; opacity: 0; }} }}
    </style>
    """, unsafe_allow_html=True)

def configurar_ui_pagina(titulo, cor):
    aplicar_estilos_ui(cor)
    st.markdown(f"""<div class="titulo-container"><div class="radar-container"><div class="radar-core"></div><div class="radar-pulse"></div></div><h1 class="titulo-texto">{titulo}</h1></div>""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {"Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"}
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

# =============================================================================
# --- 2. COMUNICAÇÃO COM BASE DE DADOS ---
# =============================================================================
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("CentralBichos")
    except: return None

@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_em_memoria(banca_nome):
    sh = conectar_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(MAPA_ABAS[banca_nome])
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        df = pd.DataFrame(dados[1:])
        df = df.iloc[:, :7]
        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
        df = df[df["P1"].astype(str).str.strip() != ""]
        return df
    except: return pd.DataFrame()

def exibir_banner_sorteio(df, banca):
    if not df.empty:
        ult_nome = str(df.iloc[-1]["Sorteio"])
        st.markdown(f"""<div style="background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px;"><span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO LIDA DA PLANILHA:</span><br><span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span></div>""", unsafe_allow_html=True)

# =============================================================================
# --- 3. MOTORES DE ANÁLISE ---
# =============================================================================
def processar_anomalia_duplas(df, coluna):
    # Motor Reconstruído: Análise Profunda de Histórico e Padrões Ocultos
    valores = df[coluna].astype(str).tolist()
    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
    if len(validos) < 2: return None
    
    # 1. Rastrear o Histórico Completo de Frequências
    streak_counts = {}
    temp_streak = 0
    # Percorre toda a história (do passado para o presente) para achar os padrões
    for val in validos:
        c = val[-3:]
        if len(set(c)) < 3: # É dupla ou tripla
            temp_streak += 1
        else:
            if temp_streak > 0:
                streak_counts[temp_streak] = streak_counts.get(temp_streak, 0) + 1
                temp_streak = 0
                
    # Conta a sequência atual que ainda está viva na ponta da lista
    current_streak = temp_streak
    if current_streak > 0:
        streak_counts[current_streak] = streak_counts.get(current_streak, 0) + 1
        
    # 2. Gera o Ataque se o gatilho foi atingido hoje
    if current_streak >= 2:
        seen_digits_set = set(); seen_digits_list = []; cold_digit = None
        for val in reversed(validos):
            for char in val[-3:]:
                d = int(char)
                if d not in seen_digits_set: 
                    seen_digits_set.add(d)
                    seen_digits_list.append(str(d))
                if len(seen_digits_set) == 9: 
                    cold_digit = (set(range(10)) - seen_digits_set).pop()
                    break
            if cold_digit is not None: break
        
        if cold_digit is not None:
            excluido = seen_digits_list[4] # O Ponto Cego (5º número)
            seen_digits_list.append(str(cold_digit)) # Junta o Frio para formar os 10D
            seq_str = " - ".join(seen_digits_list)
            
            # Descobre o Recorde Histórico absoluto do prêmio
            max_historico = max(streak_counts.keys()) if streak_counts else current_streak
            
            return cold_digit, seq_str, excluido, current_streak, max_historico, streak_counts
            
    return None

def gerar_matrizes_taticas():
    esquadroes = []; cms = [{'c_min': 0, 'c_max': 499, 'm_min': 0, 'm_max': 4999}, {'c_min': 500, 'c_max': 999, 'm_min': 5000, 'm_max': 9999}]
    for cm in cms:
        for g in range(1, 14): esquadroes.append({'alvos': set(range(g, g+13)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G13: {str(g).zfill(2)}-{str(g+12).zfill(2)}", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(51, 100))|{0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS", 'lim': 9, **cm})
    
    esquadroes.extend([
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ])
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo, c_min, c_max, m_min, m_max = cfg['alvos'], cfg['modo'], cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
    cur_p, cur_c, cur_m, max_p, max_c, max_m = 0, 0, 0, 0, 0, 0
    valores = df_analise[coluna].astype(str).tolist()
    for val in valores:
        milhar = val.strip().zfill(4)
        if milhar in ["----", "0nan", "nan", ""]: continue
        try: m = int(milhar); c = int(milhar[-3:]); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: continue
        g = 25 if d == 0 else math.ceil(d/4)
        hit_p = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos) or (modo == 'centena' and c in alvos)
        
        if hit_p: cur_p = 0
        else: cur_p += 1; max_p = max(max_p, cur_p)
        if (c_min <= c <= c_max): cur_c = 0
        else: cur_c += 1; max_c = max(max_c, cur_c)
        if (m_min <= m <= m_max): cur_m = 0
        else: cur_m += 1; max_m = max(max_m, cur_m)
    return cur_p, cur_c, cur_m, max_p, max_c, max_m

def deduplicar_alvos(lista):
    vistos = set(); resultado = []
    for item in lista:
        ta = item.get('tipo_ataque', '')
        if "MILHAR" in ta: sig = f"{item['banca']}_{item['premio']}_M_{item['cfg']['m_min']}"
        elif "CENTENA" in ta: sig = f"{item['banca']}_{item['premio']}_C_{item['cfg']['c_min']}"
        else: sig = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}"
        if sig not in vistos: vistos.add(sig); resultado.append(item)
    return resultado

# =============================================================================
# --- 4. INTERFACE GRÁFICA (PÁGINAS) ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V65.45")
    if st.button("FORÇAR ATUALIZAÇÃO", type="primary"):
        st.cache_data.clear()
        st.success("✅ Memória do radar limpa!")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Scanner de Raio-X"])

if menu == "🏠 Visão Geral (Home)":
    configurar_ui_pagina("Central AWACS", "#00ffff")
    
    if st.button("INICIAR VARREDURA GLOBAL", type="primary"):
        with st.spinner("Processando histórico e buscando alvos no Teto..."):
            alvos_teto = []
            alertas_duplas = [] 
            todos_esq = gerar_matrizes_taticas()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    
                    # Rastreio do Gatilho Especial de Duplas Seguidas
                    res_duplas = processar_anomalia_duplas(df, col)
                    if res_duplas:
                        cold_d, seq_s, excl, streak, max_hist, historico = res_duplas
                        alertas_duplas.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "cold_digit": cold_d, "seq": seq_s, "excluido": excl, "streak": streak, "max_hist": max_hist, "historico": historico})

                metrics_cache = {}
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        metrics_cache[(cfg['nome'], cfg['c_min'], col)] = (ap, ac, am, mp, mc, mm)
                
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        ap, ac, am, mp, mc, mm = metrics_cache[(cfg['nome'], cfg['c_min'], col)]
                        ap_lim = cfg['lim'] 
                        
                        estado_alvo = None; prio = 99; tipo_ataque = ""; alerta_html = ""
                        
                        # APENAS TETO (SEM APROXIMAÇÃO)
                        if am >= 9 and ac >= 9 and ap >= ap_lim: estado_alvo = "TETO"; prio = 1; tipo_ataque = "TOTAL"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE TOTAL (G+C+M) - TETO ATINGIDO</div>"
                        elif am >= 9: estado_alvo = "TETO"; prio = 2; tipo_ataque = "MILHAR"; alerta_html = f"<div class='alerta-verde'>🔵 ATAQUE MILHAR ({am}x) - TETO ATINGIDO</div>"
                        elif ac >= 9: estado_alvo = "TETO"; prio = 3; tipo_ataque = "CENTENA"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA ({ac}x) - TETO ATINGIDO</div>"
                        elif cfg['modo'] == 'unidade' and ap >= 9: estado_alvo = "TETO"; prio = 4; tipo_ataque = "UNIDADE"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE UNIDADE - TETO ATINGIDO</div>"
                        elif ap >= ap_lim: estado_alvo = "TETO"; prio = 5; tipo_ataque = "ALVO_PRINCIPAL"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE FORTE ({cfg['modo'].upper()}) - TETO ATINGIDO</div>"

                        if estado_alvo == "TETO":
                            op_data = {"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_html, "cfg": cfg, "tipo_ataque": tipo_ataque}
                            alvos_teto.append(op_data)
            
        alvos_teto = deduplicar_alvos(sorted(alvos_teto, key=lambda x: (x['prio'], -max(x['ap'], x['ac'], x['am']))))

        # --- EXIBIÇÃO NA TELA ---
        if alertas_duplas:
            st.error(f"🚨 ANOMALIA DETECTADA: {len(alertas_duplas)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alertas_duplas):
                streak_count = op['streak']
                cor_box = "#ffff00" if streak_count == 2 else "#00ff00"
                sombra_cor = "255,255,0" if streak_count == 2 else "0,255,0"
                
                # Formata a string de frequência dos padrões ocultos
                freq_str = f"2x: {op['historico'].get(2, 0)}v"
                if 3 in op['historico']: freq_str += f" | 3x: {op['historico'].get(3, 0)}v"
                if 4 in op['historico']: freq_str += f" | 4x: {op['historico'].get(4, 0)}v"
                if op['max_hist'] > 4: freq_str += f" | {op['max_hist']}x: {op['historico'].get(op['max_hist'], 0)}v"
                
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="home-box" style="border-color:{cor_box}; box-shadow: 0 0 15px rgba({sombra_cor},0.3);">
                        <div class="home-banca">🏦 {op['banca']}</div>
                        <div class="home-premio">🏆 {op['premio']}</div>
                        <div class="sniper-titulo" style="color:{cor_box};">🚨 GATILHO: {streak_count}x DUPLAS SEGUIDAS</div>
                        <div style="font-size:11px; background:rgba(0,0,0,0.5); padding:6px; border-radius:5px; margin-bottom:8px; text-align:left; color:#ccc;">
                            <b style='color:#ffcc00;'>📊 HISTÓRICO DESTE PRÊMIO:</b><br>
                            Recorde Máximo: <b style='color:#fff;'>{op['max_hist']}x</b><br>
                            Freq: {freq_str}
                        </div>
                        <div class="sniper-dado" style="margin-top:5px;"><b>Ataque Recomendado (10 Digitos):</b></div>
                        <div class="sniper-valor" style="color:#00ff00; font-size:18px;">{op['seq']}</div>
                        <div style="font-size:12px; color:{cor_box}; margin-top:8px; font-weight:bold;">❌ Excluir Ponto Cego: {op['excluido']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("---") 

        if alvos_teto:
            st.success(f"🎯 ALVOS CRÍTICOS (TETO ATINGIDO): {len(alvos_teto)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alvos_teto):
                c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                ta = op.get('tipo_ataque', '')
                css_class = f"home-box-seq"
                
                if ta == 'UNIDADE': lbl_alvo, titulo, cm_html = "Unidade", op['cfg']['nome'], ""
                elif ta == 'MILHAR': lbl_alvo, titulo, cm_html = "Filtro", f"M: {str(m_min).zfill(4)} A {str(m_max).zfill(4)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                elif ta == 'CENTENA': lbl_alvo, titulo, cm_html = "Filtro", f"C: {str(c_min).zfill(3)} A {str(c_max).zfill(3)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                else: lbl_alvo, titulo, cm_html = "Atraso", op['cfg']['nome'], f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                    
                with cols[idx % 3]:
                    st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}</div><div class="sniper-valor" style="color:#00ff00;">{op['ap']}x</div><div style="font-size:11px; color:#aaa;">{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
            st.markdown("---") 

        if not alvos_teto and not alertas_duplas: 
            st.success("🟢 MODO STEALTH: Não temos alvos no teto no momento. O radar está silencioso.")

elif menu == "🎯 Scanner de Raio-X":
    configurar_ui_pagina("Scanner de Raio-X", "#ffcc00")
    col1, col2, col3 = st.columns(3)
    with col1: banca_rx = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    with col2: categoria_rx = st.selectbox("Categoria:", ["Grupo (1 a 25)", "Dezena (00 a 99)", "Unidade (0 a 9)", "Filtros de Massa"])
    with col3:
        if categoria_rx == "Grupo (1 a 25)": alvo_rx = st.number_input("Qual?", min_value=1, max_value=25, value=1)
        elif categoria_rx == "Dezena (00 a 99)": alvo_rx = st.number_input("Qual?", min_value=0, max_value=99, value=0)
        elif categoria_rx == "Unidade (0 a 9)": alvo_rx = st.number_input("Qual?", min_value=0, max_value=9, value=0)
            
    if categoria_rx != "Filtros de Massa":
        if st.button("EXECUTAR RAIO-X INDIVIDUAL", type="primary"):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty: st.error("Sem dados.")
            else:
                exibir_banner_sorteio(df, banca_rx)
                cfg_rx = {'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999, 'lim': 0}
                if categoria_rx == "Grupo (1 a 25)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'grupo'; cfg_rx['nome'] = f"GRUPO {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Dezena (00 a 99)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'dezena'; cfg_rx['nome'] = f"DEZENA {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Unidade (0 a 9)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'unidade'; cfg_rx['nome'] = f"UNIDADE {alvo_rx}"
                
                cols_rx = st.columns(5)
                for i, col in enumerate(COLUNAS_DF):
                    ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg_rx)
                    with cols_rx[i]:
                        st.markdown(f"""<div class="home-box"><div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div><div class="sniper-valor" style="color:#ff4b4b;">{ap}x</div><div>Rec: {mp}x</div></div>""", unsafe_allow_html=True)
    else:
        if st.button("GERAR PLANILHA DE MASSA", type="primary"):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty: st.error("Sem dados.")
            else:
                filtros_lista = [
                    ("Milhares Baixas (0000-4999)", {'alvos': set(range(0, 5000)), 'modo': 'milhar', 'lim': 9}),
                    ("Milhares Altas (5000-9999)", {'alvos': set(range(5000, 10000)), 'modo': 'milhar', 'lim': 9}),
                    ("Centenas Baixas (000-499)", {'alvos': set(range(0, 500)), 'modo': 'centena', 'lim': 9}),
                    ("Centenas Altas (500-999)", {'alvos': set(range(500, 1000)), 'modo': 'centena', 'lim': 9}),
                    ("Grupos Ímpares", {'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'lim': 9}),
                    ("Grupos Pares", {'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'lim': 9}),
                    ("Dezenas Baixas (01-50)", {'alvos': set(range(1, 51)), 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Altas (51-00)", {'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Ímpares", {'alvos': {x for x in range(100) if x % 2 != 0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Pares", {'alvos': {x for x in range(100) if x % 2 == 0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Miolo (26-75)", {'alvos': set(range(26, 76)), 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Bordas", {'alvos': set(range(1, 26)) | set(range(76, 100)) | {0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Finais Baixos (1-5)", {'alvos': {x for x in range(100) if x % 10 in [1, 2, 3, 4, 5]}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Finais Altos (6-0)", {'alvos': {x for x in range(100) if x % 10 in [6, 7, 8, 9, 0]}, 'modo': 'dezena', 'lim': 9}),
                    ("Unidades Baixas (1-5)", {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Altas (6-0)", {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Ímpares", {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Pares", {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'lim': 9})
                ]
                
                dados_tabela = []
                for nome_filtro, cfg in filtros_lista:
                    cfg.update({'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999})
                    linha = {"FILTRO": nome_filtro, "TETO": cfg['lim']}
                    for i, col in enumerate(COLUNAS_DF):
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        linha[TITULOS_PREMIOS[i]] = f"{ap}x (R:{mp})"
                    dados_tabela.append(linha)
                
                exibir_banner_sorteio(df, banca_rx)
                st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)

st.markdown("""<div class="rodape-tatico">🎯 GATILHOS ATIVOS: M/C Baixas/Altas=9x | Dezenas, Unidades e Filtros=9x | 13 Grupos=9x | Gatilho Duplas (10D + Ponto Cego)</div>""", unsafe_allow_html=True)
