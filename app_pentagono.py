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
st.set_page_config(page_title="Pentágono V59.2 - Matriz 91", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); }
.home-banca { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 2px; text-transform: uppercase; }
.home-premio { font-size: 13px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 12px; font-weight: bold; color: #e94560; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px; background-color: #1a0000; border-radius: 4px; padding: 5px;}
.sniper-dado { font-size: 12px; color: #aaa; margin: 6px 0; line-height: 1.2; }
.sniper-valor { font-weight: bold; font-size: 14px; color: #fff; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

/* Cores de Alerta */
.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-amarelo { background-color: #332b00; border: 1px solid #ffcc00; color: #ffcc00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# Constantes de Anomalia Globais (Centena e Milhar sempre 5)
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

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

# =============================================================================
# 👻 O MOTOR DO ESQUADRÃO FANTASMA (AGORA COM 91 COMBINAÇÕES)
# =============================================================================
def gerar_91_esquadroes():
    esquadroes = []
    
    # 1. ESQUADRÕES SEQUENCIAIS (77 combinações - Limite Grupo 4)
    for g in range(1, 12):
        grupos_lista = list(range(g, g + 15))
        nome_g = f"G:{str(g).zfill(2)}-{str(g+14).zfill(2)}"
        for c in range(7):
            c_min, c_max = c * 100, (c * 100) + 399
            m_min, m_max = c * 1000, (c * 1000) + 3999
            esquadroes.append({'grupos': set(grupos_lista), 'nome_g': nome_g, 'c_min': c_min, 'c_max': c_max, 'm_min': m_min, 'm_max': m_max, 'lim_g': 4})
            
    # 2. ESQUADRÕES PARES E ÍMPARES (14 combinações - Limite Grupo 5)
    grupos_impares = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25}
    grupos_pares = {2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24}
    
    for c in range(7):
        c_min, c_max = c * 100, (c * 100) + 399
        m_min, m_max = c * 1000, (c * 1000) + 3999
        esquadroes.append({'grupos': grupos_impares, 'nome_g': "G:ÍMPARES", 'c_min': c_min, 'c_max': c_max, 'm_min': m_min, 'm_max': m_max, 'lim_g': 5})
        esquadroes.append({'grupos': grupos_pares, 'nome_g': "G:PARES", 'c_min': c_min, 'c_max': c_max, 'm_min': m_min, 'm_max': m_max, 'lim_g': 5})

    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg, janela=50):
    grupos_alvo = cfg['grupos']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    
    atr_g, atr_c, atr_m = 0, 0, 0
    achou_g, achou_c, achou_m = False, False, False
    
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar)
        except: c, m = -1, -1
        
        if not achou_g:
            if g is not None and g in grupos_alvo: achou_g = True
            else: atr_g += 1
        if not achou_c:
            if c_min <= c <= c_max: achou_c = True
            else: atr_c += 1
        if not achou_m:
            if m_min <= m <= m_max: achou_m = True
            else: atr_m += 1
        if achou_g and achou_c and achou_m: break

    df_janela = df_analise.tail(janela)
    cur_g, cur_c, cur_m, max_g, max_c, max_m = 0, 0, 0, 0, 0, 0
    for i in range(len(df_janela)):
        milhar = str(df_janela.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan": continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar)
        except: c, m = -1, -1
        
        cur_g = 0 if (g is not None and g in grupos_alvo) else cur_g + 1
        max_g = max(max_g, cur_g)
        cur_c = 0 if (c_min <= c <= c_max) else cur_c + 1
        max_c = max(max_c, cur_c)
        cur_m = 0 if (m_min <= m <= m_max) else cur_m + 1
        max_m = max(max_m, cur_m)
        
    return atr_g, atr_c, atr_m, max(max_g, atr_g), max(max_c, atr_c), max(max_m, atr_m)

def deduplicar_alvos(lista):
    vistos = set()
    resultado = []
    for item in lista:
        # A assinatura agora inclui o nome do bloco de grupos para não misturar Par/Ímpar com Sequencial
        assinatura = f"{item['banca']}_{item['premio']}_{item['cfg']['nome_g']}_{item['ac']}_{item['am']}"
        if assinatura not in vistos:
            vistos.add(assinatura)
            resultado.append(item)
    return resultado

# =============================================================================
# --- MOTOR DE EXTRAÇÃO (INTACTO) ---
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
            texto_alvo = txt_th if re.search(r'\d{2}:\d{2}h?|\d{2}h', txt_th) else txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})h?|(\d{2})h', texto_alvo, re.IGNORECASE)
            nome = f"{match_hora.group(3)}:00" if match_hora and match_hora.group(3) else (f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora else "Extra")
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
    st.header("Pentágono V59.2")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Radar Detalhado", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central AWACS - 91 Matrizes (Inclui Pares/Ímpares)")
    st.info("O algoritmo agora cruza sequências, pares e ímpares. O limite de disparo ajusta-se automaticamente à probabilidade da matriz.")
    
    if st.button("🚀 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("Descriptografando 1.820 assinaturas táticas..."):
            oportunidades, recordes = [], []
            todos_esq = gerar_91_esquadroes()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        ag, ac, am, mg, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        LIM_G_ATUAL = cfg['lim_g'] # O limite de disparo se adapta
                        
                        # LOGICA DE ALERTA
                        if ag >= LIM_G_ATUAL:
                            prio = 4; alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL</div>"
                            if ag >= LIM_G_ATUAL and ac >= LIMITE_CENTENA and am >= LIMITE_MILHAR:
                                prio = 1; alerta = f"<div class='alerta-supremo'>🔥 ALERTA MÁXIMO</div>"
                            elif ag >= LIM_G_ATUAL and am >= LIMITE_MILHAR:
                                prio = 2; alerta = f"<div class='alerta-azul'>🔵 ATAQUE MILHAR</div>"
                            elif ag >= LIM_G_ATUAL and ac >= LIMITE_CENTENA:
                                prio = 3; alerta = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA</div>"
                            
                            oportunidades.append({
                                "prio": prio, "banca": banca_nome, "premio": TITULOS_PREMIOS[i], "ag": ag, "ac": ac, "am": am, 
                                "mg": mg, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg
                            })
                        # LOGICA DE RECORDE
                        elif (ag == mg and mg >= LIM_G_ATUAL-1) or (ac == mc and mc >= 4) or (am == mm and mm >= 4):
                            alerta = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE ALCANÇADO</div>"
                            recordes.append({
                                "prio": 5, "banca": banca_nome, "premio": TITULOS_PREMIOS[i], "ag": ag, "ac": ac, "am": am, 
                                "mg": mg, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg
                            })
            
            # Filtro Anti-Flood
            oportunidades = deduplicar_alvos(sorted(oportunidades, key=lambda x: (x['prio'], -x['ag'], -x['ac'], -x['am'])))
            recordes = deduplicar_alvos(sorted(recordes, key=lambda x: (-x['ag'], -x['ac'], -x['am'])))
            
            if oportunidades:
                st.success(f"🎯 ALVOS TRAVADOS: {len(oportunidades)} Oportunidades Críticas Encontradas!")
                cols = st.columns(3)
                for idx, op in enumerate(oportunidades[:15]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    with cols[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box">
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-titulo">
                                {op['cfg']['nome_g']}<br>
                                C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>
                                M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}
                            </div>
                            <div class="sniper-dado" style="text-align:left;">
                                Grupo: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['ag']}x</span> (Rec: {op['mg']})</span><br>
                                Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']>=LIMITE_CENTENA else '#4CAF50'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>
                                Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']>=LIMITE_MILHAR else '#4CAF50'};">{op['am']}x</span> (Rec: {op['mm']})</span>
                            </div>
                            {op['alerta']}
                        </div>
                        """, unsafe_allow_html=True)
            elif recordes:
                st.warning("⚠️ SEM ALERTAS CRÍTICOS. Exibindo RECORDES DE ATRASO alcançados nas últimas 50 extrações:")
                cols = st.columns(3)
                for idx, op in enumerate(recordes[:15]):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    with cols[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box">
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-titulo">
                                {op['cfg']['nome_g']}<br>
                                C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>
                                M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}
                            </div>
                            <div class="sniper-dado" style="text-align:left;">
                                Grupo: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ag']==op['mg'] else '#aaa'};">{op['ag']}x</span> (Rec: {op['mg']})</span><br>
                                Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']==op['mc'] else '#aaa'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>
                                Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']==op['mm'] else '#aaa'};">{op['am']}x</span> (Rec: {op['mm']})</span>
                            </div>
                            {op['alerta']}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("🟢 Campo 100% Limpo! O fluxo de sorteios está normal.")

elif menu == "🎯 Radar Detalhado":
    st.title("🎯 Varredura de Precisão por Banca")
    banca = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("INICIAR BUSCA DETALHADA", type="primary"):
        with st.spinner("Analisando as 91 matrizes táticas..."):
            df = carregar_dados_em_memoria(banca)
            if not df.empty:
                oportunidades = []
                for cfg in gerar_91_esquadroes():
                    for i, col in enumerate(COLUNAS_DF):
                        ag, ac, am, mg, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        if ag >= cfg['lim_g']:
                            oportunidades.append({"premio": TITULOS_PREMIOS[i], "ag": ag, "ac": ac, "am": am, "cfg": cfg})
                
                if oportunidades:
                    oportunidades.sort(key=lambda x: (-x['ag'], -x['ac']))
                    vistos = set()
                    op_limpas = []
                    for o in oportunidades:
                        sig = f"{o['premio']}_{o['cfg']['nome_g']}_{o['ac']}_{o['am']}"
                        if sig not in vistos:
                            vistos.add(sig)
                            op_limpas.append(o)
                            
                    st.write(f"### 📊 Alvos Críticos encontrados para {banca}:")
                    st.table(pd.DataFrame([{
                        "Prêmio": o['premio'], 
                        "Grupos": o['cfg']['nome_g'], 
                        "Centenas": f"{str(o['cfg']['c_min']).zfill(3)} a {str(o['cfg']['c_max']).zfill(3)}",
                        "Milhares": f"{str(o['cfg']['m_min']).zfill(4)} a {str(o['cfg']['m_max']).zfill(4)}",
                        "Atraso Grupo": f"{o['ag']}x", 
                        "Atraso Centena": f"{o['ac']}x", 
                        "Atraso Milhar": f"{o['am']}x"
                    } for o in op_limpas[:15]]))
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
            else: st.error("Nenhum dado encontrado para esta data.")
