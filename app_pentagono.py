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
# --- 1. CONFIGURAÇÕES E CSS DE GLASSMORPHISM (V65.51) ---
# =============================================================================
st.set_page_config(page_title="Pentágono V65.51 - Síntese Preditiva", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07090f 0%, #000000 100%);
    background-image: 
        radial-gradient(at 0% 0%, rgba(0, 255, 255, 0.1) 0px, transparent 40%),
        radial-gradient(at 100% 100%, rgba(255, 0, 255, 0.1) 0px, transparent 40%);
    background-attachment: fixed;
}
.home-box { 
    border-radius: 12px; padding: 16px; margin-bottom: 15px; text-align: center; 
    background: rgba(20, 25, 30, 0.4); 
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5); transition: all 0.3s ease;
}
.home-box:hover {
    transform: translateY(-4px); background: rgba(30, 35, 45, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.7);
}
.rodape-tatico { 
    position: fixed; bottom: 0; left: 0; width: 100%; 
    background: rgba(5, 5, 5, 0.7); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
    color: #ffcc00; text-align: center; padding: 10px; font-size: 14px; 
    border-top: 1px solid rgba(255, 255, 255, 0.1); z-index: 9999; font-weight: bold;
}
.block-container { padding-bottom: 80px; }
div.stButton > button { 
    width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; 
    background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1); color: #ffffff; transition: all 0.3s ease;
}
div.stButton > button:hover {
    background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(0, 255, 255, 0.4);
    box-shadow: 0 0 15px rgba(0, 255, 255, 0.2); color: #00ffff;
}
.alerta-verde { background: rgba(0,255,0,0.05); backdrop-filter: blur(4px); border: 1px solid rgba(0,255,0,0.3); color: #00ff00; padding: 6px; border-radius: 6px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.sniper-titulo { font-size: 13px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; background: rgba(0,0,0,0.2); border-radius: 4px;}
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; }
.sniper-valor { font-weight: bold; font-size: 16px; color: #fff; text-shadow: 0 0 10px currentColor; letter-spacing: 1px;}
</style>
""", unsafe_allow_html=True)

def aplicar_estilos_ui(cor_neon):
    st.markdown(f"""
    <style>
        .titulo-container {{ display: flex; align-items: center; gap: 15px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;}}
        .titulo-texto {{ margin: 0; font-size: 34px; font-weight: bold; color: #ffffff; text-shadow: 0 0 15px {cor_neon};}}
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
# --- 2. COMUNICAÇÃO COM BASE DE DADOS E COLETA ---
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
        st.markdown(f"""
        <div style="background: rgba(0, 255, 0, 0.05); backdrop-filter: blur(5px); border: 1px solid rgba(0, 255, 0, 0.2); padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO LIDA DA PLANILHA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold; text-shadow: 0 0 5px rgba(255,255,255,0.5);'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# --- 3. MOTORES DE ANÁLISE ---
# =============================================================================
def gerar_milhares_preditivas(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
    if not validos: return "0000", "0000", "0000"

    sniper = ""; vulcao = ""; mutante = ""
    recentes = validos[-100:] if len(validos) >= 100 else validos

    for pos in range(4):
        delays = {str(d): -1 for d in range(10)}
        for d in range(10):
            delay = 0
            for val in reversed(validos):
                if len(val) >= 4 and val[pos] == str(d): break
                delay += 1
            delays[str(d)] = delay
        coldest = max(delays, key=delays.get)

        freqs = {str(d): 0 for d in range(10)}
        for val in recentes:
            if len(val) >= 4: freqs[val[pos]] += 1
        hottest = max(freqs, key=freqs.get)

        sniper += coldest
        vulcao += hottest
        mutante += coldest if pos % 2 == 0 else hottest

    return sniper, vulcao, mutante

def get_10d_state(validos_slice):
    seen_set = set(); seen_list = []; cold = None
    for val in reversed(validos_slice):
        for char in val[-3:]:
            d = int(char)
            if d not in seen_set: 
                seen_set.add(d); seen_list.append(str(d))
            if len(seen_set) == 9: 
                cold = (set(range(10)) - seen_set).pop()
                break
        if cold is not None: break
    if cold is not None:
        seen_list.append(str(cold))
        return seen_list
    return []

def metricas_duplas_raiox(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
    if len(validos) < 2: return 0, 0
    streak_counts = {}; temp_streak = 0
    for val in validos:
        c = val[-3:]
        if len(set(c)) < 3: temp_streak += 1
        else:
            if temp_streak > 0: streak_counts[temp_streak] = streak_counts.get(temp_streak, 0) + 1
            temp_streak = 0
    current_streak = temp_streak
    max_historico = max(list(streak_counts.keys()) + [current_streak]) if streak_counts else current_streak
    return current_streak, max_historico

def processar_anomalia_duplas(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
    if len(validos) < 2: return None
    
    streak_counts = {}
    temp_streak = 0
    for val in validos:
        c = val[-3:]
        if len(set(c)) < 3: 
            temp_streak += 1
        else:
            if temp_streak > 0:
                streak_counts[temp_streak] = streak_counts.get(temp_streak, 0) + 1
                temp_streak = 0
                
    current_streak = temp_streak
    
    if current_streak >= 2:
        current_10d_list = get_10d_state(validos)
        
        if current_10d_list:
            excluido_padrao = current_10d_list[4] 
            seq_str = " - ".join(current_10d_list)
            
            max_historico = max(list(streak_counts.keys()) + [current_streak]) if streak_counts else current_streak
            total_reached = sum(v for k, v in streak_counts.items() if k >= current_streak) + 1
            broke_at_current = streak_counts.get(current_streak, 0)
            prob_break = (broke_at_current / total_reached) * 100 if total_reached > 0 else 0
            prob_cont = 100 - prob_break
            trend_text = f"Quebra Agora: {prob_break:.1f}% | Avança pra {current_streak+1}x: {prob_cont:.1f}%"
            
            past_breaks = []
            temp = 0
            for i in range(len(validos)):
                c = validos[i][-3:]
                if len(set(c)) < 3:
                    temp += 1
                else:
                    if temp >= 2:
                        state_before = get_10d_state(validos[:i])
                        if state_before:
                            past_breaks.append({'state': state_before, 'breaker': c})
                    temp = 0
            
            best_match = None
            best_score = -1
            
            for pb in past_breaks:
                score = sum(1 for a, b in zip(pb['state'], current_10d_list) if a == b)
                if score > best_score:
                    best_score = score
                    best_match = pb
                    
            cruzamento_html = ""
            melhor_exclusao = excluido_padrao
            
            if best_match and best_score >= 0:
                cent_quebra = best_match['breaker']
                digitos_quebra = list(set(cent_quebra))
                
                detalhes = []
                for d in digitos_quebra:
                    if d in current_10d_list:
                        idx = current_10d_list.index(d)
                        if idx == 0: forca = 85; desc = "Saturado (1º da fila)"; cor = "#ffaa00"; icon="🟠"
                        elif idx == 4: forca = 99; desc = "Ponto Cego Atual"; cor = "#ff4b4b"; icon="🔴"
                        elif idx == 9: forca = 10; desc = "Dígito Frio"; cor = "#888888"; icon="⚪"
                        elif idx < 4: forca = 70; desc = f"Quente (Posição {idx+1})"; cor = "#ffff00"; icon="🟡"
                        else: forca = 40; desc = f"Morno/Frio (Posição {idx+1})"; cor = "#00ff00"; icon="🟢"
                        detalhes.append({'digito': d, 'forca': forca, 'desc': desc, 'cor': cor, 'icon': icon})
                
                detalhes.sort(key=lambda x: x['forca'], reverse=True)
                
                cruzamento_html += f"<div style='background:rgba(0,0,0,0.4); padding:10px; border-radius:6px; margin-top:10px; border:1px solid rgba(255,255,255,0.1); text-align:left; font-size:12px;'>"
                cruzamento_html += f"<b style='color:#00ffff;'>👻 RASTREIO FANTASMA (Simil. {best_score*10}%)</b><br>"
                cruzamento_html += f"<span style='color:#ccc;'>Centena do passado: <b>{cent_quebra}</b></span><br>"
                cruzamento_html += f"<b style='color:#fff; margin-top:5px; display:inline-block;'>🔬 CRUZAMENTO TÁTICO:</b><br>"
                
                primeiro = True
                for item in detalhes:
                    cruzamento_html += f"{item['icon']} Dígito <b style='color:{item['cor']};'>{item['digito']}</b>: {item['desc']} (Força: {item['forca']}%)<br>"
                    if primeiro:
                        melhor_exclusao = item['digito']
                        primeiro = False
                        
                cruzamento_html += f"<div style='margin-top:8px; color:#ff4b4b; font-weight:bold; font-size:13px; text-align:center;'>❌ DECISÃO IA: Excluir {melhor_exclusao}</div></div>"
            else:
                cruzamento_html = f"<div style='margin-top:10px; color:#ff4b4b; font-weight:bold;'>❌ DECISÃO PADRÃO P. CEGO: Excluir {melhor_exclusao}</div>"
            
            return current_10d_list[-1], seq_str, melhor_exclusao, current_streak, max_historico, streak_counts, trend_text, cruzamento_html, ""
            
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
        
        hit_p = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos) or (modo == 'centena' and c in alvos) or (modo == 'milhar' and m in alvos)
        
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

def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        resultados = []; vistos_assinaturas = set() 
        for tab in soup.find_all('table'):
            th_tag = tab.find('th')
            texto_alvo = (th_tag.get_text().upper() if th_tag else "") + " " + (tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b']).get_text().upper() if tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b']) else "")
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            nome = f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora and match_hora.group(1) else "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                assinatura = "".join(milhares)
                if assinatura not in vistos_assinaturas and milhares[0] != "----":
                    vistos_assinaturas.add(assinatura); resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 4. INTERFACE GRÁFICA (PÁGINAS) ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V65.51")
    if st.button("FORÇAR ATUALIZAÇÃO", type="primary"):
        st.cache_data.clear()
        st.success("✅ Memória do radar limpa!")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Scanner de Raio-X", "📡 Extração Central"])

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
                    
                    res_duplas = processar_anomalia_duplas(df, col)
                    if res_duplas:
                        cold_d, seq_s, excl, streak, max_hist, historico, trend_txt, cruz_html, _ = res_duplas
                        m_sniper, m_vulcao, m_mutante = gerar_milhares_preditivas(df, col)
                        alertas_duplas.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "cold_digit": cold_d, "seq": seq_s, "excluido": excl, "streak": streak, "max_hist": max_hist, "historico": historico, "trend": trend_txt, "cruzamento_html": cruz_html, "sniper": m_sniper, "vulcao": m_vulcao, "mutante": m_mutante})

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
                        
                        if am >= 9 and ac >= 9 and ap >= ap_lim: estado_alvo = "TETO"; prio = 1; tipo_ataque = "TOTAL"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE TOTAL (G+C+M) - TETO ATINGIDO</div>"
                        elif am >= 9: estado_alvo = "TETO"; prio = 2; tipo_ataque = "MILHAR"; alerta_html = f"<div class='alerta-verde'>🔵 ATAQUE MILHAR ({am}x) - TETO ATINGIDO</div>"
                        elif ac >= 9: estado_alvo = "TETO"; prio = 3; tipo_ataque = "CENTENA"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA ({ac}x) - TETO ATINGIDO</div>"
                        elif cfg['modo'] == 'unidade' and ap >= 9: estado_alvo = "TETO"; prio = 4; tipo_ataque = "UNIDADE"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE UNIDADE - TETO ATINGIDO</div>"
                        elif ap >= ap_lim: estado_alvo = "TETO"; prio = 5; tipo_ataque = "ALVO_PRINCIPAL"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE FORTE ({cfg['modo'].upper()}) - TETO ATINGIDO</div>"

                        if estado_alvo == "TETO":
                            m_sniper, m_vulcao, m_mutante = gerar_milhares_preditivas(df, col)
                            alerta_html += f"<div style='background:rgba(0,0,0,0.4); padding:8px; border-radius:6px; margin-top:8px; border: 1px solid rgba(255,255,255,0.1);'><b style='color:#ffcc00; font-size:11px;'>🤖 SÍNTESE IA DO PRÊMIO:</b><br><span style='font-size:11px;'>🧊 Sniper: <b style='color:#00ffff;'>{m_sniper}</b> | 🔥 Vulcão: <b style='color:#ff4b4b;'>{m_vulcao}</b><br>🧬 Mutante: <b style='color:#00ff00;'>{m_mutante}</b></span></div>"

                            op_data = {"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_html, "cfg": cfg, "tipo_ataque": tipo_ataque}
                            alvos_teto.append(op_data)
            
        alvos_teto = deduplicar_alvos(sorted(alvos_teto, key=lambda x: (x['prio'], -max(x['ap'], x['ac'], x['am']))))

        if alertas_duplas:
            st.error(f"🚨 ANOMALIA DETECTADA: {len(alertas_duplas)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alertas_duplas):
                streak_count = op['streak']
                cor_box = "#ffff00" if streak_count == 2 else "#00ff00"
                sombra_cor = "255,255,0" if streak_count == 2 else "0,255,0"
                
                freq_str = f"2x: {op['historico'].get(2, 0)}v"
                if 3 in op['historico']: freq_str += f" | 3x: {op['historico'].get(3, 0)}v"
                if 4 in op['historico']: freq_str += f" | 4x: {op['historico'].get(4, 0)}v"
                
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="home-box" style="border-color: rgba({sombra_cor}, 0.5); box-shadow: 0 0 20px rgba({sombra_cor},0.15);">
                        <div class="home-banca" style="color: #fff;">🏦 {op['banca']}</div>
                        <div class="home-premio" style="color: #ddd;">🏆 {op['premio']}</div>
                        <div class="sniper-titulo" style="color:{cor_box};">🚨 GATILHO: {streak_count}x DUPLAS SEGUIDAS</div>
                        <div style="font-size:11px; background:rgba(0,0,0,0.3); padding:8px; border-radius:6px; margin-bottom:8px; text-align:left; color:#ccc; border: 1px solid rgba(255,255,255,0.05);">
                            <b style='color:#ffcc00;'>📊 HISTÓRICO DESTE PRÊMIO:</b><br>
                            Recorde Máximo: <b style='color:#fff;'>{op['max_hist']}x</b><br>
                            Freq: {freq_str}<br>
                            <b style='color:#00ffff;'>📈 TENDÊNCIA: {op['trend']}</b>
                        </div>
                        <div class="sniper-dado" style="margin-top:5px;"><b>Ataque Recomendado (10 Digitos):</b></div>
                        <div class="sniper-valor" style="color:#00ff00;">{op['seq']}</div>
                        {op['cruzamento_html']}
                        <div style='background:rgba(0,0,0,0.4); padding:8px; border-radius:6px; margin-top:8px; border: 1px solid rgba(255,255,255,0.1); text-align:left; font-size:11px;'>
                            <b style='color:#ffcc00;'>🤖 SÍNTESE IA DO PRÊMIO:</b><br>
                            🧊 Sniper: <b style='color:#00ffff;'>{op['sniper']}</b> | 🔥 Vulcão: <b style='color:#ff4b4b;'>{op['vulcao']}</b><br>
                            🧬 Mutante: <b style='color:#00ff00;'>{op['mutante']}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("---") 

        if alvos_teto:
            st.success(f"🎯 ALVOS CRÍTICOS (TETO ATINGIDO): {len(alvos_teto)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alvos_teto):
                c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                ta = op.get('tipo_ataque', '')
                
                if ta == 'UNIDADE': lbl_alvo, titulo, cm_html = "Unidade", op['cfg']['nome'], ""
                elif ta == 'MILHAR': lbl_alvo, titulo, cm_html = "Filtro", f"M: {str(m_min).zfill(4)} A {str(m_max).zfill(4)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                elif ta == 'CENTENA': lbl_alvo, titulo, cm_html = "Filtro", f"C: {str(c_min).zfill(3)} A {str(c_max).zfill(3)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                else: lbl_alvo, titulo, cm_html = "Atraso", op['cfg']['nome'], f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                    
                with cols[idx % 3]:
                    st.markdown(f"""<div class="home-box"><div class="home-banca" style="color: #fff;">🏦 {op['banca']}</div><div class="home-premio" style="color: #ddd;">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}</div><div class="sniper-valor" style="color:#00ff00;">{op['ap']}x</div><div style="font-size:11px; color:#aaa;">{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
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
                        st.markdown(f"""<div class="home-box"><div class="home-premio" style="color: #fff;">🏆 {TITULOS_PREMIOS[i]}</div><div class="sniper-valor" style="color:#ff4b4b;">{ap}x</div><div style="color: #888; font-size: 11px;">Rec: {mp}x</div></div>""", unsafe_allow_html=True)
    else:
        if st.button("GERAR PLANILHA DE MASSA", type="primary"):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty: st.error("Sem dados.")
            else:
                dados_tabela = []
                
                linha_duplas = {"FILTRO": "🚨 GATILHO: DUPLAS SEGUIDAS", "TETO": "-"}
                for i, col in enumerate(COLUNAS_DF):
                    curr_strk, max_hist = metricas_duplas_raiox(df, col)
                    linha_duplas[TITULOS_PREMIOS[i]] = f"{curr_strk}x (R:{max_hist})"
                dados_tabela.append(linha_duplas)
                
                # =========================================================================
                # INJEÇÃO DA NOVA LINHA DE 10 DÍGITOS - INCONDICIONAL
                # =========================================================================
                linha_10d = {"FILTRO": "🎯 RASTREIO: 10 DÍGITOS (Atual)", "TETO": "-"}
                for i, col in enumerate(COLUNAS_DF):
                    valores = df[col].astype(str).tolist()
                    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
                    
                    if len(validos) > 0:
                        seq_10d = get_10d_state(validos)
                        if seq_10d:
                            linha_10d[TITULOS_PREMIOS[i]] = "-".join(seq_10d)
                        else:
                            linha_10d[TITULOS_PREMIOS[i]] = "-"
                    else:
                        linha_10d[TITULOS_PREMIOS[i]] = "-"
                dados_tabela.append(linha_10d)
                # =========================================================================
                
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
                
                for nome_filtro, cfg in filtros_lista:
                    cfg.update({'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999})
                    linha = {"FILTRO": nome_filtro, "TETO": cfg['lim']}
                    for i, col in enumerate(COLUNAS_DF):
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        linha[TITULOS_PREMIOS[i]] = f"{ap}x (R:{mp})"
                    dados_tabela.append(linha)
                
                linha_sintese = {"FILTRO": "🤖 SÍNTESE IA (Sniper | Vulcão | Mutante)", "TETO": "-"}
                for i, col in enumerate(COLUNAS_DF):
                    m_sniper, m_vulcao, m_mutante = gerar_milhares_preditivas(df, col)
                    linha_sintese[TITULOS_PREMIOS[i]] = f"S:{m_sniper} | V:{m_vulcao} | M:{m_mutante}"
                dados_tabela.append(linha_sintese)

                exibir_banner_sorteio(df, banca_rx)
                st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)

elif menu == "📡 Extração Central":
    configurar_ui_pagina("Extração Central", "#00ff00")
    dt = st.date_input("Data:", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        banca_ex = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
        if st.button("COLETA INDIVIDUAL", type="primary"):
            res = extrair_dia(banca_ex, dt)
            if res:
                sh = conectar_sheets()
                ws = sh.worksheet(MAPA_ABAS[banca_ex])
                existentes = ws.get_all_values()
                set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
                p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
                if p_ins: ws.append_rows(p_ins, value_input_option="RAW"); st.success(f"✅ {len(p_ins)} novos registros salvos."); st.cache_data.clear() 
                else: st.info("Base de dados já atualizada. Nenhum resultado novo encontrado.")
            else: st.error("Sem dados para extrair hoje nesta banca.")
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("EXTRAÇÃO GLOBAL", type="primary"):
            painel_status = st.empty()
            painel_status.info("Varrendo servidores da web e validando assinaturas genéticas... Aguarde.")
            
            sh = conectar_sheets()
            if not sh: 
                painel_status.error("Erro Crítico de Conexão com o Google Sheets.")
            else:
                total_salvos = 0; bancas_atualizadas = []
                for banca_alvo in BANCAS_CONFIG.keys():
                    res = extrair_dia(banca_alvo, dt)
                    if res:
                        ws = sh.worksheet(MAPA_ABAS[banca_alvo])
                        existentes = ws.get_all_values()
                        set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
                        p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
                        if p_ins: 
                            ws.append_rows(p_ins, value_input_option="RAW")
                            total_salvos += len(p_ins)
                            bancas_atualizadas.append(f"✅ **{banca_alvo}:** {len(p_ins)} novos registros inseridos.")
                        else: bancas_atualizadas.append(f"ℹ️ **{banca_alvo}:** Base já está atualizada (0 novos).")
                    else: bancas_atualizadas.append(f"⚠️ **{banca_alvo}:** Nenhum dado encontrado no site para hoje.")
                
                painel_status.empty() 
                st.markdown("### 📊 Relatório de Extração:")
                for b_msg in bancas_atualizadas: st.markdown(b_msg)
                    
                if total_salvos > 0: st.cache_data.clear(); st.success(f"🎯 EXTRAÇÃO GLOBAL CONCLUÍDA! Total de {total_salvos} novos registros.")
                else: st.info("🔄 EXTRAÇÃO GLOBAL CONCLUÍDA! Nenhum registro novo no momento.")

st.markdown("""<div class="rodape-tatico">🎯 GATILHOS ATIVOS: M/C Baixas/Altas=9x | Dezenas, Unidades e Filtros=9x | Síntese de Milhares</div>""", unsafe_allow_html=True)
