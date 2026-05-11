import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import itertools
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V56.5 - Comando Central", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-card-zebra { background-color: #330000; border: 1px solid #ff4b4b; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-numero { font-size: 20px; font-weight: bold; color: #ffffff; margin: 3px 0; }
.grupo-pontos { font-size: 11px; color: #4CAF50; font-weight: bold; }
.grupo-pontos-zebra { font-size: 11px; color: #ff4b4b; font-weight: bold; }
.grupo-posicao { font-size: 9px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #1a2634; padding: 10px; border-radius: 5px; border-left: 4px solid #2196F3; margin-bottom: 10px;}
.alerta-tendencia { background-color: #331a00; border-left: 4px solid #ffb74d; padding: 8px; font-size: 13px; margin-top: 5px; border-radius: 4px;}
.gatilho-ativo { background-color: #003300; border-left: 4px solid #00ff00; padding: 10px; margin-top: 10px; border-radius: 5px; color: #00ff00; font-weight: bold;}
.gatilho-espera { background-color: #1a1a1a; border-left: 4px solid #555555; padding: 10px; margin-top: 10px; border-radius: 5px; color: #aaaaaa; font-size: 13px;}

/* Estilo para os cards de previsão da IA expandido para 12 */
.previsao-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px; min-height: 120px; }
.previsao-num { font-size: 28px; font-weight: bold; color: #4CAF50; line-height: 1.1; }
.previsao-chance { font-size: 12px; color: #aaa; }
.bicho-nome { font-size: 14px; color: #fff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

def salvar_sem_duplicar(ws, dados_novos):
    try:
        existentes = ws.get_all_values()
        set_existentes = set()
        for row in existentes:
            if len(row) >= 2:
                set_existentes.add(f"{str(row[0]).strip()}_{str(row[1]).strip()}")
        
        para_inserir = []
        duplicados = 0
        for linha in dados_novos:
            chave = f"{str(linha[0]).strip()}_{str(linha[1]).strip()}"
            if chave in set_existentes: duplicados += 1
            else:
                para_inserir.append(linha)
                set_existentes.add(chave)
                
        if para_inserir: ws.append_rows(para_inserir, value_input_option="RAW")
        return len(para_inserir), duplicados
    except Exception as e:
        return 0, 0

MAPA_ABAS = {
    "Tradicional": "TRADICIONAL_MILHAR", 
    "Caminho da Sorte": "CAMINHO_MILHAR", 
    "Monte Carlos": "MONTE_MILHAR", 
    "Lotep": "LOTEP_MILHAR"
}

BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

BICHOS_DICT = {
    1:"Avestruz", 2:"Águia", 3:"Burro", 4:"Borboleta", 5:"Cachorro",
    6:"Cabra", 7:"Carneiro", 8:"Camelo", 9:"Cobra", 10:"Coelho",
    11:"Cavalo", 12:"Elefante", 13:"Galo", 14:"Gato", 15:"Jacaré",
    16:"Leão", 17:"Macaco", 18:"Porco", 19:"Pavão", 20:"Peru",
    21:"Touro", 22:"Tigre", 23:"Urso", 24:"Veado", 25:"Vaca"
}

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

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO E ESTATÍSTICA TRADICIONAL ---
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
            caption = tab.find('caption')
            txt_caption = caption.get_text().upper() if caption else ""
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            
            texto_alvo = txt_prev
            for t in [txt_caption, txt_th, txt_prev]:
                if re.search(r'\d{2}:\d{2}h?|\d{2}h', t, re.IGNORECASE) or "PT" in t.upper():
                    texto_alvo = t
                    break

            if "FEDERAL" in texto_alvo.upper(): continue

            match_hora = re.search(r'(\d{2}):(\d{2})h?|(\d{2})h', texto_alvo, re.IGNORECASE)
            
            if banca in ["Caminho da Sorte", "Monte Carlos", "Lotep"]:
                if match_hora:
                    nome = f"{match_hora.group(3)}:00" if match_hora.group(3) else f"{match_hora.group(1)}:{match_hora.group(2)}"
                else: continue 
            else:
                if match_hora:
                    nome = f"{match_hora.group(3)}:00" if match_hora.group(3) else f"{match_hora.group(1)}:{match_hora.group(2)}"
                else:
                    nome = texto_alvo.split("-")[0].replace("RESULTADO", "").replace("LOTEP", "").strip()
                    if not nome: nome = "Sorteio Extra"

            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            
            if len(milhares) >= 5:
                eh_clone = any(milhares[0] == r[2] and milhares[1] == r[3] for r in resultados)
                if not eh_clone: resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
                
        return resultados
    except: return []

def calcular_ranking_completo(df_analise):
    scores_tmp = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'semana': 0, 'total': 0} for i in range(1, 26)}
    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
    for i in range(len(df_analise)):
        g_v = get_grupo_str(df_analise.iloc[i]["P1"])
        if g_v:
            for k in atr_g:
                atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
    for k, v in atr_g.items():
        if v['t'] >= (v['max'] - 2) and v['t'] > 0: scores_tmp[k]['ruptura'] += 4  
    if len(df_analise) > 0:
        ult_g = get_grupo_str(df_analise.iloc[-1]["P1"])
        for i in range(len(df_analise)-1):
            if get_grupo_str(str(df_analise.iloc[i]["P1"]).zfill(4)) == ult_g:
                g_p1 = get_grupo_str(df_analise.iloc[i+1]["P1"])
                g_p2 = get_grupo_str(df_analise.iloc[i+1]["P2"])
                if g_p1: scores_tmp[g_p1]['puxada'] += 7 
                if g_p2: scores_tmp[g_p2]['puxada'] += 5 
        limite_data = pd.to_datetime(df_analise['Data']).max() - timedelta(days=7)
        df_semana = df_analise[pd.to_datetime(df_analise['Data']) >= limite_data]
        for i in range(len(df_semana)):
            for p in ["P1", "P2", "P3", "P4", "P5"]:
                g_v = get_grupo_str(df_semana.iloc[i][p])
                if g_v: scores_tmp[g_v]['semana'] += 2
    for k in scores_tmp: scores_tmp[k]['total'] = scores_tmp[k]['puxada'] + scores_tmp[k]['ruptura'] + scores_tmp[k]['semana']
    ranking_tmp = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
    return [x[0] for x in ranking_tmp], scores_tmp

def contar_sequencias(lista_booleanos):
    max_v = 0; max_d = 0; vit_a = 0; der_a = 0
    for res in lista_booleanos:
        if res:
            vit_a += 1; der_a = 0
            if vit_a > max_v: max_v = vit_a
        else:
            der_a += 1; vit_a = 0
            if der_a > max_d: max_d = der_a
    return max_v, max_d, vit_a, der_a

def prever_tendencia(lista_booleanos):
    if len(lista_booleanos) < 5: return "Aguardando mais dados para traçar perfil."
    padrao_atual = lista_booleanos[-4:]
    vitorias_apos = 0; derrotas_apos = 0
    for i in range(len(lista_booleanos) - 4):
        if lista_booleanos[i:i+4] == padrao_atual:
            if lista_booleanos[i+4] == True: vitorias_apos += 1
            else: derrotas_apos += 1
    total_ocorrencias = vitorias_apos + derrotas_apos
    padrao_emoji = "".join(["🟢" if x else "❌" for x in padrao_atual])
    if total_ocorrencias == 0: return f"A sequência ({padrao_emoji}) é inédita."
    prob_vitoria = (vitorias_apos / total_ocorrencias) * 100
    if prob_vitoria > 50: return f"Com a sequência {padrao_emoji}, a IA aponta 🟢 VITÓRIA em {prob_vitoria:.0f}% (Ocorreu {total_ocorrencias}x)."
    elif prob_vitoria < 50: return f"Com a sequência {padrao_emoji}, a IA aponta ❌ DERROTA em {(100-prob_vitoria):.0f}% (Ocorreu {total_ocorrencias}x)."
    else: return f"Sequência Neutra 50/50. (Ocorreu {total_ocorrencias}x)."

def renderizar_mobile(grupos, scores, inicio_pos, titulo, is_zebra=False):
    html = '<div class="flex-container">'
    card_class = "grupo-card-zebra" if is_zebra else "grupo-card"
    pts_class = "grupo-pontos-zebra" if is_zebra else "grupo-pontos"
    for idx, grupo in enumerate(grupos):
        pts = scores[grupo]['total']
        html += f'<div class="{card_class}"><div class="grupo-posicao">{idx + inicio_pos}º {titulo}</div><div class="grupo-numero">{grupo}</div><div class="{pts_class}">↑ {pts} pts</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# =============================================================================
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V56.5")
    menu = st.radio("Selecione a Base:", [
        "📡 Extração & Automação", 
        "📊 Estatística Tradicional", 
        "🤖 Radar IA Pentágono (XGBoost)"
    ])

# =============================================================================
# --- 4. TELA 1: EXTRAÇÃO MULTI-MODAL ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    tab1, tab2, tab3 = st.tabs(["📅 Dia Específico", "🚀 Extração em Massa", "✍️ Inserção Manual"])
    
    with tab1:
        dt_alvo = st.date_input("Data do Sorteio:", value=date.today(), key="data_unica")
        if st.button("🚀 EXTRAIR E SALVAR", use_container_width=True):
            with st.spinner("Extraindo..."):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, dados)
                        if inseridos > 0: st.success(f"✅ {inseridos} sorteios salvos com sucesso!")
                        if repetidos > 0: st.warning(f"⚠️ {repetidos} já existiam na base.")
                else: st.error("Nenhum dado válido retornado do site.")
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1: dt_inicio = st.date_input("Inicial:", value=date.today() - timedelta(days=2))
        with col2: dt_fim = st.date_input("Final:", value=date.today())
        if st.button("🚀 SALVAR MASSA", use_container_width=True):
            with st.spinner("Varrendo histórico..."):
                todos = []
                for i in range((dt_fim - dt_inicio).days + 1): todos.extend(extrair_dia(banca_sel, dt_inicio + timedelta(days=i)))
                if todos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        ins, rep = salvar_sem_duplicar(ws, todos)
                        if ins > 0: st.success(f"✅ {ins} novos salvos!")
                else: st.error("Nenhum resultado no período.")
    
    with tab3:
        df_manual = pd.DataFrame([{"Data": date.today().strftime('%Y-%m-%d'), "Sorteio": "", "1º": "", "2º": "", "3º": "", "4º": "", "5º": ""}], dtype=str)
        df_editado = st.data_editor(df_manual, num_rows="dynamic", use_container_width=True)
        if st.button("💾 SALVAR MANUAIS", use_container_width=True):
            limpos = []
            for r in df_editado.values.tolist():
                if str(r[1]).strip() not in ["", "nan", "None"]:
                    linha = [str(r[0]).strip(), str(r[1]).strip()]
                    for v in r[2:7]: linha.append("" if str(v) == "" or str(v).lower() in ["nan", "none"] else str(v).replace(".0", "").strip().zfill(4))
                    limpos.append(linha)
            if limpos:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_sel])
                    ins, rep = salvar_sem_duplicar(ws, limpos)
                    if ins > 0: st.success(f"✅ {ins} inseridos!")

# =============================================================================
# --- 5. TELA 2: ESTATÍSTICA TRADICIONAL ---
# =============================================================================
elif menu == "📊 Estatística Tradicional":
    st.title("📊 Algoritmo de Cobertura Total (V56.5)")
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_estatistica")
    
    if st.button("Processar Dados Matemáticos", use_container_width=True):
        with st.spinner("Processando Inteligência de Dados (150 Jogos)..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ia])
                    dados_brutos = ws.get_all_values()
                    
                    if len(dados_brutos) < 2: st.error("Dados insuficientes.")
                    else:
                        df = pd.DataFrame(dados_brutos[1:], columns=dados_brutos[0])
                        for i in range(len(df.columns), 7): df[i] = ""
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        df = df[~df["P1"].astype(str).str.contains("---")]
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df = df[df["P1"].astype(str).str.lower() != "p1"]
                        
                        bool_5 = []; texto_5 = []
                        bool_16 = []; texto_16 = []
                        bool_cegos = []; texto_cegos = []
                        
                        qtd_testes = min(150, len(df) - 1) 
                        
                        if qtd_testes > 0:
                            for i in range(len(df) - qtd_testes, len(df)):
                                df_passado = df.iloc[:i].copy() 
                                sorteio_alvo = str(df.iloc[i]["Sorteio"]).strip()
                                
                                ranking_passado, _ = calcular_ranking_completo(df_passado)
                                top5_passado = ranking_passado[:5]
                                top16_passado = ranking_passado[5:21]
                                top6_cegos_passado = ranking_passado[19:25] 
                                
                                g1_real = get_grupo_str(df.iloc[i]["P1"])
                                g2_real = get_grupo_str(df.iloc[i]["P2"])
                                
                                if (g1_real in top5_passado) or (g2_real in top5_passado):
                                    bool_5.append(True)
                                    if i >= len(df) - 10: texto_5.append(f"{sorteio_alvo} 🟢")
                                else:
                                    bool_5.append(False)
                                    if i >= len(df) - 10: texto_5.append(f"{sorteio_alvo} ❌")
                                    
                                if (g1_real in top16_passado) and (g2_real in top16_passado) and (g1_real != g2_real):
                                    bool_16.append(True)
                                    if i >= len(df) - 10: texto_16.append(f"{sorteio_alvo} 🟢")
                                else:
                                    bool_16.append(False)
                                    if i >= len(df) - 10: texto_16.append(f"{sorteio_alvo} ❌")
                                    
                                if g1_real in top6_cegos_passado:
                                    bool_cegos.append(True)
                                    if i >= len(df) - 10: texto_cegos.append(f"{sorteio_alvo} 🟢 (ZEBRA NO 1º!)")
                                else:
                                    bool_cegos.append(False)
                                    if i >= len(df) - 10: texto_cegos.append(f"{sorteio_alvo} ❌")

                        v_max_5, d_max_5, v_atual_5, d_atual_5 = contar_sequencias(bool_5)
                        v_max_16, d_max_16, v_atual_16, d_atual_16 = contar_sequencias(bool_16)
                        v_max_c, d_max_c, v_atual_c, d_atual_c = contar_sequencias(bool_cegos)
                        
                        tendencia_5 = prever_tendencia(bool_5)
                        tendencia_16 = prever_tendencia(bool_16)

                        ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                        ult_nome = str(df.iloc[-1]["Sorteio"])
                        ult_g = get_grupo_str(ult_m)
                        
                        ranking_completo, scores = calcular_ranking_completo(df)
                        top_5_grupos = ranking_completo[:5]
                        proximos_16_grupos = ranking_completo[5:21]
                        pontos_cegos = ranking_completo[19:25]

                        st.success(f"**Gatilho Identificado:** Sorteio {ult_nome} | Milhar {ult_m} | Grupo {ult_g}")
                        
                        st.subheader("🎯 Pelotão de Frente: 5 Grupos Fixos")
                        st.markdown(f"""
                        <div class="backtest-box">
                            <b>Backtest Fixos (150 Jogos):</b> Recorde Vitórias: <span style='color:#4CAF50'>{v_max_5} 🟢</span> | Recorde Derrotas: <span style='color:#ff4b4b'>{d_max_5} ❌</span><br>
                            <span style='font-size:0.9em;'>Últimos 10: {' - '.join(texto_5) if texto_5 else 'Sem dados'}</span>
                            <div class="alerta-tendencia">🔮 <b>Alerta Tático:</b> {tendencia_5}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        renderizar_mobile(top_5_grupos, scores, inicio_pos=1, titulo="Fixo")
                        st.divider()
                        
                        st.subheader("🛡️ Pelotão de Cobertura: Próximos 16 Grupos")
                        st.markdown(f"""
                        <div class="backtest-box">
                            <b>Backtest Duques (150 Jogos):</b> Recorde Vitórias: <span style='color:#4CAF50'>{v_max_16} 🟢</span> | Recorde Derrotas: <span style='color:#ff4b4b'>{d_max_16} ❌</span><br>
                            <span style='font-size:0.9em;'>Últimos 10: {' - '.join(texto_16) if texto_16 else 'Sem dados'}</span>
                            <div class="alerta-tendencia">🔮 <b>Alerta Tático:</b> {tendencia_16}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        renderizar_mobile(proximos_16_grupos, scores, inicio_pos=6, titulo="Lugar")
                        
                        st.write("⚔️ **Arsenal de Duques (120 Combinações):**")
                        top_16_ints = sorted([int(g) for g in proximos_16_grupos])
                        duplas_16 = list(itertools.combinations(top_16_ints, 2))
                        st.code("  |  ".join([f"{str(d[0]).zfill(2)}-{str(d[1]).zfill(2)}" for d in duplas_16]), language="text")
                        st.divider()

                        st.subheader("🚨 Radar de Exclusão: 6 Grupos Zebra")
                        st.markdown(f"""
                        <div class="backtest-box" style="border-left-color: #ff4b4b;">
                            <b>Histórico da Zebra (150 Jogos):</b> Recorde Máximo da Zebra no 1º Prêmio: <span style='color:#ff4b4b'>{v_max_c} vezes seguidas 🟢</span><br>
                            <span style='font-size:0.9em;'>Últimos 10: {' - '.join(texto_cegos) if texto_cegos else 'Sem dados'}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if v_max_c > 0 and v_atual_c >= (v_max_c - 1) and v_atual_c > 0:
                            st.markdown(f"""<div class="gatilho-ativo">🚀 GATILHO TÁTICO ATIVADO! A Zebra saiu {v_atual_c}x seguidas e encostou no limite histórico de {v_max_c}x! A probabilidade de reversão à média é extrema. OPORTUNIDADE DE ENTRADA NOS GRUPOS PRINCIPAIS!</div>""", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""<div class="gatilho-espera">⏳ Status: Aguardando exaustão da Zebra. (A Zebra saiu {v_atual_c}x seguidas atualmente. O limite histórico é {v_max_c}x).</div>""", unsafe_allow_html=True)
                        
                        renderizar_mobile(pontos_cegos, scores, inicio_pos=20, titulo="Zebra", is_zebra=True)

            except Exception as e:
                st.error(f"Erro na conexão em tempo real: {e}")

# =============================================================================
# --- 6. TELA 3: CÉREBRO IA PENTÁGONO (XGBOOST - 12 ALVOS) OTIMIZADO ---
# =============================================================================
elif menu == "🤖 Radar IA Pentágono (XGBoost)":
    st.title("🤖 Radar Preditivo Pentágono (12 Alvos IA)")
    banca_xgb = st.selectbox("Selecione a Banca Alvo para Previsão IA:", list(BANCAS_CONFIG.keys()), key="sel_banca_xgb")
    
    st.info("💡 A IA (Gradiente Boosting) utiliza Validação Cruzada (Cross-Validation) e GridSearchCV para auto-ajustar seus hiperparâmetros antes de prever o próximo resultado.")
    
    if st.button("🚀 Ativar Cérebro Pentágono (Treinar e Otimizar IA)", use_container_width=True, type="primary"):
        with st.spinner("Lendo base de dados e preparando treinamento pesado..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_xgb])
                    dados_brutos = ws.get_all_values()
                    
                    if len(dados_brutos) < 50:
                        st.error("⚠️ Dados insuficientes (mínimo 50 sorteios).")
                    else:
                        df = pd.DataFrame(dados_brutos[1:], columns=dados_brutos[0])
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df['grupo_alvo'] = df['P1'].apply(get_grupo_int)
                        df = df.dropna(subset=['grupo_alvo']).copy()
                        
                        df['ant_1'] = df['grupo_alvo'].shift(1)
                        df['ant_2'] = df['grupo_alvo'].shift(2)
                        df['ant_3'] = df['grupo_alvo'].shift(3)
                        df_treino = df.dropna().tail(500)
                        
                        # --- NOVA ARTILHARIA: GridSearchCV, CV e Early Stopping ---
                        X = df_treino[['ant_1', 'ant_2', 'ant_3']]
                        y = df_treino['grupo_alvo']
                        
                        le = LabelEncoder()
                        y_encoded = le.fit_transform(y)
                        num_classes_reais = len(le.classes_)
                        
                        X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)
                        
                        st.warning("⚙️ Otimizando motor com GridSearchCV e Validação Cruzada... Aguarde.")
                        
                        # 1. GridSearchCV: A IA testa as configurações para não sofrer overfitting
                        param_grid = {
                            'max_depth': [3, 4, 5],
                            'learning_rate': [0.05, 0.1, 0.2],
                            'n_estimators': [50, 100]
                        }
                        
                        modelo_base = xgb.XGBClassifier(
                            objective='multi:softprob', 
                            num_class=num_classes_reais, 
                            eval_metric='mlogloss'
                        )
                        
                        grid_search = GridSearchCV(
                            estimator=modelo_base,
                            param_grid=param_grid,
                            cv=3, # Cross-Validation 3 folds
                            scoring='accuracy',
                            n_jobs=-1
                        )
                        
                        grid_search.fit(X_train, y_train)
                        melhores_parametros = grid_search.best_params_
                        st.info(f"🔧 **Auto-ajuste concluído! Parâmetros adotados:** {melhores_parametros}")
                        
                        # 2. Treinamento Final com Early Stopping
                        modelo_final = xgb.XGBClassifier(
                            **melhores_parametros,
                            objective='multi:softprob',
                            num_class=num_classes_reais,
                            eval_metric='mlogloss',
                            early_stopping_rounds=10 # Trava se não evoluir
                        )
                        
                        modelo_final.fit(
                            X_train, y_train,
                            eval_set=[(X_test, y_test)],
                            verbose=False
                        )
                        
                        precisao = accuracy_score(y_test, modelo_final.predict(X_test))
                        st.success(f"✅ Inteligência Calibrada com Sucesso! Precisão Validada (OOS): {precisao*100:.2f}%")
                        
                        # 3. Previsão para os 12 próximos alvos
                        ultimos_3 = df['grupo_alvo'].tail(3).values
                        if len(ultimos_3) == 3:
                            entrada = pd.DataFrame({'ant_1':[ultimos_3[2]], 'ant_2':[ultimos_3[1]], 'ant_3':[ultimos_3[0]]})
                            probabilidades = modelo_final.predict_proba(entrada)[0]
                            
                            top_12_idx = np.argsort(probabilidades)[::-1][:12]
                            
                            st.markdown("### 🔮 Projeção dos 12 Grupos Mais Quentes (1º Prêmio):")
                            
                            for row in range(4):
                                cols = st.columns(3)
                                for col in range(3):
                                    index_list = row * 3 + col
                                    if index_list < 12:
                                        idx = top_12_idx[index_list]
                                        grupo_real = int(le.inverse_transform([idx])[0])
                                        chance = probabilidades[idx] * 100
                                        nome_bicho = BICHOS_DICT.get(grupo_real, "---")
                                        
                                        with cols[col]:
                                            st.markdown(f"""
                                            <div class="previsao-card">
                                                <div style="color:#4CAF50; font-size:11px; font-weight:bold;">{index_list+1}º ALVO IA</div>
                                                <div class="previsao-num">{str(grupo_real).zfill(2)}</div>
                                                <div class="bicho-nome">{nome_bicho}</div>
                                                <div class="previsao-chance">Força: {chance:.1f}%</div>
                                            </div>
                                            """, unsafe_allow_html=True)
                        else:
                            st.warning("Histórico recente insuficiente para formar a base de previsão (precisa de pelo menos 3 sorteios).")
            except Exception as e:
                st.error(f"Erro Crítico no Motor de IA: {e}")
