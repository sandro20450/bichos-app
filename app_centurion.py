import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time
import altair as alt
from collections import Counter

# --- IMPORTAÇÃO DA INTELIGÊNCIA ARTIFICIAL ---
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    HAS_AI = True
except ImportError:
    HAS_AI = False

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V47.0 Native", page_icon="🛡️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": { "display_name": "LOTEP (1º ao 5º)", "nome_aba": "LOTEP_TOP5", "slug": "lotep", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHODASORTE": { "display_name": "CAMINHO (1º ao 5º)", "nome_aba": "CAMINHO_TOP5", "slug": "caminho-da-sorte", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "MONTECAI": { "display_name": "MONTE CARLOS (1º ao 5º)", "nome_aba": "MONTE_TOP5", "slug": "nordeste-monte-carlos", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] }
}

# SETORES DUAL
SETORES = {
    "BAIXO (01-16)": list(range(1, 17)),
    "ALTO (17-24)": list(range(17, 25)),
    "VACA (25)": [25]
}

GRUPOS_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
    dezenas = []
    for n in range(inicio, fim + 1):
        if n == 100: dezenas.append("00")
        else: dezenas.append(f"{n:02}")
    GRUPOS_DEZENAS[g] = dezenas

if 'tocar_som' not in st.session_state: st.session_state['tocar_som'] = False

