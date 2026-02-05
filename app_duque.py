import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, date, timedelta
import time
import re
from bs4 import BeautifulSoup
import altair as alt

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E ESTILO V29 ---
# =============================================================================
st.set_page_config(page_title="Central DUQUE V6.0 - Anti-Loss", page_icon="👑", layout="wide")

CONFIG_BANCA = {
    "display_name": "TRADICIONAL (Duque)",
    "slug": "loteria-tradicional",
    "logo_url": "https://cdn-icons-png.flaticon.com/512/1063/1063233.png", 
    "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"]
}

# Inicialização de Estados
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_g1' not in st.session_state: st.session_state['auto_g1'] = 1
if 'auto_g2' not in st.session_state: st.session_state['auto_g2'] = 2

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'apagar':
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    else: return
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

# --- CSS ESTILO PENTÁGONO V29 ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #1a002e 0%, #2E004F 100%); color: #ffffff; }
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown { color: #ffffff !important; }
    .stNumberInput input { color: white !important; background-color: rgba(255,255,255,0.1) !important; }
    [data-testid="stTable"] { color: white !important; background-color: transparent !important; }
    
    /* Bolinhas dos Setores (IGUAL PENTÁGONO) */
    .bola-s1 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 10px rgba(23, 162, 184, 0.5); }
    .bola-s2 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 10px rgba(253, 126, 20, 0.5); }
    .bola-s3 { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 10px rgba(220, 53, 69, 0.5); }
    
    /* Box do SNIPER DUQUE */
    .sniper-box { 
        background: linear-gradient(135deg, #004d00, #002b00); 
        border: 2px solid #00ff00; 
        padding: 20px; 
        border-radius: 15px; 
        margin-bottom: 20px; 
        text-align: center;
        box-shadow: 0px 0px 25px rgba(0, 255, 0, 0.3);
    }
    .sniper-title { font-size: 24px; font-weight: 900; color: #00ff00; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; text-shadow: 0 0 10px rgba(0,255,0,0.5); }
    .sniper-desc { font-size: 14px; color: #ccffcc; font-style: italic; margin-bottom: 15px; }
    
    /* BACKTEST STYLES */
    .backtest-container { display: flex; justify-content: center; gap: 15px; margin-top: 5px; margin-bottom: 30px; flex-wrap: wrap; }
    .bt-card { background-color: rgba(30, 30, 30, 0.8); border-radius: 10px; padding: 10px; width: 100px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 24px; margin-bottom: 5px; }
    .bt-num { font-size: 14px; font-weight: bold; margin-bottom: 2px; }
    .bt-label { font-size: 11px; opacity: 0.8; }
    
    .max-loss-info {
        text-align: center;
        background-color: rgba(255, 0, 0, 0.1);
        border: 1px solid rgba(255, 0, 0, 0.3);
        color: #ffaaaa;
        padding: 5px 15px;
        border-radius: 20px;
        display: inline-block;
        margin-top: 10px;
        font-size: 14px;
        font-weight: bold;
    }
    
    div[data-testid="stTable"] table { color: white; }
    thead tr th:first-child {display:none}
    tbody th {display:none}
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

def salvar_duque(b1, b2, horario, data_ref):
    worksheet = conectar_planilha()
    if worksheet:
        try:
            data_str = data_ref.strftime("%Y-%m-%d")
            worksheet.append_row([int(b1), int(b2), str(horario), data_str])
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

def montar_url_correta(slug, data_alvo):
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_duque_avancado(data_alvo, horario_alvo):
    url = montar_url_correta(CONFIG_BANCA['slug'], data_alvo)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, None, f"Erro HTTP {r.status_code}"
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        for tabela in tabelas:
            cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
            if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
            horario_encontrado = None
            prev = tabela.find_previous(string=padrao_hora)
            if prev:
                m = re.search(padrao_hora, prev)
                if m:
                    raw = m.group(1).strip()
                    if ':' in raw: horario_encontrado = raw
                    elif 'h' in raw: horario_encontrado = raw.replace('h', '').strip().zfill(2) + ":00"
                    else: horario_encontrado = raw.strip().zfill(2) + ":00"
            h_alvo_clean = horario_alvo.replace('h','').strip()
            if horario_encontrado == h_alvo_clean:
                bicho1 = None; bicho2 = None
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 3:
                        premio_txt = colunas[0].get_text().strip()
                        grp_txt = colunas[2].get_text().strip()
                        if grp_txt.isdigit():
                            grp = int(grp_txt)
                            nums = re.findall(r'\d+', premio_txt)
                            if nums:
                                pos = int(nums[0])
                                if pos == 1: bicho1 = grp
                                elif pos == 2: bicho2 = grp
                if bicho1 and bicho2: return bicho1, bicho2, "Sucesso"
                else: return None, None, "Horário encontrado, mas incompleto."
        return None, None, "Horário não encontrado nesta data."
    except Exception as e: return None, None, f"Erro: {e}"

# =============================================================================
# --- 3. LÓGICA V6.0 (ALGORITMO CAMALEÃO - ANTI LOSS) ---
# =============================================================================
def gerar_universo_duques():
    todos = []
    for i in range(1, 26):
        for j in range(i, 26): todos.append((i, j))
    setor1 = [d for k, d in enumerate(todos) if k % 3 == 0]
    setor2 = [d for k, d in enumerate(todos) if k % 3 == 1]
    setor3 = [d for k, d in enumerate(todos) if k % 3 == 2]
    return todos, {"S1": setor1, "S2": setor2, "S3": setor3}

def formatar_palpite_texto(lista_tuplas):
    lista_ordenada = sorted(list(set(lista_tuplas)))
    texto = ""
    for i, p in enumerate(lista_ordenada):
        texto += f"[{p[0]:02}-{p[1]:02}] "
        if (i + 1) % 10 == 0: texto += "\n" 
    return texto.strip()

# --- NOVO ALGORITMO CAMALEÃO V6 (PESO DINÂMICO PARA QUEBRAR SEQUÊNCIA) ---
def gerar_sniper_top200_v6(historico_slice):
    hist_rev = historico_slice[::-1]
    todos_duques, _ = gerar_universo_duques()
    
    # Pesos Base
    c_curto = Counter(hist_rev[:15]) # Curtíssimo prazo (muito quente)
    c_longo = Counter(hist_rev[:100]) # Consistência
    
    # Vício Imediato (O segredo para não perder em repetição)
    if len(historico_slice) > 0:
        ultimo = historico_slice[-1]
        bichos_vicio = set([ultimo[0], ultimo[1]])
        # Adiciona vizinhos também (ex: saiu 5, vicia o 4 e o 6)
        for b in list(bichos_vicio):
            bichos_vicio.add(b + 1 if b < 25 else 1)
            bichos_vicio.add(b - 1 if b > 1 else 25)
    else:
        bichos_vicio = set()

    scores = {}
    for d in todos_duques:
        score = 0
        # Peso 1: Frequência Recente (Explosão)
        score += c_curto[d] * 5.0
        
        # Peso 2: Frequência Longa (Segurança)
        score += c_longo[d] * 1.0
        
        # Peso 3: Vício Imediato (Proteção contra repetição)
        # Se o duque contém um bicho que acabou de sair, ganha MUITO ponto
        if d[0] in bichos_vicio or d[1] in bichos_vicio:
            score += 500.0 
            
        scores[d] = score
        
    # Ordena e pega os 200 melhores
    rank_final = sorted(scores.items(), key=lambda x: -x[1])
    top_200 = [d for d, s in rank_final][:200]
    
    # Ordena a lista final para ficar bonita visualmente
    return sorted(top_200)

# --- FUNÇÃO DE BACKTEST DUQUE ---
def executar_backtest_duque(historico):
    resultados_backtest = []
    # Analisa 4 jogos para trás
    for i in range(1, 5):
        if len(historico) <= i + 50: break 
        
        target_duque = tuple(sorted(historico[-i]))
        hist_treino = historico[:-i] 
        
        # Usa o V6 Camaleão
        sniper_past = gerar_sniper_top200_v6(hist_treino)
        
        win = target_duque in sniper_past
        
        resultados_backtest.append({
            "index": i,
            "duque_real": target_duque,
            "vitoria": win
        })
    return resultados_backtest

# --- CALCULAR RECORDE DE DERROTAS (50 JOGOS) ---
def calcular_max_derrotas_duque(historico):
    max_derrotas = 0
    derrotas_consecutivas_temp = 0
    range_analise = min(50, len(historico) - 50)
    start_idx = len(historico) - range_analise
    
    for i in range(start_idx, len(historico)):
        target_duque = tuple(sorted(historico[i]))
        hist_treino = historico[:i]
        
        sniper_past = gerar_sniper_top200_v6(hist_treino)
        win = target_duque in sniper_past
        
        if not win:
            derrotas_consecutivas_temp += 1
        else:
            if derrotas_consecutivas_temp > max_derrotas:
                max_derrotas = derrotas_consecutivas_temp
            derrotas_consecutivas_temp = 0
            
    if derrotas_consecutivas_temp > max_derrotas:
        max_derrotas = derrotas_consecutivas_temp
    return max_derrotas

def calcular_tabela_stress_visual(historico):
    _, mapa = gerar_universo_duques()
    recorte = historico[-20:] 
    total_recorte = len(recorte)
    stats = []
    for nome_setor, lista_duques in mapa.items():
        count = sum(1 for x in recorte if x in lista_duques)
        porcentagem = (count / total_recorte * 100) if total_recorte > 0 else 0
        stats.append({ "SETOR": nome_setor, "PRESENCA": porcentagem })
    return pd.DataFrame(stats)

# --- NOVA FUNÇÃO: GERAR BOLINHAS VISUAIS (IGUAL PENTÁGONO) ---
def gerar_bolinhas_recentes_duque(historico):
    _, mapa = gerar_universo_duques()
    html = "<div>"
    # Pega os últimos 12 resultados
    for duque in reversed(historico[-12:]):
        duque_sorted = tuple(sorted(duque))
        classe = ""
        letra = ""
        
        # Identifica a qual setor o duque pertence
        if duque_sorted in mapa["S1"]:
            classe = "bola-s1"
            letra = "S1"
        elif duque_sorted in mapa["S2"]:
            classe = "bola-s2"
            letra = "S2"
        elif duque_sorted in mapa["S3"]:
            classe = "bola-s3"
            letra = "S3"
        else:
            # Fallback raro
            classe = "bola-s1"
            letra = "?"
            
        html += f"<div class='{classe}'>{letra}</div>"
    html += "</div>"
    return html

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================
with st.sidebar:
    st.image(CONFIG_BANCA['logo_url'], width=100)
    st.title("MENU DUQUE")
    st.link_button("🔗 Ver Site Oficial", "https://www.resultadofacil.com.br")
    st.markdown("---")

    with st.expander("📥 Importar Resultado", expanded=True):
        opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
        if opcao_data == "Hoje": data_busca = date.today()
        elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
        else: data_busca = st.sidebar.date_input("Escolha:", date.today())
        horario_busca = st.selectbox("Horário:", CONFIG_BANCA['horarios'])
        
        if st.button("🚀 Baixar & Salvar"):
            with st.spinner(f"Buscando {horario_busca}..."):
                b1, b2, msg = raspar_duque_avancado(data_busca, horario_busca)
                if b1 and b2:
                    st.session_state['auto_g1'] = b1; st.session_state['auto_g2'] = b2
                    if salvar_duque(b1, b2, horario_busca, data_busca):
                        st.session_state['tocar_som_salvar'] = True
                        st.success(f"Salvo: {b1}-{b2}"); time.sleep(1); st.rerun()
                else: st.error(f"Erro: {msg}")

    st.markdown("---")
    st.write("🔧 **Ajuste Manual**")
    c1, c2 = st.columns(2)
    with c1: b1_in = st.number_input("1º Bicho", 1, 25, st.session_state['auto_g1'])
    with c2: b2_in = st.number_input("2º Bicho", 1, 25, st.session_state['auto_g2'])
    if st.button("💾 GRAVAR MANUAL"):
        if salvar_duque(b1_in, b2_in, horario_busca, data_busca):
            st.session_state['tocar_som_salvar'] = True
            st.toast("Salvo Manualmente!", icon="✅"); time.sleep(0.5); st.rerun()
            
    if st.button("🗑️ APAGAR ÚLTIMO"):
        if deletar_ultimo():
            st.session_state['tocar_som_apagar'] = True
            st.toast("Apagado!", icon="🗑️"); time.sleep(0.5); st.rerun()

historico, ultimo_horario_salvo = carregar_dados()
st.title(f"👑 {CONFIG_BANCA['display_name']}")

if len(historico) > 50:
    ult = historico[-1]
    st.caption(f"📅 Último Registro: {ult[0]:02}-{ult[1]:02} ({ultimo_horario_salvo}) | Total Jogos: {len(historico)}")
    
    # --- GERAR DADOS ---
    sniper_200 = gerar_sniper_top200_v6(historico)
    df_stress_vis = calcular_tabela_stress_visual(historico)
    bt_results = executar_backtest_duque(historico)
    max_loss_rec = calcular_max_derrotas_duque(historico)

    # --- BOX DO SNIPER TOP 200 (CAMALEÃO V6) ---
    st.markdown("""
    <div class="sniper-box">
        <div class="sniper-title">🎯 SNIPER DUQUE (V6 CAMALEÃO)</div>
        <div class="sniper-desc">Algoritmo Reativo: Adaptação Imediata ao Último Resultado.</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Exibe o indicador de Pior Sequência (Esperamos que caia para 1 ou 2)
    st.markdown(f"<div style='text-align:center;'><span class='max-loss-info'>📉 Pior Sequência (50 Jogos): {max_loss_rec} Derrotas</span></div>", unsafe_allow_html=True)
    
    # Exibe Cartões de Backtest
    if bt_results:
        cards_html = ""
        for res in reversed(bt_results):
            classe_res = "bt-win" if res['vitoria'] else "bt-loss"
            icon = "🟢" if res['vitoria'] else "❌"
            duque_str = f"{res['duque_real'][0]:02}-{res['duque_real'][1]:02}"
            cards_html += f"<div class='bt-card {classe_res}'><div class='bt-icon'>{icon}</div><div class='bt-num'>D: {duque_str}</div><div class='bt-label'>-{res['index']} Jogos</div></div>"
        final_html = f"<div class='backtest-container'>{cards_html}</div>"
        st.markdown(final_html, unsafe_allow_html=True)

    # Exibe o palpite formatado
    with st.expander("📋 Ver Lista de Jogos (200 Pares)", expanded=False):
        st.code(formatar_palpite_texto(sniper_200), language="text")

    st.markdown("---")
    
    # --- ÁREA DO RADAR DE SETORES E GRÁFICO ---
    st.subheader("📡 Radar de Setores (S1 / S2 / S3)")
    
    # 1. Bolinhas Visuais (NOVA FUNCIONALIDADE - IGUAL PENTÁGONO)
    st.markdown("**Visual Recente (⬅️ Mais Novo):**")
    st.markdown(gerar_bolinhas_recentes_duque(historico), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Gráfico de Rosca
    base = alt.Chart(df_stress_vis).encode(theta=alt.Theta("PRESENCA", stack=True))
    pie = base.mark_arc(outerRadius=120, innerRadius=60).encode(
        color=alt.Color("SETOR",
            scale=alt.Scale(domain=['S1', 'S2', 'S3'], range=['#17a2b8', '#fd7e14', '#dc3545']),
            legend=None 
        ),
        order=alt.Order("PRESENCA", sort="descending"),
        tooltip=["SETOR", alt.Tooltip("PRESENCA", format=".1f", title="% Presença (20 Jogos)")]
    )
    text = base.mark_text(radius=140).encode(
        text=alt.Text("PRESENCA", format=".1f"),
        order=alt.Order("PRESENCA", sort="descending"),
        color=alt.value("white")  
    )
    st.altair_chart(pie + text, use_container_width=True)
    
    st.markdown("**Tabela de Domínio Recente (20 Jogos):**")
    st.table(df_stress_vis.set_index("SETOR"))

    st.markdown("---")
    with st.expander("🔍 Ver Composição dos Setores (Base Fixa)"):
        _, mapa_copy = gerar_universo_duques()
        st.caption("Estes são os duques fixos que compõem cada setor:")
        st.text("🔵 Setor 1 (S1):")
        st.code(formatar_palpite_texto(mapa_copy["S1"]), language="text")
        st.text("🟠 Setor 2 (S2):")
        st.code(formatar_palpite_texto(mapa_copy["S2"]), language="text")
        st.text("🔴 Setor 3 (S3):")
        st.code(formatar_palpite_texto(mapa_copy["S3"]), language="text")

else:
    st.warning("⚠️ Base de dados insuficiente para o Sniper e Backtest. Adicione pelo menos 50 resultados na barra lateral.")
