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
st.set_page_config(page_title="Pentágono V58.4 - Frota Completa", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.tabela-compacta { width: 100%; border-collapse: collapse; text-align: center; font-size: 14px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
.tabela-compacta th { background-color: #330000; color: #ff4b4b; padding: 8px; border: 1px solid #444; font-size: 13px; }
.tabela-compacta td { padding: 6px; border: 1px solid #333; color: #fff; background-color: #121212; }
.td-cabecalho { color: #888 !important; font-size: 10px !important; background-color: #000 !important; }
.grupo-destaque { font-weight: bold; color: #4CAF50 !important; font-size: 16px; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

/* Estilos do Sniper Triplo e Home */
.sniper-box { background-color: #1a1a2e; border: 1px solid #16213e; border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
.home-box { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); position: relative;}
.home-banca { font-size: 18px; font-weight: bold; color: #fff; margin-bottom: 5px; text-transform: uppercase; }
.home-premio { font-size: 14px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 16px; font-weight: bold; color: #e94560; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px;}
.sniper-dado { font-size: 13px; color: #aaa; margin: 8px 0; line-height: 1.1; }
.sniper-valor { font-weight: bold; font-size: 15px; color: #fff; }
.sniper-recorde { font-size: 10px; color: #666; display: block; margin-top: 2px; }

/* Cores de Alerta */
.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-amarelo { background-color: #332b00; border: 1px solid #ffcc00; color: #ffcc00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-cinza { background-color: #222; border: 1px solid #555; color: #888; padding: 8px; border-radius: 5px; font-size: 12px; margin-top: 15px; }

/* Cabeçalhos dos 10 Esquadrões */
.titulo-esquadrao { text-align: center; font-weight: bold; padding: 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 15px; text-transform: uppercase; font-size: 14px;}
.bg-alpha { background-color: #001f3f; border: 1px solid #0074D9; color: #7FDBFF; }
.bg-bravo { background-color: #3e1f00; border: 1px solid #FF851B; color: #FFDC00; }
.bg-charlie { background-color: #2e003e; border: 1px solid #B10DC9; color: #F012BE; }
.bg-delta { background-color: #003333; border: 1px solid #39CCCC; color: #7FDBFF; }
.bg-echo { background-color: #330000; border: 1px solid #FF4136; color: #FF851B; }
.bg-foxtrot { background-color: #1a1a1a; border: 1px solid #aaaaaa; color: #ffffff; }
.bg-golf { background-color: #002200; border: 1px solid #01FF70; color: #01FF70; }
.bg-hotel { background-color: #2b1d00; border: 1px solid #FFD700; color: #FFD700; }
.bg-india { background-color: #330000; border: 1px solid #ffffff; color: #ffffff; }
.bg-juliet { background-color: #191970; border: 1px solid #E6E6FA; color: #E6E6FA; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# Configurações Globais dos 10 Esquadrões
ESQUADROES_CFG = [
    (1, 15, 600, 999, 6000, 9999, "bg-alpha", "⚔️ ESQ. ALPHA (G:01-15 | C:600-999)"),
    (7, 21, 100, 499, 1000, 4999, "bg-bravo", "⚔️ ESQ. BRAVO (G:07-21 | C:100-499)"),
    (11, 25, 0, 399, 0, 3999, "bg-charlie", "⚔️ ESQ. CHARLIE (G:11-25 | C:000-399)"),
    (6, 20, 300, 699, 3000, 6999, "bg-delta", "⚔️ ESQ. DELTA (G:06-20 | C:300-699)"),
    (4, 18, 500, 899, 5000, 8999, "bg-echo", "⚔️ ESQ. ECHO (G:04-18 | C:500-899)"),
    (1, 15, 0, 399, 0, 3999, "bg-foxtrot", "⚔️ ESQ. FOXTROT (G:01-15 | C:000-399)"),
    (11, 25, 600, 999, 6000, 9999, "bg-golf", "⚔️ ESQ. GOLF (G:11-25 | C:600-999)"),
    (2, 16, 200, 599, 2000, 5999, "bg-hotel", "⚔️ ESQ. HOTEL (G:02-16 | C:200-599)"),
    (9, 23, 400, 799, 4000, 7999, "bg-india", "⚔️ ESQ. INDIA (G:09-23 | C:400-799)"),
    (5, 19, 100, 499, 1000, 4999, "bg-juliet", "⚔️ ESQ. JULIET (G:05-19 | C:100-499)")
]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
LIMITE_GRUPO, LIMITE_CENTENA, LIMITE_MILHAR = 4, 5, 5

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
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO MONITORADA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

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
# --- MOTOR DO SNIPER ---
# =============================================================================
def calcular_metricas_sniper(df_analise, coluna, g_min, g_max, c_min, c_max, m_min, m_max, janela=50):
    atraso_grupo, atraso_centena, atraso_milhar = 0, 0, 0
    achou_g, achou_c, achou_m = False, False, False
    
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:])
        except: c = -1
        try: m = int(milhar)
        except: m = -1
            
        if not achou_g:
            if g is not None and g_min <= g <= g_max: achou_g = True
            else: atraso_grupo += 1
        if not achou_c:
            if c_min <= c <= c_max: achou_c = True
            else: atraso_centena += 1
        if not achou_m:
            if m_min <= m <= m_max: achou_m = True
            else: atraso_milhar += 1
            
        if achou_g and achou_c and achou_m: break

    df_janela = df_analise.tail(janela)
    curr_g, curr_c, curr_m = 0, 0, 0
    max_g, max_c, max_m = 0, 0, 0
    
    for i in range(len(df_janela)):
        milhar = str(df_janela.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:])
        except: c = -1
        try: m = int(milhar)
        except: m = -1
            
        if g is not None and g_min <= g <= g_max: curr_g = 0
        else: curr_g += 1
        if curr_g > max_g: max_g = curr_g
            
        if c_min <= c <= c_max: curr_c = 0
        else: curr_c += 1
        if curr_c > max_c: max_c = curr_c
            
        if m_min <= m <= m_max: curr_m = 0
        else: curr_m += 1
        if curr_m > max_m: max_m = curr_m

    max_g = max(max_g, atraso_grupo)
    max_c = max(max_c, atraso_centena)
    max_m = max(max_m, atraso_milhar)

    return atraso_grupo, atraso_centena, atraso_milhar, max_g, max_c, max_m

# =============================================================================
# --- INTERFACE DE COMANDO ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V58.4")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Radar Sniper (Banca Específica)", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central de Alerta AWACS (10 Esquadrões)")
    st.info("Varredura simultânea usando 10 matrizes matemáticas. Exibindo os 15 melhores alvos confirmados no momento.")
    
    if st.button("🔄 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("Analisando Bancas, Prêmios e 10 Esquadrões... Aguarde."):
            oportunidades = []
            recordes = []
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                
                for cfg in ESQUADROES_CFG:
                    g_min, g_max, c_min, c_max, m_min, m_max, css_class, titulo_esq = cfg
                    
                    for i, col in enumerate(COLUNAS_DF):
                        atr_g, atr_c, atr_m, max_g, max_c, max_m = calcular_metricas_sniper(df, col, g_min, g_max, c_min, c_max, m_min, m_max)
                        
                        # 1. Verifica Alertas Críticos
                        if atr_g >= LIMITE_GRUPO:
                            prioridade = 4
                            html_alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL<br><span style='font-size:10px;font-weight:normal;'>Jogue APENAS Grupos</span></div>"
                            
                            if atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA and atr_m >= LIMITE_MILHAR:
                                prioridade = 1
                                html_alerta = f"<div class='alerta-supremo'>🔥 ALERTA MÁXIMO<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos + Centenas + Milhares</span></div>"
                            elif atr_g >= LIMITE_GRUPO and atr_m >= LIMITE_MILHAR:
                                prioridade = 2
                                html_alerta = f"<div class='alerta-azul'>🔵 ATAQUE MILHAR<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos + Milhares</span></div>"
                            elif atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA:
                                prioridade = 3
                                html_alerta = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos + Centenas</span></div>"
                            
                            oportunidades.append({
                                "prioridade": prioridade, "banca": banca_nome, "premio": TITULOS_PREMIOS[i], "esquadrao": titulo_esq,
                                "css": css_class, "atr_g": atr_g, "atr_c": atr_c, "atr_m": atr_m, "max_g": max_g, "max_c": max_c, "max_m": max_m,
                                "html_alerta": html_alerta, "g_info": f"{str(g_min).zfill(2)}-{str(g_max).zfill(2)}",
                                "c_info": f"{str(c_min).zfill(3)}-{str(c_max).zfill(3)}", "m_info": f"{str(m_min).zfill(4)}-{str(m_max).zfill(4)}"
                            })
                        
                        # 2. Se NÃO houver alerta crítico, verifica Recordes Quebrados
                        else:
                            rec_g = (atr_g == max_g and max_g >= 3)
                            rec_c = (atr_c == max_c and max_c >= 4)
                            rec_m = (atr_m == max_m and max_m >= 4)
                            
                            if rec_g or rec_c or rec_m:
                                alertas_rec = []
                                if rec_g: alertas_rec.append("Grupo")
                                if rec_c: alertas_rec.append("Centena")
                                if rec_m: alertas_rec.append("Milhar")
                                
                                motivo = " + ".join(alertas_rec)
                                html_recorde = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE ALCANÇADO<br><span style='font-size:10px;font-weight:normal;'>{motivo} no limite histórico</span></div>"
                                
                                recordes.append({
                                    "banca": banca_nome, "premio": TITULOS_PREMIOS[i], "esquadrao": titulo_esq, "css": css_class,
                                    "atr_g": atr_g, "atr_c": atr_c, "atr_m": atr_m, "max_g": max_g, "max_c": max_c, "max_m": max_m,
                                    "html_alerta": html_recorde, "g_info": f"{str(g_min).zfill(2)}-{str(g_max).zfill(2)}",
                                    "c_info": f"{str(c_min).zfill(3)}-{str(c_max).zfill(3)}", "m_info": f"{str(m_min).zfill(4)}-{str(m_max).zfill(4)}"
                                })
            
            # --- RENDERIZAÇÃO DA TELA HOME ---
            if oportunidades:
                st.success(f"🎯 Foram encontrados {len(oportunidades)} ALERTAS CRÍTICOS. Exibindo o Top 15:")
                oportunidades.sort(key=lambda x: (x['prioridade'], -x['atr_g']))
                
                cols_ui = st.columns(3)
                for idx, op in enumerate(oportunidades[:15]): # Exibe até 15 cards
                    with cols_ui[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box">
                            <div class="titulo-esquadrao {op['css']}" style="margin-top:0px;">{op['esquadrao']}</div>
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-dado" style="text-align:left;">
                                G ({op['g_info']}): <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['atr_g']}x</span> (Rec: {op['max_g']})</span><br>
                                C ({op['c_info']}): <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['atr_c']>=LIMITE_CENTENA else '#4CAF50'};">{op['atr_c']}x</span> (Rec: {op['max_c']})</span><br>
                                M ({op['m_info']}): <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['atr_m']>=LIMITE_MILHAR else '#4CAF50'};">{op['atr_m']}x</span> (Rec: {op['max_m']})</span>
                            </div>
                            {op['html_alerta']}
                        </div>
                        """, unsafe_allow_html=True)
                        
            elif recordes:
                st.warning("⚠️ Nenhum Alerta Crítico (Gatilho Principal) no momento, mas os seguintes **RECORDES DE ATRASO** foram alcançados nas últimas 50 extrações:")
                recordes.sort(key=lambda x: (-x['atr_c'], -x['atr_m'], -x['atr_g']))
                
                cols_ui = st.columns(3)
                for idx, op in enumerate(recordes[:15]):
                    with cols_ui[idx % 3]:
                        st.markdown(f"""
                        <div class="home-box">
                            <div class="titulo-esquadrao {op['css']}" style="margin-top:0px;">{op['esquadrao']}</div>
                            <div class="home-banca">🏦 {op['banca']}</div>
                            <div class="home-premio">🏆 {op['premio']}</div>
                            <div class="sniper-dado" style="text-align:left;">
                                G ({op['g_info']}): <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['atr_g']==op['max_g'] else '#4CAF50'};">{op['atr_g']}x</span> (Rec: {op['max_g']})</span><br>
                                C ({op['c_info']}): <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['atr_c']==op['max_c'] else '#4CAF50'};">{op['atr_c']}x</span> (Rec: {op['max_c']})</span><br>
                                M ({op['m_info']}): <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['atr_m']==op['max_m'] else '#4CAF50'};">{op['atr_m']}x</span> (Rec: {op['max_m']})</span>
                            </div>
                            {op['html_alerta']}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("🟢 Campo Limpo! Não há anomalias críticas nem recordes sendo quebrados no momento.")

elif menu == "🎯 Radar Sniper (Banca Específica)":
    st.title("🎯 Centro de Comando de Operações (Detalhado)")
    banca_ia = st.selectbox("Selecione a Banca para Mapeamento:", list(BANCAS_CONFIG.keys()))
    
    if st.button("INICIAR VARREDURA GERAL", use_container_width=True, type="primary"):
        with st.spinner("Varrendo os 10 Esquadrões na banca selecionada..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                for cfg in ESQUADROES_CFG:
                    g_min, g_max, c_min, c_max, m_min, m_max, css_class, titulo_esq = cfg
                    st.markdown(f"<div class='titulo-esquadrao {css_class}'>{titulo_esq}</div>", unsafe_allow_html=True)
                    cols = st.columns(5)
                    for i in range(5):
                        atr_g, atr_c, atr_m, max_g, max_c, max_m = calcular_metricas_sniper(df, COLUNAS_DF[i], g_min, g_max, c_min, c_max, m_min, m_max)
                        if atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA and atr_m >= LIMITE_MILHAR:
                            veredito = "<div class='alerta-supremo'>🔥 ALERTA MÁXIMO</div>"
                        elif atr_g >= LIMITE_GRUPO and atr_m >= LIMITE_MILHAR:
                            veredito = "<div class='alerta-azul'>🔵 ATAQUE MILHAR</div>"
                        elif atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA:
                            veredito = "<div class='alerta-verde'>🟢 ATAQUE CENTENA</div>"
                        elif atr_g >= LIMITE_GRUPO:
                            veredito = "<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL</div>"
                        else:
                            veredito = "<div class='alerta-cinza'>⚪ AGUARDAR</div>"
                            
                        with cols[i]:
                            st.markdown(f"""
                            <div class="sniper-box">
                                <div class="sniper-titulo">{TITULOS_PREMIOS[i]}</div>
                                <div class="sniper-dado">Grupos: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_g >= LIMITE_GRUPO else '#4CAF50'};">{atr_g}x</span> <span class="sniper-recorde">Rec: {max_g}x</span></div>
                                <div class="sniper-dado">Centenas: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_c >= LIMITE_CENTENA else '#4CAF50'};">{atr_c}x</span> <span class="sniper-recorde">Rec: {max_c}x</span></div>
                                <div class="sniper-dado">Milhares: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_m >= LIMITE_MILHAR else '#4CAF50'};">{atr_m}x</span> <span class="sniper-recorde">Rec: {max_m}x</span></div>
                                {veredito}
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.error("Erro ao carregar base. Execute uma extração primeiro.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração e Automação")
    banca_ex = st.selectbox("Banca para Extração:", list(BANCAS_CONFIG.keys()))
    dt = st.date_input("Data do Sorteio:", value=date.today())
    if st.button("🚀 INICIAR COLETA", use_container_width=True):
        with st.spinner("Acessando servidores externos..."):
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
                        st.success(f"✅ Missão Cumprida: {len(p_ins)} novos registros salvos.")
                        carregar_dados_em_memoria.clear() 
                    else:
                        st.info("Todos os dados já estão no banco de dados.")
            else: st.error("Nenhum resultado disponível para esta data.")
