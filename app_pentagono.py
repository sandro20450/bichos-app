import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import itertools

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V67.1 - Motor Turbo", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); border: 1px solid; }
.home-box-seq { background-color: #111111; border-color: #444444; } 
.home-box-impar { background-color: #2a0a18; border-color: #ff0055; } 
.home-box-par { background-color: #0a1b2a; border-color: #00aaff; } 
.home-box-dez { background-color: #1a1f00; border-color: #ffcc00; } 
.home-box-uni { background-color: #2d001d; border-color: #ff00aa; } 
.home-box-gemeas { background-color: #1a0033; border-color: #9933ff; } 
.home-box-pendulo { background-color: #1a1a2e; border-color: #e94560; } 

.home-banca { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 2px; text-transform: uppercase; }
.home-horario { font-size: 11px; color: #aaa; margin-top: -2px; margin-bottom: 8px; font-weight: normal; }
.home-premio { font-size: 13px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); border-radius: 4px; padding: 5px;}
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; line-height: 1.2; }
.sniper-valor { font-weight: bold; font-size: 14px; color: #fff; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-amarelo { background-color: rgba(0,0,0,0.5); border: 1px solid #ffcc00; color: #ffcc00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }

.rodape-tatico {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: rgba(17, 17, 17, 0.95);
    color: #ffcc00;
    text-align: center;
    padding: 12px;
    font-size: 15px;
    font-weight: bold;
    border-top: 2px solid #ff4b4b;
    z-index: 9999;
}
.block-container { padding-bottom: 80px; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

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

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

# =============================================================================
# 👻 MOTORES DE ANÁLISE OTIMIZADOS (AWACS, PÊNDULO E GÊMEAS)
# =============================================================================
def gerar_matrizes_taticas():
    esquadroes = []
    cms = []
    for c in range(7): cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
    for cm in cms:
        for g in range(1, 12):
            alvos = set(range(g, g + 15))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G:{str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 6, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 8, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 8, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS (01-50)", 'lim': 8, **cm})
        esquadroes.append({'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS (51-00)", 'lim': 8, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 != 0}, 'modo': 'dezena', 'tipo': 'impar', 'nome': "D: ÍMPARES", 'lim': 8, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 == 0}, 'modo': 'dezena', 'tipo': 'par', 'nome': "D: PARES", 'lim': 8, **cm})
    
    esquadroes_unidade = [
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ]
    esquadroes_gemeas = [
        {'alvos': {0, 11, 22, 33, 44, 55, 66, 77, 88, 99}, 'modo': 'dezena', 'tipo': 'gemeas', 'nome': "👯 DEZENAS GÊMEAS", 'lim': 50, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ]
    
    esquadroes.extend(esquadroes_unidade)
    esquadroes.extend(esquadroes_gemeas)
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    
    # OTIMIZAÇÃO V67.1: Carregando tudo pra memória (lista) de uma vez só!
    valores = df_analise[coluna].astype(str).tolist()
    
    atr_p, atr_c, atr_m = 0, 0, 0 
    achou_p, achou_c, achou_m = False, False, False
    
    # 1. Calculando Atraso Atual (Lendo de trás pra frente)
    for m in reversed(valores):
        milhar = m.zfill(4)
        if milhar == "----" or milhar == "0nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m_val = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:]) 
        except: c, m_val, d, u = -1, -1, -1, -1
        
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        
        if not achou_p:
            if hit_p: achou_p = True
            else: atr_p += 1
        if not achou_c:
            if c_min <= c <= c_max: achou_c = True
            else: atr_c += 1
        if not achou_m:
            if m_min <= m_val <= m_max: achou_m = True
            else: atr_m += 1
            
        if achou_p and achou_c and achou_m: break
    
    # 2. Calculando Recorde Histórico Máximo (Lendo de frente pra trás)
    cur_p, max_p, cur_c, max_c, cur_m, max_m = 0, 0, 0, 0, 0, 0
    for m in valores:
        milhar = m.zfill(4)
        if milhar == "----" or milhar == "0nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m_val = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: c, m_val, d, u = -1, -1, -1, -1
        
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        
        cur_p = 0 if hit_p else cur_p + 1
        if cur_p > max_p: max_p = cur_p
        
        cur_c = 0 if (c_min <= c <= c_max) else cur_c + 1
        if cur_c > max_c: max_c = cur_c
        
        cur_m = 0 if (m_min <= m_val <= m_max) else cur_m + 1
        if cur_m > max_m: max_m = cur_m
        
    return atr_p, atr_c, atr_m, max_p, max_c, max_m

def deduplicar_alvos(lista):
    vistos = set(); resultado = []
    for item in lista:
        assinatura = f"{item['banca']}_{item['premio']}_{item.get('alerta', '')}_{item.get('ap', 0)}_{item.get('cfg', {}).get('nome', '')}"
        if assinatura not in vistos: vistos.add(assinatura); resultado.append(item)
    return resultado

# 🧲 MOTOR DO PÊNDULO OTIMIZADO
def direcao_pendulo_generico(prev, curr, mod, max_step):
    if prev == curr: return "✖️"
    dist_c = (curr - prev) % mod
    dist_d = (prev - curr) % mod
    if 1 <= dist_c <= max_step: return "C"
    if 1 <= dist_d <= max_step: return "D"
    return "✖️"

def processar_pendulo_generico(df, coluna, modo):
    if modo == 'grupo': mod, max_step, reb_size, zlen = 25, 6, 15, 2
    elif modo == 'dezena': mod, max_step, reb_size, zlen = 100, 25, 50, 2
    elif modo == 'centena': mod, max_step, reb_size, zlen = 1000, 250, 500, 3
    
    valores = df[coluna].astype(str).tolist()
    all_nums = []
    
    for m in valores:
        milhar = m.zfill(4)
        if milhar != "----" and milhar != "0nan" and milhar.strip():
            if modo == 'grupo': n = get_grupo_int(milhar)
            elif modo == 'dezena': n = int(milhar[-2:]) if milhar[-2:].isdigit() else None
            elif modo == 'centena': n = int(milhar[-3:]) if milhar[-3:].isdigit() else None
            if n is not None: all_nums.append(n)
            
    if len(all_nums) < 6: return None
    
    draws = all_nums[-6:]; dirs_history = []
    for i in range(1, len(all_nums)): 
        dirs_history.append(direcao_pendulo_generico(all_nums[i-1], all_nums[i], mod, max_step))
        
    curr_streak = 0; curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
            
    max_streak = 0; temp_streak = 0; temp_dir = None
    for d in dirs_history:
        if d in ["C", "D"]:
            if d == temp_dir: temp_streak += 1
            else: temp_dir = d; temp_streak = 1
            if temp_streak > max_streak: max_streak = temp_streak
        else: temp_dir = None; temp_streak = 0
        
    dirs = dirs_history[-5:]; last_num = draws[-1]
    
    if curr_streak >= 3:
        status = "🚨 SATURAÇÃO ALTA" if curr_streak == 3 else "🔥 SATURAÇÃO EXTREMA" if curr_streak == 4 else "☢️ SATURAÇÃO CRÍTICA"
        if curr_dir == "C":
            if modo == 'centena': lista_jogos = f"De {(last_num - reb_size + 1) % mod} até {last_num}"
            else:
                jogos = []; curr = last_num
                for _ in range(reb_size):
                    jogos.append(str(curr).zfill(zlen))
                    curr -= 1
                    if modo == 'grupo' and curr < 1: curr = 25
                    elif curr < 0: curr = mod - 1
                lista_jogos = ", ".join(jogos)
        else:
            if modo == 'centena': lista_jogos = f"De {last_num} até {(last_num + reb_size - 1) % mod}"
            else:
                jogos = []; curr = last_num
                for _ in range(reb_size):
                    jogos.append(str(curr).zfill(zlen))
                    curr += 1
                    if modo == 'grupo' and curr > 25: curr = 1
                    elif curr >= mod: curr = 0
                lista_jogos = ", ".join(jogos)
        return status, lista_jogos, draws, dirs, curr_streak, max_streak, curr_dir, modo
    return None

# =============================================================================
# --- MOTOR DE EXTRAÇÃO E INTERFACE ---
# =============================================================================
def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        for tab in tabelas:
            th_tag = tab.find('th'); txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b']); txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th + " " + txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            nome = f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora and match_hora.group(1) else "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5: resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V67.1")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central AWACS - Visão Geral")
    if st.button("🚀 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("Motor Turbo V67.1 Ativado... Calculando recordes em milissegundos..."):
            oportunidades, alertas_pendulo = [], []
            todos_esq = gerar_matrizes_taticas()
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                # Varredura Pêndulo
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    res_p = processar_pendulo_generico(df, col, 'grupo')
                    if res_p: alertas_pendulo.append({"banca": banca_nome, "sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "data": res_p})

                # Varredura AWACS + GÊMEAS
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        if ap >= cfg['lim']:
                            if cfg['tipo'] == 'gemeas': prio = 1; alerta = f"<div class='alerta-supremo' style='border-color:#9933ff; color:#9933ff;'>🔥 ATAQUE GÊMEAS (1x{92 if banca_nome!='Tradicional' else 85})</div>"
                            elif cfg['modo'] == 'unidade': prio = 1; alerta = f"<div class='alerta-supremo' style='border-color:#ff00aa; color:#ff00aa;'>🔥 ATAQUE UNIDADE</div>"
                            else:
                                prio = 4; alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE FORTE</div>"
                                if ap >= cfg['lim'] and ac >= 5 and am >= 5: prio = 1; alerta = f"<div class='alerta-supremo'>🔥 ATAQUE TOTAL</div>"
                            oportunidades.append({"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "mp": mp, "ac": ac, "mc": mc, "am": am, "mm": mm, "alerta": alerta, "cfg": cfg})

            oportunidades = deduplicar_alvos(sorted(oportunidades, key=lambda x: (x['prio'], -x['ap'])))
            
            # EXIBIÇÃO PENDULO
            if alertas_pendulo:
                st.success(f"🧲 PÊNDULOS SATURADOS: {len(alertas_pendulo)}")
                cols = st.columns(3)
                for idx, p in enumerate(alertas_pendulo):
                    st_txt, j, dr, di, cs, ms, cd, mo = p['data']
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box home-box-pendulo" style="border-color:{'#ff00aa' if cd=='C' else '#00ffff'};"><div class="home-banca">🏦 {p['banca']}</div><div class="home-premio">🏆 {p['premio']}</div><div class="sniper-dado">Saturação: <span class="sniper-valor" style="color:#ff4b4b;">{cs}x</span> (Rec: {ms})</div><div class="alerta-supremo" style="border-color:#fff;">{st_txt}</div><div class="sniper-valor" style="color:#ffcc00; font-size:11px;">{j}</div></div>""", unsafe_allow_html=True)
            
            # EXIBIÇÃO AWACS + GÊMEAS
            if oportunidades:
                st.success(f"🎯 OPORTUNIDADES AWACS/GÊMEAS: {len(oportunidades)}")
                cols = st.columns(3)
                for idx, op in enumerate(oportunidades[:18]):
                    css = f"home-box-{op['cfg']['tipo']}"
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box {css}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-horario">🕒 {op['ultimo_sorteio']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{op['cfg']['nome']}</div><div class="sniper-dado">Atraso: <span class="sniper-valor" style="color:#ff4b4b;">{op['ap']}x</span> (Rec: {op['mp']})</div>{op['alerta']}</div>""", unsafe_allow_html=True)
            if not alertas_pendulo and not oportunidades:
                st.success("🟢 Modo Stealth: Nenhum alvo atingiu a zona de ruptura crítica ainda.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração de Resultados")
    dt = st.date_input("Data do Sorteio:", value=date.today())
    if st.button("🌍 EXTRAÇÃO GLOBAL", type="primary", use_container_width=True):
        with st.spinner("Iniciando varredura global..."):
            sh = conectar_sheets()
            if sh:
                total = 0
                for b in BANCAS_CONFIG.keys():
                    res = extrair_dia(b, dt)
                    if res:
                        ws = sh.worksheet(MAPA_ABAS[b]); exist = {f"{r[0]}_{r[1]}" for r in ws.get_all_values() if len(r)>=2}
                        p_ins = [l for l in res if f"{l[0]}_{l[1]}" not in exist]
                        if p_ins: ws.append_rows(p_ins, value_input_option="RAW"); total += len(p_ins)
                if total > 0: carregar_dados_em_memoria.clear(); st.success(f"✅ {total} registros salvos.")
                else: st.info("Tudo atualizado.")

st.markdown("""<div class="rodape-tatico">🎯 AWACS: Atraso 9x | Unidade/Grupo/Gêmeas 6x/50x &nbsp;&nbsp; || &nbsp;&nbsp; 🧲 PÊNDULO: Saturação 3x ou mais</div>""", unsafe_allow_html=True)
