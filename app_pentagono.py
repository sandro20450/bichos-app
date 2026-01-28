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
st.set_page_config(page_title="PENTÁGONO V10 - Fix Caminho", page_icon="🛡️", layout="wide")

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

def calcular_stress_tabela(historico, indice_premio):
    stats = []
    for nome_setor, lista_bichos in SETORES.items():
        max_atraso = 0; curr_atraso = 0; max_seq_v = 0; curr_seq_v = 0
        for jogo in historico:
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos:
                curr_seq_v += 1
                if curr_atraso > max_atraso: max_atraso = curr_atraso
                curr_atraso = 0
            else:
                curr_atraso += 1
                if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
                curr_seq_v = 0
        
        if curr_atraso > max_atraso: max_atraso = curr_atraso
        if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
        
        atraso_real = 0
        for jogo in reversed(historico):
            bicho = jogo['premios'][indice_premio]
            if bicho in lista_bichos: break
            atraso_real += 1
            
        stats.append({
            "SETOR": nome_setor,
            "ATRASO": atraso_real,
            "REC. ATRASO": max_atraso,
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

# ROBÔ COM CORREÇÃO PARA "17" (SEM H E SEM :)
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
        
        # --- CORREÇÃO DO REGEX ---
        # Aceita: 12:45 | 18h | 17 (apenas número solto)
        padrao_hora = re.compile(r'(\d{1,2}:\d{2}|\d{1,2}h|\b\d{1,2}\b)')
        
        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                prev = tabela.find_previous(string=padrao_hora)
                if prev:
                    m = re.search(padrao_hora, prev)
                    if m:
                        raw = m.group(1).strip()
                        
                        # Normalização Inteligente
                        if ':' in raw:
                            h_detect = raw
                        elif 'h' in raw:
                            h_detect = raw.replace('h', '').strip().zfill(2) + ":00"
                        else:
                            # Caso onde acha só "17" -> Converte para "17:00"
                            h_detect = raw.zfill(2) + ":00"
                        
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
    
    with st.spinner("Escaneando todas as bancas e prêmios..."):
        alertas_globais = []
        for banca_key, config in CONFIG_BANCAS.items():
            historico = carregar_dados_top5(config['nome_aba'])
            if len(historico) > 0:
                for idx_pos in range(5):
                    df = calcular_stress_tabela(historico, idx_pos)
                    for _, row in df.iterrows():
                        atraso = row['ATRASO']; recorde = row['REC. ATRASO']; setor = row['SETOR']
                        if "VACA" in setor: continue
                        if (recorde - atraso) <= 1 and recorde >= 5:
                            alertas_globais.append({
                                "banca": config['display_name'].split("(")[0].strip(),
                                "premio": f"{idx_pos+1}º Prêmio",
                                "setor": setor,
                                "atraso": atraso,
                                "recorde": recorde
                            })
        
        col2.metric("Base de Dados", "Conectada", "Google Sheets")
        col3.metric("Oportunidades Críticas", f"{len(alertas_globais)}", "Zonas de Tiro")
        
        st.markdown("---")
        
        if alertas_globais:
            st.warning("🚨 Oportunidades Encontradas")
            cols = st.columns(2)
            for i, alerta in enumerate(alertas_globais):
                classe = "box-alerta" if alerta['atraso'] >= alerta['recorde'] else "box-aviso"
                status = "ESTOURADO!" if alerta['atraso'] >= alerta['recorde'] else "Zona de Tiro"
                with cols[i % 2]:
                    st.markdown(f"""
                    <div class="{classe}">
                        <h3>{alerta['banca']}</h3>
                        <p>📍 <b>{alerta['premio']}</b> | {alerta['setor']}</p>
                        <p>Atraso: {alerta['atraso']} (Recorde: {alerta['recorde']})</p>
                        <p><b>STATUS: {status}</b></p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("✅ Tudo calmo nas 3 bancas.")

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
                if "VACA" in setor: continue 
                if (recorde - atraso) <= 1 and recorde >= 5:
                    alertas_locais += 1
                    classe = "box-alerta" if atraso >= recorde else "box-aviso"
                    msg_extra = "**ESTOURADO!**" if atraso >= recorde else "Zona de Tiro"
                    with col_alerts:
                        st.markdown(f"<div class='{classe}'><b>{nome_pos} | {setor}</b><br>Atraso: {atraso} (Recorde: {recorde}) - {msg_extra}</div>", unsafe_allow_html=True)
        
        if alertas_locais == 0: st.success("Sem alertas críticos nesta banca.")
        st.markdown("---")

        abas = st.tabs(nomes_posicoes)
        for idx_aba, aba in enumerate(abas):
            with aba:
                st.markdown(f"### 📊 Raio-X: {nomes_posicoes[idx_aba]}")
                st.markdown("**Visual Recente (⬅️ Mais Novo):**")
                st.markdown(gerar_bolinhas_recentes(historico, idx_aba), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                st.markdown("**📉 Tabela de Stress:**")
                df_stats = calcular_stress_tabela(historico, idx_aba)
                st.table(df_stats)
                
                st.markdown("---")
                st.subheader("🔄 Monitor de Ciclos")
                stats_ciclo = calcular_ciclo(historico, idx_aba)
                prog_val = stats_ciclo['vistos'] / 25.0
                st.progress(prog_val)
                st.caption(f"Status: {stats_ciclo['vistos']}/25 bichos já saíram.")
                c1, c2 = st.columns(2)
                with c1: st.metric("Jogos no Ciclo Atual", f"{stats_ciclo['jogos_atual']}")
                with c2: st.metric("Média para Fechar", f"{stats_ciclo['media_historica']:.1f}")
                if stats_ciclo['faltam']:
                    st.markdown("**Faltam Sair (Sugestão):**")
                    st.code(", ".join(map(str, stats_ciclo['faltam'])), language="text")
                else: st.success("Ciclo Fechado! Próximo sorteio abre novo ciclo.")

                st.markdown("---")
                st.subheader("💎 DIAMANTES (Elite 3x - Últimos 30 Jogos)")
                df_diamante = calcular_tabela_diamante(historico, idx_aba)
                if not df_diamante.empty:
                    st.table(df_diamante)
                else:
                    st.info("Nenhum grupo de Alta Frequência (3x ou mais) encontrado recentemente.")

                st.markdown("<br>", unsafe_allow_html=True)
                if "VACA (25)" in df_stats['SETOR'].values:
                    row_vaca = df_stats[df_stats['SETOR'] == "VACA (25)"].iloc[0]
                    if row_vaca['ATRASO'] > 15:
                        st.info(f"ℹ️ **Vaca (25):** Atraso Atual: {row_vaca['ATRASO']} | Recorde: {row_vaca['REC. ATRASO']}")
    else:
        st.warning("⚠️ Base vazia.")
