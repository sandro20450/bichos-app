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
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V60.1 - Matriz 133", page_icon="🎯", layout="wide")

st.markdown("""
<style>
/* Estilos Base dos Cards */
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); border: 1px solid; }

/* 🎨 HUD Tático de Cores (Aprimoramento Visual) */
.home-box-seq { background-color: #111111; border-color: #444444; } /* Sequencial: Cinza/Preto */
.home-box-impar { background-color: #2a0a18; border-color: #ff0055; } /* Ímpar: Púrpura/Vermelho */
.home-box-par { background-color: #0a1b2a; border-color: #00aaff; } /* Par: Azul/Ciano */
.home-box-dez { background-color: #1a1f00; border-color: #ffcc00; } /* Dezenas Gerais: Oliva/Dourado */

.home-banca { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 2px; text-transform: uppercase; }
.home-horario { font-size: 11px; color: #aaa; margin-top: -2px; margin-bottom: 8px; font-weight: normal; }
.home-premio { font-size: 13px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); border-radius: 4px; padding: 5px;}
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; line-height: 1.2; }
.sniper-valor { font-weight: bold; font-size: 14px; color: #fff; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

/* Cores de Alerta */
.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-amarelo { background-color: rgba(0,0,0,0.5); border: 1px solid #ffcc00; color: #ffcc00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# Constantes de Anomalia Globais
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
# 👻 O MOTOR DO ESQUADRÃO FANTASMA (133 COMBINAÇÕES)
# =============================================================================
def gerar_133_esquadroes():
    esquadroes = []
    
    cms = []
    for c in range(7):
        cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
        
    for cm in cms:
        # 1. ESQUADRÕES DE GRUPOS SEQUENCIAIS (11)
        for g in range(1, 12):
            alvos = set(range(g, g + 15))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G:{str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 4, **cm})
            
        # 2. ESQUADRÕES DE GRUPOS PARES E ÍMPARES (2)
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 5, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 5, **cm})
        
        # 3. ESQUADRÕES DE DEZENAS (6 variações de 50%)
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS (01-50)", 'lim': 5, **cm})
        esquadroes.append({'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS (51-00)", 'lim': 5, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 != 0}, 'modo': 'dezena', 'tipo': 'impar', 'nome': "D: ÍMPARES", 'lim': 5, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 == 0}, 'modo': 'dezena', 'tipo': 'par', 'nome': "D: PARES", 'lim': 5, **cm})
        esquadroes.append({'alvos': set(range(26, 76)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: MIOLO (26-75)", 'lim': 5, **cm})
        esquadroes.append({'alvos': set(range(1, 26)) | set(range(76, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BORDAS", 'lim': 5, **cm})

    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg, janela=50):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    
    atr_p, atr_c, atr_m = 0, 0, 0 # atr_p = Atraso Principal (Grupo ou Dezena)
    achou_p, achou_c, achou_m = False, False, False
    
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: 
            c = int(milhar[-3:])
            m = int(milhar)
            d = int(milhar[-2:])
        except: c, m, d = -1, -1, -1
        
        # Verifica Alvo Principal (Grupo ou Dezena)
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        
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
        try: 
            c = int(milhar[-3:])
            m = int(milhar)
            d = int(milhar[-2:])
        except: c, m, d = -1, -1, -1
        
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        
        cur_p = 0 if hit_p else cur_p + 1
        max_p = max(max_p, cur_p)
        cur_c = 0 if (c_min <= c <= c_max) else cur_c + 1
        max_c = max(max_c, cur_c)
        cur_m = 0 if (m_min <= m <= m_max) else cur_m + 1
        max_m = max(max_m, cur_m)
        
    return atr_p, atr_c, atr_m, max(max_p, atr_p), max(max_c, atr_c), max(max_m, atr_m)

def deduplicar_alvos(lista):
    vistos = set()
    resultado = []
    for item in lista:
        assinatura = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}_{item['ac']}_{item['am']}"
        if assinatura not in vistos:
            vistos.add(assinatura)
            resultado.append(item)
    return resultado

# =============================================================================
# --- MOTOR DE EXTRAÇÃO BLINDADO (CORREÇÃO DA NOMECLATURA 21h) ---
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
            
            # Combina os textos para não perder nenhuma informação
            texto_alvo = txt_th + " " + txt_prev
            
            if "FEDERAL" in texto_alvo.upper(): continue
            
            # 🛡️ Nova Regex Blindada: Pega "18:30", "18h30", "21h", "21H", "21 h"
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            if match_hora:
                if match_hora.group(1): # Achou formato com dois pontos ou minutos
                    nome = f"{match_hora.group(1)}:{match_hora.group(2)}"
                else: # Achou formato solto, ex: 21h
                    nome = f"{match_hora.group(3)}:00"
            else:
                nome = "Extra"
                
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
    st.header("Pentágono V60.1")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Radar Detalhado", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central AWACS - 133 Matrizes")
    st.info("Algoritmo interceptando Grupos, Dezenas, Pares, Ímpares e Extremos. Horário de último sinal integrado nos cards.")
    
    if st.button("🚀 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("O Computador está analisando 2.660 assinaturas de combate..."):
            oportunidades, recordes = [], []
            todos_esq = gerar_133_esquadroes()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                
                # Extrai o último horário do sorteio dessa banca específica
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        LIM_P_ATUAL = cfg['lim'] 
                        
                        # LOGICA DE ALERTA
                        if ap >= LIM_P_ATUAL:
                            prio = 4; alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL</div>"
                            if ap >= LIM_P_ATUAL and ac >= LIMITE_CENTENA and am >= LIMITE_MILHAR:
                                prio = 1; alerta = f"<div class='alerta-supremo'>🔥 ALERTA MÁXIMO</div>"
                            elif ap >= LIM_P_ATUAL and am >= LIMITE_MILHAR:
                                prio = 2; alerta = f"<div class='alerta-azul'>🔵 ATAQUE MILHAR</div>"
                            elif ap >= LIM_P_ATUAL and ac >= LIMITE_CENTENA:
                                prio = 3; alerta = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA</div>"
                            
                            oportunidades.append({
                                "prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], 
                                "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg
                            })
                        # LOGICA DE RECORDE
                        elif (ap == mp and mp >= LIM_P_ATUAL-1) or (ac == mc and mc >= 4) or (am == mm and mm >= 4):
                            alerta = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE ALCANÇADO</div>"
                            recordes.append({
                                "prio": 5, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], 
                                "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg
                            })
            
            # Filtro Anti-Flood
            oportunidades = deduplicar_alvos(sorted(oportunidades, key=lambda x: (x['prio'], -x['ap'], -x['ac'], -x['am'])))
            recordes = deduplicar_alvos(sorted(recordes, key=lambda x: (-x['ap'], -x['ac'], -x['am'])))
            
            if oportunidades:
                st.success(f"🎯 ALVOS TRAVADOS: {len(oportunidades)} Oportunidades Críticas Encontradas!")
                cols = st.columns(3)
                for idx, op in enumerate(oportunidades[:18]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else "Dezena"
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    
                    with cols[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box {css_class}">
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-titulo">
                                {op['cfg']['nome']}<br>
                                C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>
                                M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}
                            </div>
                            <div class="sniper-dado" style="text-align:left;">
                                {lbl_alvo}: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['ap']}x</span> (Rec: {op['mp']})</span><br>
                                Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']>=LIMITE_CENTENA else '#4CAF50'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>
                                Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']>=LIMITE_MILHAR else '#4CAF50'};">{op['am']}x</span> (Rec: {op['mm']})</span>
                            </div>
                            {op['alerta']}
                        </div>
                        """, unsafe_allow_html=True)
            elif recordes:
                st.warning("⚠️ SEM ALERTAS CRÍTICOS. Exibindo RECORDES DE ATRASO alcançados nas últimas 50 extrações:")
                cols = st.columns(3)
                for idx, op in enumerate(recordes[:18]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else "Dezena"
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    
                    with cols[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box {css_class}">
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-titulo">
                                {op['cfg']['nome']}<br>
                                C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>
                                M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}
                            </div>
                            <div class="sniper-dado" style="text-align:left;">
                                {lbl_alvo}: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ap']==op['mp'] else '#aaa'};">{op['ap']}x</span> (Rec: {op['mp']})</span><br>
                                Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']==op['mc'] else '#aaa'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>
                                Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']==op['mm'] else '#aaa'};">{op['am']}x</span> (Rec: {op['mm']})</span>
                            </div>
                            {op['alerta']}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("🟢 Campo 100% Limpo! Nenhuma anomalia no momento.")

elif menu == "🎯 Radar Detalhado":
    st.title("🎯 Varredura de Precisão por Banca")
    banca = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("INICIAR BUSCA DETALHADA", type="primary"):
        with st.spinner("Analisando as 133 matrizes táticas..."):
            df = carregar_dados_em_memoria(banca)
            if not df.empty:
                # Retorna o Banner de Atualização que havia sumido!
                exibir_banner_sorteio(df, banca)
                
                oportunidades = []
                for cfg in gerar_133_esquadroes():
                    for i, col in enumerate(COLUNAS_DF):
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        if ap >= cfg['lim']:
                            oportunidades.append({"premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "cfg": cfg})
                
                if oportunidades:
                    oportunidades.sort(key=lambda x: (-x['ap'], -x['ac']))
                    vistos = set()
                    op_limpas = []
                    for o in oportunidades:
                        sig = f"{o['premio']}_{o['cfg']['nome']}_{o['ac']}_{o['am']}"
                        if sig not in vistos:
                            vistos.add(sig)
                            op_limpas.append(o)
                            
                    st.write(f"### 📊 Alvos Críticos encontrados para {banca}:")
                    st.table(pd.DataFrame([{
                        "Prêmio": o['premio'], 
                        "Alvo Principal": o['cfg']['nome'], 
                        "Centenas": f"{str(o['cfg']['c_min']).zfill(3)} a {str(o['cfg']['c_max']).zfill(3)}",
                        "Milhares": f"{str(o['cfg']['m_min']).zfill(4)} a {str(o['cfg']['m_max']).zfill(4)}",
                        "Atraso (Alvo)": f"{o['ap']}x", 
                        "Atraso Centena": f"{o['ac']}x", 
                        "Atraso Milhar": f"{o['am']}x"
                    } for o in op_limpas[:20]]))
                else:
                    st.info(f"✅ Nenhuma anomalia crítica encontrada na banca {banca} neste momento.")
            else:
                st.error("Erro ao carregar base. Execute uma extração primeiro.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração de Resultados")
    banca_ex = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    dt = st.date_input("Data:", value=date.today())
    if st.button("🚀 INICIAR COLETA", type="primary"):
        with st.spinner("Conectando aos servidores..."):
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
                    else: st.info("Base de dados já atualizada para hoje.")
            else: st.error("Nenhum dado encontrado para esta data ou a banca ainda não atualizou o site.")