# Ajuste visual mínimo para tabelas no modo dark
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E LÓGICA (SEM CACHE) ---
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_dados_top5(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        raw = ws.get_all_values()
        if len(raw) < 2: return []
        dados_processados = []
        for row in raw[1:]:
            if len(row) >= 7:
                try:
                    premios = [int(p) for p in row[2:7] if p.isdigit()]
                    if len(premios) == 5:
                        dados_processados.append({ "data": row[0], "horario": row[1], "premios": premios })
                except: pass
        return dados_processados
    return []

# --- CÉREBRO IA ---
def treinar_oraculo_pentagono(historico, indice_premio):
    if not HAS_AI or len(historico) < 50: return [], 0
    df = pd.DataFrame(historico)
    df['data_dt'] = pd.to_datetime(df['data'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['data_dt']) 
    df['dia_semana'] = df['data_dt'].dt.dayofweek 
    le_hora = LabelEncoder()
    df['hora_code'] = le_hora.fit_transform(df['horario'])
    bichos_alvo = [jogo['premios'][indice_premio] for jogo in historico if 'data_dt' in df.columns]
    df = df.iloc[:len(bichos_alvo)]
    df['target_grupo'] = bichos_alvo
    df['target_futuro'] = df['target_grupo'].shift(-1)
    df_treino = df.dropna().tail(200)
    if len(df_treino) < 30: return [], 0
    X = df_treino[['dia_semana', 'hora_code', 'target_grupo']]
    y = df_treino['target_futuro']
    modelo = RandomForestClassifier(n_estimators=50, random_state=42)
    modelo.fit(X, y)
    ultimo_real = df.iloc[-1]
    X_novo = pd.DataFrame({
        'dia_semana': [ultimo_real['dia_semana']],
        'hora_code': [ultimo_real['hora_code']],
        'target_grupo': [ultimo_real['target_grupo']]
    })
    probs = modelo.predict_proba(X_novo)[0]
    classes = modelo.classes_
    ranking_ia = []
    for i, prob in enumerate(probs):
        grupo = int(classes[i])
        ranking_ia.append((grupo, prob))
    ranking_ia.sort(key=lambda x: x[1], reverse=True)
    top_ia = [x[0] for x in ranking_ia[:8]] 
    confianca = ranking_ia[0][1] * 100
    return top_ia, confianca

# --- BACKTEST DA IA ---
def executar_backtest_ia(historico, indice_premio):
    if not HAS_AI or len(historico) < 60: return []
    resultados = []
    for i in range(1, 6):
        target_idx = -i
        target_game = historico[target_idx]
        target_num = target_game['premios'][indice_premio]
        hist_treino = historico[:target_idx]
        top_8_prev, _ = treinar_oraculo_pentagono(hist_treino, indice_premio)
        win = target_num in top_8_prev
        resultados.append({'index': i, 'numero_real': target_num, 'vitoria': win})
    return resultados

def calcular_max_derrotas_ia_50(historico, indice_premio):
    if not HAS_AI or len(historico) < 60: return 0
    max_derrotas = 0; derrotas_consecutivas_temp = 0
    range_analise = min(50, len(historico) - 50)
    start_idx = len(historico) - range_analise
    for i in range(start_idx, len(historico)):
        target_game = historico[i]
        target_num = target_game['premios'][indice_premio]
        hist_treino = historico[:i]
        top_8_prev, _ = treinar_oraculo_pentagono(hist_treino, indice_premio)
        win = target_num in top_8_prev
        if not win: derrotas_consecutivas_temp += 1
        else:
            if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
            derrotas_consecutivas_temp = 0
    if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
    return max_derrotas

def obter_proxima_batalha(banca_key, ultimo_horario_str):
    horarios = CONFIG_BANCAS[banca_key]['horarios']
    try:
        uh_clean = ultimo_horario_str.replace('h', '').strip()
        if ':' not in uh_clean and len(uh_clean) <= 2: uh_clean += ":00"
        idx = -1
        for i, h in enumerate(horarios):
            if h == uh_clean or h.replace(':00', '') == uh_clean.replace(':00', ''):
                idx = i
                break
        if idx != -1:
            if idx == len(horarios) - 1: return f"AMANHÃ AS {horarios[0]} HS"
            else: return f"HOJE AS {horarios[idx+1]} HS"
        else: return "PRÓXIMO SORTEIO" 
    except: return "PRÓXIMO SORTEIO"

def calcular_stress_tabela(historico, indice_premio):
    stats = []
    total_jogos = len(historico)
    for nome_setor, lista_bichos in SETORES.items():
        max_atraso = 0; curr_atraso = 0; max_seq_v = 0; curr_seq_v = 0; total_vitorias = 0
        for jogo in historico:
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos:
                total_vitorias += 1; curr_seq_v += 1
                if curr_atraso > max_atraso: max_atraso = curr_atraso
                curr_atraso = 0
            else:
                if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
                curr_seq_v = 0; curr_atraso += 1
        if curr_atraso > max_atraso: max_atraso = curr_atraso
        if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
        atraso_real = 0
        for jogo in reversed(historico):
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos: break
            atraso_real += 1
        seq_atual = 0
        for jogo in reversed(historico):
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos: seq_atual += 1
            else: break
        porcentagem = (total_vitorias / total_jogos * 100) if total_jogos > 0 else 0
        stats.append({ "SETOR": nome_setor, "% PRESENÇA": porcentagem, "ATRASO": atraso_real, "REC. ATRASO": max_atraso, "SEQ. ATUAL": seq_atual, "REC. SEQ. (V)": max_seq_v })
    return pd.DataFrame(stats)

def calcular_ciclo(historico, indice_premio):
    ciclos_fechados = []
    bichos_vistos = set()
    contador_jogos = 0
    for jogo in historico:
        bicho = jogo['premios'][indice_premio]
        contador_jogos += 1
        bichos_vistos.add(bicho)
        if len(bichos_vistos) == 25:
            ciclos_fechados.append(contador_jogos)
            bichos_vistos = set()
            contador_jogos = 0
    faltam = list(set(range(1, 26)) - bichos_vistos)
    media = sum(ciclos_fechados) / len(ciclos_fechados) if ciclos_fechados else 0
    return { "vistos": len(bichos_vistos), "jogos_atual": contador_jogos, "media_historica": media, "faltam": sorted(faltam) }

def calcular_tabela_diamante(historico, indice_premio):
    janela = 30
    recorte = historico[-janela:]
    recorte_invertido = recorte[::-1] 
    if len(recorte) < 10: return pd.DataFrame()
    contagem = {}
    ultimo_visto = {} 
    for i, jogo in enumerate(recorte_invertido):
        bicho = jogo['premios'][indice_premio]
        contagem[bicho] = contagem.get(bicho, 0) + 1
        if bicho not in ultimo_visto: ultimo_visto[bicho] = i
    tabela_dados = []
    for bicho, qtd in contagem.items():
        if qtd >= 3:
            media = 30 / qtd
            atraso_atual = ultimo_visto.get(bicho, 0)
            status = ""
            if atraso_atual <= 2: status = "Saiu Agora (Aguarde)"
            elif atraso_atual >= media: status = "🔥 PONTO DE ENTRADA"
            elif atraso_atual >= (media * 0.6): status = "⏳ Aquece (Quase lá)"
            else: status = "Neutro"
            tabela_dados.append({ "GRUPO": bicho, "SAÍDAS (30 Jogos)": qtd, "MÉDIA": f"1 a cada {media:.1f}", "ÚLTIMA VEZ": f"Há {atraso_atual} jogos", "STATUS / DICA": status })
    def sort_key(x):
        s = x['STATUS / DICA']
        if "🔥" in s: return 0
        if "⏳" in s: return 1
        return 2
    tabela_dados.sort(key=sort_key)
    return pd.DataFrame(tabela_dados)

def identificar_saturados(historico, indice_premio):
    recorte = historico[-50:]
    if len(recorte) < 20: return []
    contagem = Counter([jogo['premios'][indice_premio] for jogo in recorte])
    saturados = [grp for grp, qtd in contagem.items() if qtd >= 7]
    if not saturados:
        saturados = [grp for grp, qtd in contagem.items() if qtd >= 6]
    return saturados

def gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados):
    # Identifica reversão em qualquer setor
    setor_estourado = None
    for index, row in df_stress.iterrows():
        if "VACA" not in row['SETOR']:
            if row['SEQ. ATUAL'] >= row['REC. SEQ. (V)'] and row['REC. SEQ. (V)'] >= 3:
                setor_estourado = row['SETOR']
                break
    
    modo_reversao = False
    setores_reais = df_stress[~df_stress['SETOR'].str.contains("VACA")]
    
    setores_ordenados = setores_reais.sort_values(by='% PRESENÇA', ascending=False)
    setor_forte = setores_ordenados.iloc[0]['SETOR']
    setor_fraco = setores_ordenados.iloc[-1]['SETOR']

    if setor_estourado:
        modo_reversao = True
        setor_fraco = setor_estourado 
        if setor_estourado == setor_forte:
             setor_forte = setores_ordenados.iloc[-1]['SETOR'] 

    lista_diamantes_segura = []
    if not df_diamante.empty and 'GRUPO' in df_diamante.columns:
        lista_diamantes_segura = df_diamante['GRUPO'].tolist()

    def calcular_score(grupo):
        score = 0
        if grupo == ultimo_bicho: score += 500
        if grupo in stats_ciclo['faltam']: score += 100
        if grupo in lista_diamantes_segura: score += 50
        if grupo in saturados: score -= 5000
        return score

    # ATAQUE (8 GRUPOS): 5 do Forte + 3 do Fraco
    grupos_ataque = []
    
    rank_forte = sorted(SETORES[setor_forte], key=lambda x: calcular_score(x), reverse=True)
    grupos_ataque.extend(rank_forte[:5]) 

    rank_fraco = sorted(SETORES[setor_fraco], key=lambda x: calcular_score(x), reverse=True)
    grupos_ataque.extend(rank_fraco[:3])

    # DEFESA (4 GRUPOS): 4 Melhores do Fraco que NÃO estão no ataque
    dezenas_proibidas = ['00', '11', '22', '33', '44', '55', '66', '77', '88', '99']
    
    grupos_defesa_candidatos = [g for g in rank_fraco if g not in grupos_ataque and g not in saturados]
    grupos_defesa_finais = grupos_defesa_candidatos[:4]

    dezenas_defesa = []
    for g in grupos_defesa_finais:
        dzs = GRUPOS_DEZENAS[g]
        pre_selecao = dzs[:3]
        filtradas = [d for d in pre_selecao if d not in dezenas_proibidas]
        dezenas_defesa.extend(filtradas)

    score_vaca = 0
    row_vaca = df_stress[df_stress['SETOR'].str.contains("VACA")].iloc[0]
    if row_vaca['ATRASO'] > 12: score_vaca += 80 
    if 25 == ultimo_bicho: score_vaca += 500
    if 25 in stats_ciclo['faltam']: score_vaca += 100
    if 25 in saturados: score_vaca -= 5000

    if score_vaca > 50:
        dezenas_defesa.append('97')
        dezenas_defesa.append('98')

    grupos_ataque = sorted(list(set(grupos_ataque)))
    if 25 in grupos_ataque: grupos_ataque.remove(25)
    dezenas_defesa = sorted(list(set(dezenas_defesa))) 
    
    sf_name = setor_forte.split(' ')[0]
    sw_name = setor_fraco.split(' ')[0]
    
    if modo_reversao:
        meta_info = f"🔄 REVERSÃO: Evitando {sw_name} (Estourado). Foco em {sf_name}."
    else:
        meta_info = f"TENDÊNCIA: {sf_name} Dominante (5G) + {sw_name} Apoio (3G)."
    
    return { "grupos_ataque": grupos_ataque, "dezenas_defesa": dezenas_defesa, "nota": 100, "meta_info": meta_info, "modo_reversao": modo_reversao, "is_record": False }

def executar_backtest_sniper(historico, indice_premio):
    resultados_backtest = []
    for i in range(1, 6):
        if len(historico) <= i + 20: break
        target_game = historico[-i]
        target_num = target_game['premios'][indice_premio]
        hist_treino = historico[:-i]
        
        df_s = calcular_stress_tabela(hist_treino, indice_premio)
        st_c = calcular_ciclo(hist_treino, indice_premio)
        df_d = calcular_tabela_diamante(hist_treino, indice_premio)
        u_b = hist_treino[-1]['premios'][indice_premio]
        sat = identificar_saturados(hist_treino, indice_premio)
        
        sniper_past = gerar_sniper_v39_final(df_s, st_c, df_d, u_b, sat)
        
        win_ataque = target_num in sniper_past['grupos_ataque']
        resultados_backtest.append({ "index": i, "numero_real": target_num, "vitoria": win_ataque })
    return resultados_backtest

def calcular_max_derrotas_50(historico, indice_premio):
    max_derrotas = 0; derrotas_consecutivas_temp = 0
    range_analise = min(50, len(historico) - 20)
    start_idx = len(historico) - range_analise
    for i in range(start_idx, len(historico)):
        target_game = historico[i]
        target_num = target_game['premios'][indice_premio]
        hist_treino = historico[:i]
        df_s = calcular_stress_tabela(hist_treino, indice_premio)
        st_c = calcular_ciclo(hist_treino, indice_premio)
        df_d = calcular_tabela_diamante(hist_treino, indice_premio)
        u_b = hist_treino[-1]['premios'][indice_premio]
        sat = identificar_saturados(hist_treino, indice_premio)
        sniper_past = gerar_sniper_v39_final(df_s, st_c, df_d, u_b, sat)
        
        win = target_num in sniper_past['grupos_ataque'] 
        
        if not win: derrotas_consecutivas_temp += 1
        else:
            if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
            derrotas_consecutivas_temp = 0
    if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
    return max_derrotas

def montar_url_correta(slug, data_alvo):
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    if delta == 0: return f"{base}/resultados-{slug}-de-hoje"
    elif delta == 1: return f"{base}/resultados-{slug}-de-ontem"
    else: return f"{base}/resultados-{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

def raspar_horario_especifico(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    url = montar_url_correta(config['slug'], data_alvo)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return None, "Erro Site"
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                cabecalho = tabela.find_previous(string=re.compile(r"Resultado do dia"))
                if cabecalho and "FEDERAL" in cabecalho.upper(): continue 
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        if ':' in raw: h_detect = raw
                        elif 'h' in raw: h_detect = raw.replace('h', '').strip().zfill(2) + ":00"
                        else: h_detect = raw.strip().zfill(2) + ":00"
                        if h_detect == horario_alvo:
                            bichos = []
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                cols = linha.find_all('td')
                                if len(cols) >= 3:
                                    grp = cols[2].get_text().strip()
                                    premio = cols[0].get_text().strip()
                                    if grp.isdigit():
                                        nums = re.findall(r'\d+', premio)
                                        if nums and 1 <= int(nums[0]) <= 5: bichos.append(int(grp))
                            if len(bichos) >= 5: return bichos[:5], "Sucesso"
                            else: return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. DASHBOARD GERAL ---
# =============================================================================
def tela_dashboard_global():
    st.title("🛡️ PENTÁGONO - COMMAND CENTER")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Bancas Monitoradas", "3", "Lotep, Caminho, Monte")
    
    with st.spinner("Varrendo Oportunidades em Tempo Real..."):
        alertas_globais = []
        
        for banca_key, config in CONFIG_BANCAS.items():
            historico = carregar_dados_top5(config['nome_aba'])
            if len(historico) > 0:
                for idx_pos in range(5):
                    # SNIPER V45
                    df_stress = calcular_stress_tabela(historico, idx_pos)
                    stats_ciclo = calcular_ciclo(historico, idx_pos)
                    df_diamante = calcular_tabela_diamante(historico, idx_pos)
                    ultimo_bicho = historico[-1]['premios'][idx_pos]
                    saturados_list = identificar_saturados(historico, idx_pos)
                    
                    sniper = gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados_list)
                    
                    # 1. IA HIGH CONFIDENCE
                    if HAS_AI:
                        _, conf_ia_global = treinar_oraculo_pentagono(historico, idx_pos)
                        if conf_ia_global >= 60.0:
                            prox_hora = obter_proxima_batalha(banca_key, historico[-1]['horario'])
                            alertas_globais.append({
                                "tipo": "IA",
                                "banca": config['display_name'].split("(")[0].strip(),
                                "premio": f"{idx_pos+1}º Prêmio",
                                "msg": f"🤖 IA CONFIANTE ({conf_ia_global:.1f}%) | {prox_hora}"
                            })

                    # 2. FALHAS SNIPER
                    bt_results = executar_backtest_sniper(historico, idx_pos)
                    if len(bt_results) >= 2:
                        if not bt_results[0]['vitoria'] and not bt_results[1]['vitoria']:
                            prox_hora = obter_proxima_batalha(banca_key, historico[-1]['horario'])
                            alertas_globais.append({
                                "tipo": "SNIPER",
                                "banca": config['display_name'].split("(")[0].strip(),
                                "premio": f"{idx_pos+1}º Prêmio",
                                "msg": f"🎯 OPORTUNIDADE SNIPER (2 Loss) | {prox_hora}"
                            })

        col2.metric("Oportunidades", f"{len(alertas_globais)}", "Ativas")
        col3.metric("Status", "Online", "Sem Cache")
        st.markdown("---")
        
        if alertas_globais:
            st.subheader("🚨 Radar de Oportunidades")
            for alerta in alertas_globais:
                if alerta['tipo'] == "SNIPER":
                    st.warning(f"**{alerta['banca']} - {alerta['premio']}** | {alerta['msg']}")
                else:
                    st.info(f"**{alerta['banca']} - {alerta['premio']}** | {alerta['msg']}")
        else: st.success("✅ Tudo calmo no Radar Global.")

# =============================================================================
# --- 4. FLUXO PRINCIPAL DO APP ---
# =============================================================================

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

st.sidebar.markdown("---")
st.sidebar.link_button("🛡️ Ir para App CENTURION", "https://seu-app-centurion.streamlit.app") 
st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    tela_dashboard_global()

else:
    banca_selecionada = escolha_menu
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    st.sidebar.markdown("---")
    url_site = f"https://www.resultadofacil.com.br/resultados-{config_banca['slug']}-de-hoje"
    st.sidebar.link_button("🔗 Ver Site Oficial", url_site)
    st.sidebar.markdown("---")
    
    # --- MODO EXTRAÇÃO ---
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)"])
    
    if modo_extracao == "🎯 Unitária":
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.sidebar.date_input("Escolha:", date.today())
            
            horario_busca = st.selectbox("Horário:", config_banca['horarios'])
            
            if st.button("🚀 Baixar & Salvar"):
                ws = conectar_planilha(config_banca['nome_aba'])
                if ws:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try:
                            # Verificação limpa sem cache
                            existentes = ws.get_all_values()
                            chaves = [f"{str(row[0]).strip()}|{str(row[1]).strip()}" for row in existentes if len(row)>1]
                        except: chaves = []
                        
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{horario_busca}"
                        
                        if chave_atual in chaves:
                            st.warning("Resultado já existe!")
                        else:
                            top5, msg = raspar_horario_especifico(banca_selecionada, data_busca, horario_busca)
                            if top5:
                                row = [data_busca.strftime('%Y-%m-%d'), horario_busca] + top5
                                ws.append_row(row)
                                st.toast(f"Sucesso! {top5}", icon="✅")
                                time.sleep(1)
                                st.rerun()
                            else: st.error(msg)
                else: st.error("Erro Planilha")
                
    else: # MODO TURBO
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        
        if st.sidebar.button("🚀 INICIAR TURBO"):
            ws = conectar_planilha(config_banca['nome_aba'])
            if ws:
                status = st.sidebar.empty()
                bar = st.sidebar.progress(0)
                try:
                    existentes = ws.get_all_values()
                    chaves = [f"{str(row[0]).strip()}|{str(row[1]).strip()}" for row in existentes if len(row)>1]
                except: chaves = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config_banca['horarios'])
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    for hora in config_banca['horarios']:
                        op_atual += 1
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                        
                        if chave_atual in chaves: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue

                        top5, msg = raspar_horario_especifico(banca_selecionada, dia, hora)
                        if top5:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + top5)
                            sucessos += 1
                            chaves.append(chave_atual)
                        time.sleep(1.0)
                
                bar.progress(100)
                status.success(f"🏁 Concluído! {sucessos} novos sorteios.")
                time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão")

    # --- PÁGINA DA BANCA ---
    st.header(f"🔭 {config_banca['display_name']}")
    
    with st.spinner("Carregando dados..."):
        historico = carregar_dados_top5(config_banca['nome_aba'])

    if len(historico) > 0:
        ult = historico[-1]
        st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **1º:** G{ult['premios'][0]} | **2º:** G{ult['premios'][1]}...")
        
        prox_tiro_local = obter_proxima_batalha(banca_selecionada, ult['horario'])
        nomes_posicoes = ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]
        
        abas = st.tabs(nomes_posicoes)
        
        for idx_aba, aba in enumerate(abas):
            with aba:
                # CÁLCULOS
                df_stress = calcular_stress_tabela(historico, idx_aba)
                stats_ciclo = calcular_ciclo(historico, idx_aba)
                df_diamante = calcular_tabela_diamante(historico, idx_aba)
                ultimo_bicho = historico[-1]['premios'][idx_aba]
                saturados = identificar_saturados(historico, idx_aba)
                
                sniper_local = gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados)
                
                if HAS_AI:
                    top_8_ia, confianca_ia = treinar_oraculo_pentagono(historico, idx_aba)
                    bt_ia = executar_backtest_ia(historico, idx_aba)
                    max_loss_ia = calcular_max_derrotas_ia_50(historico, idx_aba)
                
                bt_results = executar_backtest_sniper(historico, idx_aba)
                max_loss_record = calcular_max_derrotas_50(historico, idx_aba)
                
                # --- VISUAL NATIVO (ZERO HTML ERROS) ---
                
                if HAS_AI:
                    with st.container(border=True):
                        st.markdown("### 🧠 Oráculo IA (Top 8)")
                        st.info(f"Confiança: {confianca_ia:.1f}%")
                        st.markdown(f"**Previsão:** {', '.join(map(str, top_8_ia))}")
                        
                        # Super Grupos (Interseção)
                        super_g = list(set(sniper_local['grupos_ataque']) & set(top_8_ia))
                        if super_g:
                            st.success(f"🌟 **SUPER GRUPOS (Sniper + IA):** {', '.join(map(str, super_g))}")
                        
                        st.markdown(f"**Histórico IA (50 Jogos):** Pior Sequência: {max_loss_ia} Derrotas")
                        # Mini backtest visual IA
                        cols_ia = st.columns(len(bt_ia))
                        for i, res in enumerate(reversed(bt_ia)):
                            with cols_ia[i]:
                                if res['vitoria']: st.success(f"G{res['numero_real']}")
                                else: st.error(f"G{res['numero_real']}")

                # SNIPER CARD
                with st.container(border=True):
                    st.markdown(f"## 🎯 SNIPER: {nomes_posicoes[idx_aba]}")
                    st.caption(f"Próximo: {prox_tiro_local}")
                    
                    if sniper_local['modo_reversao']:
                        st.error(f"🔄 MODO REVERSÃO ATIVADO: {sniper_local['meta_info']}")
                    else:
                        st.info(sniper_local['meta_info'])
                    
                    c1, c2 = st.columns(2)
                    c1.metric("🟢 ATAQUE (8 Grupos)", ", ".join(map(str, sniper_local['grupos_ataque'])))
                    c2.metric("🛡️ DEFESA (Dezenas)", ", ".join(map(str, sniper_local['dezenas_defesa'])))
                    
                    if saturados: st.warning(f"Saturados: {saturados}")

                st.error(f"📉 Pior Sequência Sniper (50 Jogos): {max_loss_record} Derrotas")
                
                # BACKTEST SNIPER
                if bt_results:
                    st.markdown("### ⏪ Performance Recente (Sniper)")
                    cols_sn = st.columns(len(bt_results))
                    for i, res in enumerate(reversed(bt_results)):
                        with cols_sn[i]:
                            val = f"G{res['numero_real']}"
                            if res['vitoria']: st.success(f"{val} (WIN)")
                            else: st.error(f"{val} (LOSS)")

                st.markdown("---")
                
                # GRÁFICO E TABELAS
                st.markdown("### 📊 Raio-X Estatístico")
                
                # Gráfico
                df_chart = df_stress.copy()
                base = alt.Chart(df_chart).encode(theta=alt.Theta("% PRESENÇA", stack=True))
                pie = base.mark_arc(outerRadius=80).encode(
                    color=alt.Color("SETOR"),
                    order=alt.Order("% PRESENÇA", sort="descending"),
                    tooltip=["SETOR", "% PRESENÇA"]
                )
                st.altair_chart(pie, use_container_width=True)
                
                st.markdown("**Tabela de Stress:**")
                st.dataframe(df_stress.drop(columns=['SEQ. ATUAL']), use_container_width=True)
                
                st.markdown("---")
                st.markdown(f"**Ciclo (Vistos: {stats_ciclo['vistos']}/25):**")
                st.progress(stats_ciclo['vistos'] / 25.0)
                if stats_ciclo['faltam']:
                    st.markdown(f"**Faltam Sair:** {', '.join(map(str, stats_ciclo['faltam']))}")
                else: st.success("Ciclo Fechado!")
                
                st.markdown("---")
                st.markdown("**💎 Diamantes (Frequência Alta):**")
                if not df_diamante.empty:
                    st.dataframe(df_diamante, use_container_width=True)
                else: st.info("Sem destaques no momento.")

    else:
        st.warning("⚠️ Base vazia.")
