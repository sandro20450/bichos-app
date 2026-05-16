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
st.set_page_config(page_title="Pentágono V65.1 - Radar Visão Total", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); border: 1px solid; }
.home-box-seq { background-color: #111111; border-color: #444444; } 
.home-box-impar { background-color: #2a0a18; border-color: #ff0055; } 
.home-box-par { background-color: #0a1b2a; border-color: #00aaff; } 
.home-box-dez { background-color: #1a1f00; border-color: #ffcc00; } 
.home-box-uni { background-color: #2d001d; border-color: #ff00aa; } 
.home-box-lab { background-color: #001f3f; border-color: #00ffff; } 
.home-box-pendulo { background-color: #1a1a2e; border-color: #e94560; } 

.home-banca { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 2px; text-transform: uppercase; }
.home-horario { font-size: 11px; color: #aaa; margin-top: -2px; margin-bottom: 8px; font-weight: normal; }
.home-premio { font-size: 13px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); border-radius: 4px; padding: 5px;}
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; line-height: 1.2; }
.sniper-valor { font-weight: bold; font-size: 14px; color: #fff; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
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

LIMITE_CENTENA, LIMITE_MILHAR = 5, 5
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

def exibir_banner_sorteio(df, banca):
    if not df.empty:
        ult_nome = str(df.iloc[-1]["Sorteio"])
        st.markdown(f"""
        <div class="banner-info">
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO LIDA DA PLANILHA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

# =============================================================================
# 👻 MOTORES DE ANÁLISE (AWACS, LAB E PÊNDULO)
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
        esquadroes.append({'alvos': set(range(26, 76)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: MIOLO (26-75)", 'lim': 8, **cm})
        esquadroes.append({'alvos': set(range(1, 26)) | set(range(76, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BORDAS", 'lim': 8, **cm})
    
    esquadroes_unidade = [
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 6, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ]
    esquadroes.extend(esquadroes_unidade)
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg, janela=50):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    atr_p, atr_c, atr_m = 0, 0, 0 
    achou_p, achou_c, achou_m = False, False, False
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:]) 
        except: c, m, d, u = -1, -1, -1, -1
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
            if m_min <= m <= m_max: achou_m = True
            else: atr_m += 1
        if achou_p and achou_c and achou_m: break
    df_janela = df_analise.tail(janela)
    cur_p, cur_c, cur_m, max_p, max_c, max_m = 0, 0, 0, 0, 0, 0
    for i in range(len(df_janela)):
        milhar = str(df_janela.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan": continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: c, m, d, u = -1, -1, -1, -1
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        cur_p = 0 if hit_p else cur_p + 1
        max_p = max(max_p, cur_p)
        cur_c = 0 if (c_min <= c <= c_max) else cur_c + 1
        max_c = max(max_c, cur_c)
        cur_m = 0 if (m_min <= m <= m_max) else cur_m + 1
        max_m = max(max_m, cur_m)
    return atr_p, atr_c, atr_m, max(max_p, atr_p), max(max_c, atr_c), max(max_m, atr_m)

def deduplicar_alvos(lista):
    vistos = set(); resultado = []
    for item in lista:
        assinatura = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}_{item['ac']}_{item['am']}"
        if assinatura not in vistos: vistos.add(assinatura); resultado.append(item)
    return resultado

def processar_laboratorio_ternos(df):
    ternos_grupo_vistos = set(); ternos_dezena_vistos = set()
    for i in range(len(df)):
        grupos_sorteio = set(); dezenas_sorteio = set()
        for col in COLUNAS_DF:
            milhar = str(df.iloc[i][col]).zfill(4)
            if milhar != "----" and milhar != "nan" and milhar.strip():
                g = get_grupo_int(milhar)
                try: d = int(milhar[-2:])
                except: d = -1
                if g is not None: grupos_sorteio.add(g)
                if d != -1: dezenas_sorteio.add(d)
        for tg in itertools.combinations(sorted(list(grupos_sorteio)), 3): ternos_grupo_vistos.add(tg)
        for td in itertools.combinations(sorted(list(dezenas_sorteio)), 3): ternos_dezena_vistos.add(td)
    atrasos_g = {g: 0 for g in range(1, 26)}; atrasos_d = {d: 0 for d in range(100)}
    for g in range(1, 26):
        for i in range(len(df)-1, -1, -1):
            achou = False
            for col in COLUNAS_DF:
                m = str(df.iloc[i][col]).zfill(4)
                if m != "----" and m != "nan" and get_grupo_int(m) == g: achou = True; break
            if achou: break
            atrasos_g[g] += 1
    for d in range(100):
        for i in range(len(df)-1, -1, -1):
            achou = False
            for col in COLUNAS_DF:
                m = str(df.iloc[i][col]).zfill(4)
                if m != "----" and m != "nan":
                    try: 
                        if int(m[-2:]) == d: achou = True; break
                    except: pass
            if achou: break
            atrasos_d[d] += 1
    g_ordenados = sorted(atrasos_g.keys(), key=lambda x: atrasos_g[x], reverse=True)
    d_ordenadas = sorted(atrasos_d.keys(), key=lambda x: atrasos_d[x], reverse=True)
    top5_grupos = []
    for tg in itertools.combinations(g_ordenados, 3):
        tg_sorted = tuple(sorted(list(tg)))
        if tg_sorted not in ternos_grupo_vistos:
            soma_atraso = sum([atrasos_g[x] for x in tg_sorted])
            top5_grupos.append({'terno': tg_sorted, 'score': soma_atraso, 'atrasos': [atrasos_g[x] for x in tg_sorted]})
            if len(top5_grupos) == 5: break
    top5_dezenas = []
    for td in itertools.combinations(d_ordenadas, 3):
        td_sorted = tuple(sorted(list(td)))
        if td_sorted not in ternos_dezena_vistos:
            soma_atraso = sum([atrasos_d[x] for x in td_sorted])
            top5_dezenas.append({'terno': td_sorted, 'score': soma_atraso, 'atrasos': [atrasos_d[x] for x in td_sorted]})
            if len(top5_dezenas) == 5: break
    return top5_grupos, top5_dezenas

# 🧲 MOTOR DO PÊNDULO: MODO "PASSOS CURTOS" (MÁX. 6 CASAS)
def direcao_pendulo(prev, curr):
    if prev == curr: return "="
    
    dist_c = (curr - prev) % 25
    dist_d = (prev - curr) % 25
    
    if 1 <= dist_c <= 6: return "C"  # Passo curto pra Direita
    if 1 <= dist_d <= 6: return "D"  # Passo curto pra Esquerda
    
    return "-" # Pulo longo (Quebra a saturação)

def processar_pendulo(df, coluna):
    all_groups = []
    for i in range(len(df)):
        m = str(df.iloc[i][coluna]).zfill(4)
        if m != "----" and m != "nan" and m.strip():
            g = get_grupo_int(m)
            if g is not None:
                all_groups.append(g) 
                
    if len(all_groups) < 6: return None
    
    draws = all_groups[-6:] 
    
    dirs_history = []
    for i in range(1, len(all_groups)):
        dirs_history.append(direcao_pendulo(all_groups[i-1], all_groups[i]))
        
    curr_streak = 0
    curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
            
    max_streak = 0
    temp_streak = 0
    temp_dir = None
    for d in dirs_history:
        if d in ["C", "D"]:
            if d == temp_dir: temp_streak += 1
            else:
                temp_dir = d
                temp_streak = 1
            if temp_streak > max_streak: max_streak = temp_streak
        else:
            temp_dir = None
            temp_streak = 0
            
    dirs = dirs_history[-5:] 
    last_g = draws[-1]
    
    if curr_streak >= 3:
        if curr_streak == 3: status = "🚨 SATURAÇÃO ALTA"
        elif curr_streak == 4: status = "🔥 SATURAÇÃO EXTREMA"
        else: status = f"☢️ SATURAÇÃO CRÍTICA"
        
        jogos = []; curr = last_g
        if curr_dir == "C":
            for _ in range(15):
                jogos.append(str(curr).zfill(2))
                curr -= 1
                if curr < 1: curr = 25
        else:
            for _ in range(15):
                jogos.append(str(curr).zfill(2))
                curr += 1
                if curr > 25: curr = 1
        return status, jogos, draws, dirs, curr_streak, max_streak, curr_dir
        
    return "Estável", [], draws, dirs, curr_streak, max_streak, curr_dir

# =============================================================================
# --- MOTOR DE EXTRAÇÃO BLINDADO ---
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
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th + " " + txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            if match_hora:
                if match_hora.group(1): nome = f"{match_hora.group(1)}:{match_hora.group(2)}"
                else: nome = f"{match_hora.group(3)}:00"
            else: nome = "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V65.1")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Radar Detalhado", "🧲 Armadilha do Pêndulo", "🧪 Lab de Ternos (Vácuo)", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central AWACS - Stealth Mode")
    st.info("Filtros operando em limite extremo. (Banca Tradicional exibe exclusivamente o 1º Prêmio).")
    if st.button("🚀 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("Analisando assinaturas de combate (Incluindo Pêndulo de Passos Curtos)..."):
            oportunidades, recordes, alertas_pendulo = [], [], []
            todos_esq = gerar_matrizes_taticas()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                # 1. Varredura do Pêndulo na Home
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    resultado_pend = processar_pendulo(df, col)
                    if resultado_pend:
                        status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado_pend
                        if status != "Estável":
                            alertas_pendulo.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "status": status, "jogos": jogos, "draws": draws, "dirs": dirs, "curr_streak": curr_streak, "max_streak": max_streak, "curr_dir": curr_dir})
                
                # 2. Varredura AWACS Normal
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        if cfg['modo'] == 'unidade' and (banca_nome != "Tradicional" or col != "P1"): continue
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        LIM_P_ATUAL = cfg['lim'] 
                        
                        # MUDANÇA DA V65.1: Se a Centena ou Milhar bater 9x ou mais, é promovido a Alvo Travado!
                        if ap >= LIM_P_ATUAL or ac >= 9 or am >= 9:
                            if cfg['modo'] == 'unidade':
                                prio = 1; alerta = f"<div class='alerta-supremo' style='border-color:#ff00aa; color:#ff00aa;'>🔥 ATAQUE UNIDADE</div>"
                            else:
                                if ap >= LIM_P_ATUAL and ac >= LIMITE_CENTENA and am >= LIMITE_MILHAR: 
                                    prio = 1; alerta = f"<div class='alerta-supremo'>🔥 ATAQUE TOTAL (G+C+M)</div>"
                                elif am >= 9 or (ap >= LIM_P_ATUAL and am >= LIMITE_MILHAR): 
                                    prio = 2; alerta = f"<div class='alerta-azul'>🔵 ATAQUE MILHAR</div>"
                                elif ac >= 9 or (ap >= LIM_P_ATUAL and ac >= LIMITE_CENTENA): 
                                    prio = 3; alerta = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA</div>"
                                else:
                                    prio = 4; alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE FORTE (GRUPO)</div>"
                            oportunidades.append({"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg})
                        
                        # Alvos secundários (Recordes), se não foi promovido
                        elif (ap == mp and mp >= LIM_P_ATUAL-1) or (cfg['modo'] != 'unidade' and ((ac == mc and mc >= 5) or (am == mm and mm >= 5))):
                            alerta = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE ALCANÇADO</div>"
                            recordes.append({"prio": 5, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg})
            
            oportunidades = deduplicar_alvos(sorted(oportunidades, key=lambda x: (x['prio'], -x['ap'], -x['ac'], -x['am'])))
            recordes = deduplicar_alvos(sorted(recordes, key=lambda x: (-x['ap'], -x['ac'], -x['am'])))
            
            # EXIBIÇÃO: PENDULO PRIMEIRO
            if alertas_pendulo:
                st.success(f"🧲 ALERTA GRAVITACIONAL: {len(alertas_pendulo)} Pêndulos Saturados Detectados!")
                cols_pend = st.columns(3)
                for idx, pend in enumerate(alertas_pendulo):
                    with cols_pend[idx % 3]:
                        status, jogos, draws, dirs = pend['status'], pend['jogos'], pend['draws'], pend['dirs']
                        curr_streak, max_streak, curr_dir = pend['curr_streak'], pend['max_streak'], pend['curr_dir']
                        
                        setas = ["➡️" if d == "C" else "⬅️" if d == "D" else "⏸️" if d == "=" else "✖️" for d in dirs]
                        seq_visual = f"<span style='font-size:16px; font-weight:bold;'>{str(draws[0]).zfill(2)}</span> {setas[0]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[1]).zfill(2)}</span> {setas[1]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[2]).zfill(2)}</span> {setas[2]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[3]).zfill(2)}</span> {setas[3]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[4]).zfill(2)}</span> {setas[4]} " \
                                     f"<span style='font-size:16px; font-weight:bold; color:#ff4b4b;'>{str(draws[5]).zfill(2)}</span>"
                                     
                        cor_box = "border-color: #ff00aa;" if curr_dir == "C" else "border-color: #00ffff;"
                        lista_jogos = ", ".join(jogos)
                        
                        st.markdown(f"""
                        <div class="home-box home-box-pendulo" style="{cor_box}">
                            <div class="home-banca">🏦 {pend['banca']}</div>
                            <div class="home-horario">🕒 ÚLTIMO: {pend['ultimo_sorteio']}</div>
                            <div class="home-premio">🏆 {pend['premio']}</div>
                            <div class="sniper-dado" style="margin-bottom:10px;">{seq_visual}</div>
                            <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                Saturação: <span class="sniper-valor" style="color:#ff4b4b;">{curr_streak}x</span> (Rec: {max_streak})
                            </div>
                            <div class="alerta-supremo" style="{cor_box}">{status}<br> {'Direção: Crescente' if curr_dir == 'C' else 'Direção: Decrescente'}</div>
                            <div class="sniper-dado" style="margin-top:10px; color:#fff;">Atirar em 15 Grupos {'Anteriores' if curr_dir == 'C' else 'Seguintes'}:</div>
                            <div class="sniper-valor" style="color:#ffcc00; font-size:12px; word-wrap: break-word;">{lista_jogos}</div>
                        </div>
                        """, unsafe_allow_html=True)
                st.markdown("---") # Divisor
            
            # EXIBIÇÃO: OPORTUNIDADES AWACS
            if oportunidades:
                st.success(f"🎯 ALVOS TRAVADOS: {len(oportunidades)} Oportunidades de Ruptura Encontradas!")
                cols = st.columns(3)
                for idx, op in enumerate(oportunidades[:18]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    if op['cfg']['modo'] == 'unidade':
                        lbl_alvo = "Unidade"; sub_titulo = "ALVO EXCLUSIVO: UNIDADE"
                        cm_html = """Centena: <span style="float:right;color:#555;">---</span><br>Milhar: <span style="float:right;color:#555;">---</span>"""
                    else:
                        lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else "Dezena"
                        sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']>=LIMITE_CENTENA else '#4CAF50'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']>=LIMITE_MILHAR else '#4CAF50'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{op['cfg']['nome']}<br>{sub_titulo}</div><div class="sniper-dado" style="text-align:left;">{lbl_alvo}: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['ap']}x</span> (Rec: {op['mp']})</span><br>{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
                st.markdown("---") # Divisor

            # EXIBIÇÃO: RECORDES (SEMPRE VISÍVEL AGORA)
            if recordes:
                st.warning("⚠️ RECORDES HISTÓRICOS ALCANÇADOS (Radar Secundário):")
                cols = st.columns(3)
                for idx, op in enumerate(recordes[:18]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    if op['cfg']['modo'] == 'unidade':
                        lbl_alvo = "Unidade"; sub_titulo = "ALVO EXCLUSIVO: UNIDADE"
                        cm_html = """Centena: <span style="float:right;color:#555;">---</span><br>Milhar: <span style="float:right;color:#555;">---</span>"""
                    else:
                        lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else "Dezena"
                        sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']==op['mc'] else '#aaa'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']==op['mm'] else '#aaa'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{op['cfg']['nome']}<br>{sub_titulo}</div><div class="sniper-dado" style="text-align:left;">{lbl_alvo}: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ap']==op['mp'] else '#aaa'};">{op['ap']}x</span> (Rec: {op['mp']})</span><br>{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
            
            # SE NÃO TIVER NADA DE NADA
            if not oportunidades and not alertas_pendulo and not recordes: 
                st.success("🟢 Modo Stealth: Nenhum alvo atingiu a zona de ruptura crítica ainda.")

elif menu == "🎯 Radar Detalhado":
    st.title("🎯 Varredura de Precisão por Banca")
    banca = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("INICIAR BUSCA DETALHADA", type="primary"):
        with st.spinner("Buscando por alvos em ruptura máxima..."):
            df = carregar_dados_em_memoria(banca)
            if not df.empty:
                exibir_banner_sorteio(df, banca)
                oportunidades = []
                for cfg in gerar_matrizes_taticas():
                    for i, col in enumerate(COLUNAS_DF):
                        if cfg['modo'] == 'unidade' and (banca != "Tradicional" or col != "P1"): continue
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        if ap >= cfg['lim']: oportunidades.append({"premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "cfg": cfg})
                if oportunidades:
                    oportunidades.sort(key=lambda x: (-x['ap'], -x['ac']))
                    vistos = set(); op_limpas = []
                    for o in oportunidades:
                        sig = f"{o['premio']}_{o['cfg']['nome']}_{o['ac']}_{o['am']}"
                        if sig not in vistos: vistos.add(sig); op_limpas.append(o)
                    st.write(f"### 📊 Alvos Críticos (Extremos) encontrados para {banca}:")
                    st.table(pd.DataFrame([{"Prêmio": o['premio'], "Alvo Principal": o['cfg']['nome'], "Centenas": "---" if o['cfg']['modo'] == 'unidade' else f"{str(o['cfg']['c_min']).zfill(3)} a {str(o['cfg']['c_max']).zfill(3)}", "Milhares": "---" if o['cfg']['modo'] == 'unidade' else f"{str(o['cfg']['m_min']).zfill(4)} a {str(o['cfg']['m_max']).zfill(4)}", "Atraso (Alvo)": f"{o['ap']}x", "Atraso Centena": "---" if o['cfg']['modo'] == 'unidade' else f"{o['ac']}x", "Atraso Milhar": "---" if o['cfg']['modo'] == 'unidade' else f"{o['am']}x"} for o in op_limpas[:20]]))
                else: st.info(f"✅ Nenhuma ruptura detectada.")
            else: st.error("Erro ao carregar base. Execute uma extração primeiro.")

elif menu == "🧲 Armadilha do Pêndulo":
    st.title("🧲 Armadilha de Saturação (Pêndulo)")
    st.info("Analisa a física circular de **Passos Curtos (1 a 6 casas)** dos últimos 6 sorteios. Pulos longos (✖️) quebram a saturação.")
    banca_pendulo = st.selectbox("Selecione o Alvo de Rastreador Circular:", list(BANCAS_CONFIG.keys()))
    
    if st.button("🧲 ANALISAR MOMENTUM CIRCULAR", type="primary", use_container_width=True):
        with st.spinner(f"Calculando a distância circular na {banca_pendulo}..."):
            df = carregar_dados_em_memoria(banca_pendulo)
            if df.empty:
                st.error("Base de dados vazia. Faça uma extração primeiro.")
            else:
                exibir_banner_sorteio(df, banca_pendulo)
                st.markdown("### 📊 Resultado do Rastreador")
                cols = st.columns(5)
                for i, col in enumerate(COLUNAS_DF):
                    resultado = processar_pendulo(df, col)
                    with cols[i]:
                        if resultado:
                            status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado
                            # Visualização com o "✖️" para passos longos
                            setas = ["➡️" if d == "C" else "⬅️" if d == "D" else "⏸️" if d == "=" else "✖️" for d in dirs]
                            seq_visual = f"<span style='font-size:16px; font-weight:bold;'>{str(draws[0]).zfill(2)}</span> {setas[0]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[1]).zfill(2)}</span> {setas[1]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[2]).zfill(2)}</span> {setas[2]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[3]).zfill(2)}</span> {setas[3]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[4]).zfill(2)}</span> {setas[4]} " \
                                         f"<span style='font-size:16px; font-weight:bold; color:#ff4b4b;'>{str(draws[5]).zfill(2)}</span>"
                            
                            if status != "Estável":
                                cor_box = "border-color: #ff00aa;" if curr_dir == "C" else "border-color: #00ffff;"
                                lista_jogos = ", ".join(jogos)
                                
                                st.markdown(f"""
                                <div class="home-box home-box-pendulo" style="{cor_box}">
                                    <div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div>
                                    <div class="sniper-dado" style="margin-bottom:10px;">{seq_visual}</div>
                                    <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                        Saturação: <span class="sniper-valor" style="color:#ff4b4b;">{curr_streak}x</span> (Rec: {max_streak})
                                    </div>
                                    <div class="alerta-supremo" style="{cor_box}">{status}<br> {'Direção: Crescente' if curr_dir == 'C' else 'Direção: Decrescente'}</div>
                                    <div class="sniper-dado" style="margin-top:10px; color:#fff;">Atirar em 15 Grupos {'Anteriores' if curr_dir == 'C' else 'Seguintes'}:</div>
                                    <div class="sniper-valor" style="color:#ffcc00; font-size:12px; word-wrap: break-word;">{lista_jogos}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class="home-box" style="background-color:#111; border-color:#333;">
                                    <div class="home-premio" style="color:#aaa;">🏆 {TITULOS_PREMIOS[i]}</div>
                                    <div class="sniper-dado" style="margin-bottom:10px; color:#666;">{seq_visual}</div>
                                    <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                        Saturação: <span class="sniper-valor" style="color:#4CAF50;">{curr_streak}x</span> (Rec: {max_streak})
                                    </div>
                                    <div class="sniper-dado">Movimento Estável.<br>Sem saturação detectada.</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.write(f"Sem dados suficientes em {TITULOS_PREMIOS[i]}")

elif menu == "🧪 Lab de Ternos (Vácuo)":
    st.title("🧪 Laboratório de Vácuo Estatístico")
    st.info("Analisa **todo o histórico da planilha** para encontrar Ternos que NUNCA saíram juntos.")
    banca_lab = st.selectbox("Selecione o Alvo para Pesquisa Profunda:", list(BANCAS_CONFIG.keys()))
    if st.button("🔬 PROCESSAR VÁCUO ESTATÍSTICO", type="primary", use_container_width=True):
        with st.spinner(f"Lendo histórico da {banca_lab} e cruzando milhares de combinações..."):
            df_lab = carregar_dados_em_memoria(banca_lab)
            if df_lab.empty: st.error("Base de dados vazia. Faça uma extração primeiro.")
            else:
                total_sorteios = len(df_lab)
                top5_g, top5_d = processar_laboratorio_ternos(df_lab)
                st.success(f"✅ Histórico completo analisado: **{total_sorteios} sorteios processados.**")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 🐯 Terno de Grupo (Inéditos Top 5)")
                    if top5_g:
                        for i, t in enumerate(top5_g):
                            t_format = " - ".join([str(x).zfill(2) for x in t['terno']])
                            atr_format = " | ".join([f"G:{str(g).zfill(2)}({a}x)" for g, a in zip(t['terno'], t['atrasos'])])
                            st.markdown(f"""<div class="home-box home-box-lab"><div class="sniper-titulo" style="color:#00ffff;">Terno #{i+1}: {t_format}</div><div class="sniper-dado" style="color:#fff;">Atrasos Individuais Atuais:</div><div class="sniper-dado" style="color:#FF851B; font-weight:bold;">{atr_format}</div><div class="alerta-azul" style="border-color:#00ffff; color:#00ffff;">NUNCA SAIU JUNTO</div></div>""", unsafe_allow_html=True)
                    else: st.info("Todos os ternos de grupo já saíram pelo menos uma vez.")
                with col2:
                    st.markdown("### 💣 Terno de Dezena (Inéditos Top 5)")
                    if top5_d:
                        for i, t in enumerate(top5_d):
                            t_format = " - ".join([str(x).zfill(2) for x in t['terno']])
                            atr_format = " | ".join([f"D:{str(d).zfill(2)}({a}x)" for d, a in zip(t['terno'], t['atrasos'])])
                            st.markdown(f"""<div class="home-box home-box-lab"><div class="sniper-titulo" style="color:#ffcc00;">Terno #{i+1}: {t_format}</div><div class="sniper-dado" style="color:#fff;">Atrasos Individuais Atuais:</div><div class="sniper-dado" style="color:#FF851B; font-weight:bold;">{atr_format}</div><div class="alerta-amarelo" style="border-color:#ffcc00; color:#ffcc00;">NUNCA SAIU JUNTO</div></div>""", unsafe_allow_html=True)
                    else: st.info("Todos os ternos de dezena já saíram pelo menos uma vez.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração de Resultados")
    dt = st.date_input("Data do Sorteio:", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        banca_ex = st.selectbox("Selecione o Alvo Individual:", list(BANCAS_CONFIG.keys()))
        if st.button("🚀 COLETA INDIVIDUAL", type="primary", use_container_width=True):
            with st.spinner(f"Conectando aos servidores da {banca_ex}..."):
                res = extrair_dia(banca_ex, dt)
                if res:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_ex])
                        existentes = ws.get_all_values()
                        set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
                        p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
                        if p_ins: 
                            ws.append_rows(p_ins, value_input_option="RAW")
                            st.success(f"✅ {len(p_ins)} novos registros salvos.")
                            carregar_dados_em_memoria.clear() 
                        else: st.info("Base de dados já atualizada.")
                else: st.error("Sem dados para extrair.")
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🌍 EXTRAÇÃO GLOBAL", type="primary", use_container_width=True):
            with st.spinner("Iniciando varredura global em todos os servidores..."):
                sh = conectar_sheets()
                if not sh: st.error("Erro Crítico de Conexão.")
                else:
                    total_salvos = 0
                    for banca_alvo in BANCAS_CONFIG.keys():
                        res = extrair_dia(banca_alvo, dt)
                        if res:
                            ws = sh.worksheet(MAPA_ABAS[banca_alvo])
                            existentes = ws.get_all_values()
                            set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
                            p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
                            if p_ins:
                                ws.append_rows(p_ins, value_input_option="RAW")
                                total_salvos += len(p_ins)
                                st.success(f"✅ {banca_alvo}: {len(p_ins)} salvos.")
                            else: st.info(f"ℹ️ {banca_alvo}: Atualizada.")
                        else: st.warning(f"⚠️ {banca_alvo}: Sem dados.")
                    if total_salvos > 0:
                        carregar_dados_em_memoria.clear()
                        st.success(f"🎯 MISSÃO CONCLUÍDA: {total_salvos} novos registros.")

# MUDANÇA DA V65.1: RODAPÉ COM A INSTRUÇÃO DA SATURAÇÃO DAS SETAS ACIMA DE 4X
st.markdown("""<div class="rodape-tatico">🎯 AWACS: M/C > 9x | G > 6x | Filtros > 9x | U > 6x &nbsp;&nbsp; || &nbsp;&nbsp; 🧲 PÊNDULO: Saturação de Setas Acima de 4x</div>""", unsafe_allow_html=True)
