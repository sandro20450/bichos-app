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

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS MOBILE E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V54 - Otimização 150 Jogos", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-numero { font-size: 20px; font-weight: bold; color: #ffffff; margin: 3px 0; }
.grupo-pontos { font-size: 11px; color: #4CAF50; font-weight: bold; }
.grupo-posicao { font-size: 9px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #1a2634; padding: 10px; border-radius: 5px; border-left: 4px solid #2196F3; margin-bottom: 10px;}
.alerta-tendencia { background-color: #331a00; border-left: 4px solid #ffb74d; padding: 8px; font-size: 13px; margin-top: 5px; border-radius: 4px;}
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

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {"Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"}

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO ---
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
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            if "FEDERAL" in txt_prev or "FEDERAL" in tab.get_text().upper(): continue 
            nome = txt_prev.split("-")[0].strip() if prev else "Sorteio"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V54")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🧠 Cérebro IA (Algoritmo)"])

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
            dados = extrair_dia(banca_sel, dt_alvo)
            if dados:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_sel])
                    inseridos, repetidos = salvar_sem_duplicar(ws, dados)
                    if inseridos > 0: st.success(f"✅ {inseridos} salvos!")
                    if repetidos > 0: st.warning(f"⚠️ {repetidos} já existiam.")
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1: dt_inicio = st.date_input("Inicial:", value=date.today() - timedelta(days=2))
        with col2: dt_fim = st.date_input("Final:", value=date.today())
        if st.button("🚀 SALVAR MASSA", use_container_width=True):
            todos = []
            for i in range((dt_fim - dt_inicio).days + 1): todos.extend(extrair_dia(banca_sel, dt_inicio + timedelta(days=i)))
            if todos:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_sel])
                    ins, rep = salvar_sem_duplicar(ws, todos)
                    if ins > 0: st.success(f"✅ {ins} novos salvos!")
    
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
# --- 5. TELA 2: CÉREBRO IA (RADAR OTIMIZADO PARA 150 JOGOS) ---
# =============================================================================
elif menu == "🧠 Cérebro IA (Algoritmo)":
    st.title("🧠 Algoritmo de Padrões (150 Jogos Otimizados)")
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_ia")
    
    def get_grupo(m):
        try:
            d = int(str(m)[-2:])
            return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
        except: return None
        
    def calcular_ranking_completo(df_analise):
        scores_tmp = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'semana': 0, 'total': 0} for i in range(1, 26)}
        atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
        for i in range(len(df_analise)):
            g_v = get_grupo(df_analise.iloc[i]["P1"])
            if g_v:
                for k in atr_g:
                    atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                    if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
        for k, v in atr_g.items():
            if v['t'] >= (v['max'] - 2) and v['t'] > 0: scores_tmp[k]['ruptura'] += 4  
        if len(df_analise) > 0:
            ult_g = get_grupo(df_analise.iloc[-1]["P1"])
            for i in range(len(df_analise)-1):
                if get_grupo(str(df_analise.iloc[i]["P1"]).zfill(4)) == ult_g:
                    g_p1 = get_grupo(df_analise.iloc[i+1]["P1"])
                    g_p2 = get_grupo(df_analise.iloc[i+1]["P2"])
                    if g_p1: scores_tmp[g_p1]['puxada'] += 7 
                    if g_p2: scores_tmp[g_p2]['puxada'] += 5 
            limite_data = df_analise['Data'].max() - timedelta(days=7)
            df_semana = df_analise[df_analise['Data'] >= limite_data]
            for i in range(len(df_semana)):
                for p in ["P1", "P2", "P3", "P4", "P5"]:
                    g_v = get_grupo(df_semana.iloc[i][p])
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
        return max_v, max_d

    # DOCUMENTAÇÃO: FUNÇÃO DE PREVISÃO AGORA LIMITADA A 150 JOGOS NO TEXTO
    def prever_tendencia(lista_booleanos):
        if len(lista_booleanos) < 5: return "Aguardando mais dados para traçar perfil."
        
        padrao_atual = lista_booleanos[-4:]
        vitorias_apos = 0
        derrotas_apos = 0
        
        for i in range(len(lista_booleanos) - 4):
            if lista_booleanos[i:i+4] == padrao_atual:
                if lista_booleanos[i+4] == True: vitorias_apos += 1
                else: derrotas_apos += 1
                
        total_ocorrencias = vitorias_apos + derrotas_apos
        padrao_emoji = "".join(["🟢" if x else "❌" for x in padrao_atual])
        
        if total_ocorrencias == 0:
            return f"A sequência de 4 ({padrao_emoji}) é inédita nos últimos 150 jogos."
            
        prob_vitoria = (vitorias_apos / total_ocorrencias) * 100
        
        if prob_vitoria > 50:
            return f"Com a sequência {padrao_emoji}, o algoritmo aponta 🟢 VITÓRIA em {prob_vitoria:.0f}% das vezes (Padrão encontrado {total_ocorrencias} vezes em 150 jogos)."
        elif prob_vitoria < 50:
            return f"Com a sequência {padrao_emoji}, o algoritmo aponta ❌ DERROTA em {(100-prob_vitoria):.0f}% das vezes (Padrão encontrado {total_ocorrencias} vezes em 150 jogos)."
        else:
            return f"A sequência {padrao_emoji} está Neutra (50% Vitória / 50% Derrota). (Padrão encontrado {total_ocorrencias} vezes em 150 jogos)."

    def renderizar_mobile(grupos, scores, inicio_pos, titulo):
        html = '<div class="flex-container">'
        for idx, grupo in enumerate(grupos):
            pts = scores[grupo]['total']
            html += f'<div class="grupo-card"><div class="grupo-posicao">{idx + inicio_pos}º {titulo}</div><div class="grupo-numero">{grupo}</div><div class="grupo-pontos">↑ {pts} pts</div></div>'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    if st.button("Processar Dados Matemáticos", use_container_width=True):
        with st.spinner("Processamento rápido: Compilando os 150 jogos mais recentes..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ia])
                    dados_brutos = ws.get_all_values()
                    
                    if len(dados_brutos) < 2: st.error("Dados insuficientes.")
                    else:
                        df = pd.DataFrame(dados_brutos)
                        for i in range(len(df.columns), 7): df[i] = ""
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        df = df[~df["P1"].astype(str).str.contains("---")]
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df = df[df["P1"].astype(str).str.lower() != "p1"]
                        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                        
                        # =================================================================
                        # ROTINA DE BACKTEST DUPLO (OTIMIZADO PARA 150 JOGOS)
                        # =================================================================
                        bool_5 = []; texto_5 = []
                        bool_16 = []; texto_16 = []
                        
                        # DOCUMENTAÇÃO: Máquina do tempo reduzida para 150 sorteios garantindo velocidade
                        qtd_testes = min(150, len(df) - 1) 
                        
                        if qtd_testes > 0:
                            for i in range(len(df) - qtd_testes, len(df)):
                                df_passado = df.iloc[:i].copy() 
                                sorteio_alvo = str(df.iloc[i]["Sorteio"]).strip()
                                
                                ranking_passado, _ = calcular_ranking_completo(df_passado)
                                top5_passado = ranking_passado[:5]
                                top16_passado = ranking_passado[5:21]
                                
                                g1_real = get_grupo(df.iloc[i]["P1"])
                                g2_real = get_grupo(df.iloc[i]["P2"])
                                
                                # Análise do Top 5
                                if (g1_real in top5_passado) or (g2_real in top5_passado):
                                    bool_5.append(True)
                                    if i >= len(df) - 5: texto_5.append(f"{sorteio_alvo} 🟢")
                                else:
                                    bool_5.append(False)
                                    if i >= len(df) - 5: texto_5.append(f"{sorteio_alvo} ❌")
                                    
                                # Análise dos 16 Secundários
                                if (g1_real in top16_passado) and (g2_real in top16_passado) and (g1_real != g2_real):
                                    bool_16.append(True)
                                    if i >= len(df) - 5: texto_16.append(f"{sorteio_alvo} 🟢")
                                else:
                                    bool_16.append(False)
                                    if i >= len(df) - 5: texto_16.append(f"{sorteio_alvo} ❌")

                        v_max_5, d_max_5 = contar_sequencias(bool_5)
                        v_max_16, d_max_16 = contar_sequencias(bool_16)
                        
                        tendencia_5 = prever_tendencia(bool_5)
                        tendencia_16 = prever_tendencia(bool_16)

                        # =================================================================
                        # CÁLCULO DO PRESENTE
                        # =================================================================
                        ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                        ult_nome = str(df.iloc[-1]["Sorteio"])
                        ult_g = get_grupo(ult_m)
                        
                        ranking_completo, scores = calcular_ranking_completo(df)
                        top_5_grupos = ranking_completo[:5]
                        proximos_16_grupos = ranking_completo[5:21]

                        # =================================================================
                        # RENDERIZAÇÃO NA TELA
                        # =================================================================
                        st.success(f"**Gatilho Identificado:** Sorteio {ult_nome} | Milhar {ult_m} | Grupo {ult_g}")
                        
                        # --- PAINEL 1: PELOTÃO DE FRENTE (TOP 5) ---
                        st.subheader("🎯 Pelotão de Frente: 5 Grupos Fixos")
                        st.markdown(f"""
                        <div class="backtest-box">
                            <b>Backtest Fixos (150 Jogos):</b> Recorde Vitórias: <span style='color:#4CAF50'>{v_max_5} 🟢</span> | Recorde Derrotas: <span style='color:#ff4b4b'>{d_max_5} ❌</span><br>
                            <span style='font-size:0.9em;'>Últimos 5: {' - '.join(texto_5) if texto_5 else 'Sem dados'}</span>
                            <div class="alerta-tendencia">🔮 <b>Alerta Tático:</b> {tendencia_5}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        renderizar_mobile(top_5_grupos, scores, inicio_pos=1, titulo="Fixo")
                        st.divider()
                        
                        # --- PAINEL 2: PELOTÃO DE COBERTURA (16 GRUPOS) ---
                        st.subheader("🛡️ Pelotão de Cobertura: Próximos 16 Grupos")
                        st.markdown(f"""
                        <div class="backtest-box">
                            <b>Backtest Duques (150 Jogos):</b> Recorde Vitórias: <span style='color:#4CAF50'>{v_max_16} 🟢</span> | Recorde Derrotas: <span style='color:#ff4b4b'>{d_max_16} ❌</span><br>
                            <span style='font-size:0.9em;'>Últimos 5: {' - '.join(texto_16) if texto_16 else 'Sem dados'}</span>
                            <div class="alerta-tendencia">🔮 <b>Alerta Tático:</b> {tendencia_16}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        renderizar_mobile(proximos_16_grupos, scores, inicio_pos=6, titulo="Lugar")
                        
                        # --- PAINEL 3: ARSENAL 120 DUQUES ---
                        st.write("⚔️ **Arsenal de Duques Gerados (120 Combinações):**")
                        top_16_ints = sorted([int(g) for g in proximos_16_grupos])
                        duplas_16 = list(itertools.combinations(top_16_ints, 2))
                        lista_formatada = [f"{str(d[0]).zfill(2)}-{str(d[1]).zfill(2)}" for d in duplas_16]
                        st.code("  |  ".join(lista_formatada), language="text")

            except Exception as e:
                st.error(f"Erro na conexão em tempo real: {e}")
