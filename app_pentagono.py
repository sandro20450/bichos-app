import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V16 - Law of Large Numbers", page_icon="⚖️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": {
        "display_name": "LOTEP (1º ao 5º)",
        "nome_aba": "LOTEP_TOP5",
        "slug": "lotep",
        "horarios": ["10:45", "12:45", "15:45", "18:00"]
    },
    "CAMINHODASORTE": {
        "display_name": "CAMINHO (1º ao 5º)",
        "nome_aba": "CAMINHO_TOP5",
        "slug": "caminho-da-sorte",
        "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"]
    },
    "MONTECAI": {
        "display_name": "MONTE CARLOS (1º ao 5º)",
        "nome_aba": "MONTE_TOP5",
        "slug": "nordeste-monte-carlos",
        "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"]
    }
}

SETORES = {
    "BAIXO (01-08)": list(range(1, 9)),
    "MÉDIO (09-16)": list(range(9, 17)),
    "ALTO (17-24)": list(range(17, 25)),
    "VACA (25)": [25]
}

if 'tocar_som' not in st.session_state: st.session_state['tocar_som'] = False

def reproduzir_som():
    sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def aplicar_estilo():
    st.markdown("""
    <style>
        .stMetric { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }
        .box-alerta { background-color: #580000; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; color: #ffcccc; }
        .box-aviso { background-color: #584e00; padding: 15px; border-radius: 8px; border-left: 5px solid #ffd700; margin-bottom: 15px; color: #fffacd; }
        .box-inverso-critico { background-color: #2e004f; padding: 15px; border-radius: 8px; border-left: 5px solid #d000ff; margin-bottom: 15px; color: #e0b0ff; font-weight: bold; }
        .box-inverso-atencao { background-color: #1a002e; padding: 15px; border-radius: 8px; border-left: 5px solid #9932cc; margin-bottom: 15px; color: #dda0dd; }
        
        /* Palpite Inteligente */
        .palpite-box { background: linear-gradient(90deg, #004d00 0%, #002b00 100%); border: 1px solid #00ff00; padding: 15px; border-radius: 10px; margin-bottom: 20px; color: #ccffcc; }
        .palpite-nums { font-size: 24px; font-weight: bold; color: #fff; letter-spacing: 2px; }
        
        .bola-b { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-m { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-a { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-v { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #6f42c1; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        
        div[data-testid="stTable"] table { color: white; }
        thead tr th:first-child {display:none}
        tbody th {display:none}
        
        .diamante-box { border: 1px solid #00d2ff; background-color: rgba(0, 210, 255, 0.1); padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

if st.session_state['tocar_som']:
    reproduzir_som()
    st.session_state['tocar_som'] = False

# =============================================================================
# --- 2. CONEXÃO E LÓGICA ---
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
                        dados_processados.append({
                            "data": row[0],
                            "horario": row[1],
                            "premios": premios 
                        })
                except: pass
        return dados_processados
    return []

# --- CÁLCULO DE STRESS + PORCENTAGEM (V16) ---
def calcular_stress_tabela(historico, indice_premio):
    stats = []
    total_jogos = len(historico)
    
    for nome_setor, lista_bichos in SETORES.items():
        max_atraso = 0; curr_atraso = 0; max_seq_v = 0; curr_seq_v = 0
        total_vitorias = 0 # Contador para porcentagem
        
        # 1. Varredura Histórica
        for jogo in historico:
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos:
                total_vitorias += 1 # Contabiliza vitória
                curr_seq_v += 1
                if curr_atraso > max_atraso: max_atraso = curr_atraso
                curr_atraso = 0
            else:
                if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
                curr_seq_v = 0
                curr_atraso += 1
        
        if curr_atraso > max_atraso: max_atraso = curr_atraso
        if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
        
        # 2. Atraso Real
        atraso_real = 0
        for jogo in reversed(historico):
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos: break
            atraso_real += 1
            
        # 3. Sequência Atual
        seq_atual = 0
        for jogo in reversed(historico):
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos: seq_atual += 1
            else: break
            
        # 4. Cálculo da Porcentagem
        porcentagem = (total_vitorias / total_jogos * 100) if total_jogos > 0 else 0

        stats.append({
            "SETOR": nome_setor,
            "% PRESENÇA": f"{porcentagem:.1f}%", # Nova Coluna
            "ATRASO": atraso_real,
            "REC. ATRASO": max_atraso,
            "SEQ. ATUAL": seq_atual,
            "REC. SEQ. (V)": max_seq_v
        })
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
            if atraso_atual <= 2: status = "❄️ Saiu Agora (Aguarde)"
            elif atraso_atual >= media: status = "🔥 PONTO DE ENTRADA"
            elif atraso_atual >= (media * 0.6): status = "⏳ Aquece (Quase lá)"
            else: status = "💤 Neutro"
            tabela_dados.append({
                "GRUPO": bicho,
                "SAÍDAS (30 Jogos)": qtd,
                "MÉDIA": f"1 a cada {media:.1f}",
                "ÚLTIMA VEZ": f"Há {atraso_atual} jogos",
                "STATUS / DICA": status
            })
    def sort_key(x):
        s = x['STATUS / DICA']
        if "🔥" in s: return 0
        if "⏳" in s: return 1
        if "❄️" in s: return 3
        return 2
    tabela_dados.sort(key=sort_key)
    return pd.DataFrame(tabela_dados)

# --- GERADOR DE PALPITE 8 GRUPOS (SMART MIX) ---
def gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante):
    candidatos = [] 
    
    # 1. IDENTIFICAR SETOR CRÍTICO
    setor_critico = None
    for index, row in df_stress.iterrows():
        setor = row['SETOR']
        if "VACA" not in setor and (row['REC. ATRASO'] - row['ATRASO']) <= 1 and row['REC. ATRASO'] >= 5:
            setor_critico = setor
            break
            
    motivo = "Mix Equilibrado: Ciclos + Tendência."
    
    if setor_critico:
        motivo = f"Foco no {setor_critico} (Crítico) misturado com Diamantes para proteção."
        grupos_setor = SETORES[setor_critico]
        for g in grupos_setor:
            if g in stats_ciclo['faltam']: candidatos.append(g)
                
    if not df_diamante.empty:
        for index, row in df_diamante.iterrows():
            if "🔥" in row['STATUS / DICA'] or "⏳" in row['STATUS / DICA']: candidatos.append(row['GRUPO'])
                
    if setor_critico:
        grupos_setor = SETORES[setor_critico]
        for g in grupos_setor: candidatos.append(g)
            
    for g in stats_ciclo['faltam']: candidatos.append(g)
        
    maior_atraso = df_stress.loc[~df_stress['SETOR'].str.contains("VACA")].sort_values(by='ATRASO', ascending=False).iloc[0]
    setor_bkp = maior_atraso['SETOR']
    for g in SETORES[setor_bkp]: candidatos.append(g)

    palpite_final = []
    seen = set()
    for item in candidatos:
        if item not in seen:
            palpite_final.append(item)
            seen.add(item)
        if len(palpite_final) == 8: break
        
    palpite_final.sort()
    destaque = [g for g in palpite_final if g in stats_ciclo['faltam']]
    
    return { "tipo": "SMART MIX (Híbrido)", "grupos": palpite_final, "destaque": destaque, "motivo": motivo }

# ROBÔ
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

def gerar_bolinhas_recentes(historico, indice_premio):
    html = "<div>"
    for jogo in reversed(historico[-12:]):
        bicho = jogo['premios'][indice_premio]
        classe = ""
        letra = ""
        if bicho in SETORES["BAIXO (01-08)"]: classe = "bola-b"; letra = "B"
        elif bicho in SETORES["MÉDIO (09-16)"]: classe = "bola-m"; letra = "M"
        elif bicho in SETORES["ALTO (17-24)"]: classe = "bola-a"; letra = "A"
        elif bicho == 25: classe = "bola-v"; letra = "V"
        html += f"<div class='{classe}'>{letra}</div>"
    html += "</div>"
    return html

# =============================================================================
# --- 3. DASHBOARD GERAL ---
# =============================================================================
def tela_dashboard_global():
    st.title("🛡️ CENTRO DE COMANDO (Pentágono)")
    st.markdown("### 📡 Varredura de Oportunidades em Tempo Real")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Bancas Monitoradas", "3", "LOTEP, CAMINHO, MONTE")
    
    with st.spinner("Escaneando e gerando palpites..."):
        alertas_globais = []
        palpites_gerados = []
        
        for banca_key, config in CONFIG_BANCAS.items():
            historico = carregar_dados_top5(config['nome_aba'])
            if len(historico) > 0:
                for idx_pos in range(5):
                    # CALCULA TUDO PARA O PALPITE
                    df_stress = calcular_stress_tabela(historico, idx_pos)
                    stats_ciclo = calcular_ciclo(historico, idx_pos)
                    df_diamante = calcular_tabela_diamante(historico, idx_pos)
                    
                    # CHECAGEM DE ALERTAS
                    tem_alerta_critico = False
                    for _, row in df_stress.iterrows():
                        atraso = row['ATRASO']; recorde = row['REC. ATRASO']; setor = row['SETOR']
                        seq_atual = row['SEQ. ATUAL']; recorde_seq = row['REC. SEQ. (V)']
                        if "VACA" in setor: continue
                        
                        # Alerta Atraso
                        if (recorde - atraso) <= 1 and recorde >= 5:
                            alertas_globais.append({"tipo": "ATRASO", "banca": config['display_name'].split("(")[0].strip(), "premio": f"{idx_pos+1}º Prêmio", "setor": setor, "val_atual": atraso, "val_rec": recorde})
                            tem_alerta_critico = True
                            
                        # Alerta Repetição
                        margem_seq = recorde_seq - seq_atual
                        if margem_seq <= 1 and recorde_seq >= 3:
                            alertas_globais.append({"tipo": "REPETICAO", "banca": config['display_name'].split("(")[0].strip(), "premio": f"{idx_pos+1}º Prêmio", "setor": setor, "val_atual": seq_atual, "val_rec": recorde_seq, "margem": margem_seq})
                            tem_alerta_critico = True
                    
                    # SE TEM ALERTA CRITICO, GERA O PALPITE NA HOME
                    if tem_alerta_critico:
                        palpite = gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante)
                        palpites_gerados.append({
                            "banca": config['display_name'].split("(")[0].strip(),
                            "premio": f"{idx_pos+1}º Prêmio",
                            "grupos": palpite['grupos'],
                            "motivo": palpite['motivo'],
                            "destaque": palpite['destaque']
                        })

        col2.metric("Base de Dados", "Conectada", "Google Sheets")
        col3.metric("Oportunidades Críticas", f"{len(alertas_globais)}", "Zonas de Tiro")
        st.markdown("---")
        
        # EXIBE ALERTAS
        if alertas_globais:
            st.warning("🚨 Oportunidades Encontradas")
            cols = st.columns(2)
            for i, alerta in enumerate(alertas_globais):
                if alerta['tipo'] == "ATRASO":
                    classe = "box-alerta" if alerta['val_atual'] >= alerta['val_rec'] else "box-aviso"
                    titulo_val, msg = "Atraso", "ZONA DE TIRO (Atraso)"
                else: 
                    if alerta['margem'] <= 0: classe, msg = "box-inverso-critico", "ESTOURADO! (Bateu Recorde)"
                    else: classe, msg = "box-inverso-atencao", "Atenção (Próximo do Recorde)"
                    titulo_val = "Sequência"
                with cols[i % 2]:
                    st.markdown(f"<div class='{classe}'><h3>{alerta['banca']}</h3><p>📍 <b>{alerta['premio']}</b> | {alerta['setor']}</p><p>{titulo_val}: {alerta['val_atual']} (Recorde: {alerta['val_rec']})</p><p><b>{msg}</b></p></div>", unsafe_allow_html=True)
        else: st.success("✅ Tudo calmo nas 3 bancas.")

        # EXIBE PALPITES AUTOMÁTICOS
        if palpites_gerados:
            st.markdown("### 🎯 PREVISÕES DE ELITE (Smart Mix)")
            st.info("O Robô gerou estas combinações de 8 Grupos baseadas nos alertas acima.")
            for p in palpites_gerados:
                st.markdown(f"""
                <div class="palpite-box">
                    <h4>{p['banca']} - {p['premio']}</h4>
                    <p class="palpite-nums">{', '.join(map(str, p['grupos']))}</p>
                    <small><b>Motivo:</b> {p['motivo']}</small>
                </div>
                """, unsafe_allow_html=True)
                if p['destaque']: st.write(f"⭐ **Destaque:** {', '.join(map(str, p['destaque']))}")

# =============================================================================
# --- 4. FLUXO PRINCIPAL DO APP ---
# =============================================================================
aplicar_estilo()

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes)

if escolha_menu == "🏠 RADAR GERAL (Home)":
    tela_dashboard_global()

else:
    banca_selecionada = escolha_menu
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    st.sidebar.markdown("---")
    url_site = f"https://www.resultadofacil.com.br/resultados-{config_banca['slug']}-de-hoje"
    st.sidebar.link_button("🔗 Ver Site Oficial", url_site)
    st.sidebar.markdown("---")
    
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
                        existentes = ws.get_all_values()
                        chaves = [f"{row[0]}|{row[1]}" for row in existentes if len(row)>1]
                    except: chaves = []
                    chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{horario_busca}"
                    if chave_atual in chaves: st.warning("Resultado já existe!")
                    else:
                        top5, msg = raspar_horario_especifico(banca_selecionada, data_busca, horario_busca)
                        if top5:
                            row = [data_busca.strftime('%Y-%m-%d'), horario_busca] + top5
                            ws.append_row(row)
                            st.session_state['tocar_som'] = True
                            st.toast(f"Sucesso! {top5}", icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else: st.error(msg)
            else: st.error("Erro Planilha")

    st.header(f"🔭 {config_banca['display_name']}")
    with st.spinner("Carregando dados..."):
        historico = carregar_dados_top5(config_banca['nome_aba'])

    if len(historico) > 0:
        ult = historico[-1]
        st.caption(f"📅 Último: {ult['data']} às {ult['horario']}")
        
        st.subheader(f"🚨 Radar Local: {config_banca['display_name'].split('(')[0]}")
        nomes_posicoes = ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]
        col_alerts = st.container()
        alertas_locais = 0
        for idx_pos, nome_pos in enumerate(nomes_posicoes):
            df = calcular_stress_tabela(historico, idx_pos)
            for index, row in df.iterrows():
                atraso = row['ATRASO']; recorde = row['REC. ATRASO']; setor = row['SETOR']
                seq_atual = row['SEQ. ATUAL']; recorde_seq = row['REC. SEQ. (V)']
                if "VACA" in setor: continue 
                if (recorde - atraso) <= 1 and recorde >= 5:
                    alertas_locais += 1
                    classe = "box-alerta" if atraso >= recorde else "box-aviso"
                    msg_extra = "**ESTOURADO!**" if atraso >= recorde else "Zona de Tiro"
                    with col_alerts: st.markdown(f"<div class='{classe}'><b>{nome_pos} | {setor}</b><br>Atraso: {atraso} (Recorde: {recorde}) - {msg_extra}</div>", unsafe_allow_html=True)
                margem_seq = recorde_seq - seq_atual
                if margem_seq <= 1 and recorde_seq >= 3:
                    alertas_locais += 1
                    if margem_seq <= 0: classe, msg_extra = "box-inverso-critico", "🔁 REPETIÇÃO MÁXIMA (Inverso Recomendado)"
                    else: classe, msg_extra = "box-inverso-atencao", "⚠️ Atenção: Sequência Alta (Quase no Recorde)"
                    with col_alerts: st.markdown(f"<div class='{classe}'><b>{nome_pos} | {setor}</b><br>Sequência Atual: {seq_atual}x (Recorde: {recorde_seq})<br>{msg_extra}</div>", unsafe_allow_html=True)
        if alertas_locais == 0: st.success("Sem alertas críticos nesta banca.")
        st.markdown("---")

        abas = st.tabs(nomes_posicoes)
        for idx_aba, aba in enumerate(abas):
            with aba:
                df_stress = calcular_stress_tabela(historico, idx_aba)
                stats_ciclo = calcular_ciclo(historico, idx_aba)
                df_diamante = calcular_tabela_diamante(historico, idx_aba)
                palpite = gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante)
                
                st.markdown(f"""
                <div class="palpite-box">
                    <h4>🎯 PALPITE INTELIGENTE (8 GRUPOS) - {nomes_posicoes[idx_aba]}</h4>
                    <p class="palpite-nums">{', '.join(map(str, palpite['grupos']))}</p>
                    <small><b>Estratégia:</b> {palpite['tipo']} | <b>Motivo:</b> {palpite['motivo']}</small>
                </div>
                """, unsafe_allow_html=True)
                if palpite['destaque']: st.info(f"⭐ Destaque (Falta no Ciclo): **{', '.join(map(str, palpite['destaque']))}**")
                
                st.markdown(f"### 📊 Raio-X: {nomes_posicoes[idx_aba]}")
                st.markdown("**Visual Recente (⬅️ Mais Novo):**")
                st.markdown(gerar_bolinhas_recentes(historico, idx_aba), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**📉 Tabela de Stress:**")
                df_visual = df_stress.drop(columns=['SEQ. ATUAL'])
                st.table(df_visual)
                st.markdown("---")
                st.subheader("🔄 Monitor de Ciclos")
                prog_val = stats_ciclo['vistos'] / 25.0
                st.progress(prog_val)
                st.caption(f"Status: {stats_ciclo['vistos']}/25 bichos já saíram.")
                c1, c2 = st.columns(2)
                with c1: st.metric("Jogos no Ciclo Atual", f"{stats_ciclo['jogos_atual']}")
                with c2: st.metric("Média para Fechar", f"{stats_ciclo['media_historica']:.1f}")
                if stats_ciclo['faltam']: st.markdown("**Faltam Sair (Sugestão):**"); st.code(", ".join(map(str, stats_ciclo['faltam'])), language="text")
                else: st.success("Ciclo Fechado! Próximo sorteio abre novo ciclo.")
                st.markdown("---")
                st.subheader("💎 DIAMANTES (Elite 3x - Últimos 30 Jogos)")
                if not df_diamante.empty: st.table(df_diamante)
                else: st.info("Nenhum grupo de Alta Frequência (3x ou mais) encontrado recentemente.")
                st.markdown("<br>", unsafe_allow_html=True)
                if "VACA (25)" in df_stress['SETOR'].values:
                    row_vaca = df_stress[df_stress['SETOR'] == "VACA (25)"].iloc[0]
                    if row_vaca['ATRASO'] > 15: st.info(f"ℹ️ **Vaca (25):** Atraso Atual: {row_vaca['ATRASO']} | Recorde: {row_vaca['REC. ATRASO']}")
    else:
        st.warning("⚠️ Base vazia.")
