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
# --- 1. CONFIGURAÇÕES GERAIS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V143.0 - Livro dos Recordes", page_icon="🎯", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "🎯 TRADICIONAL", "nome_aba": "TRADICIONAL_MILHAR", "slug": "tradicional", "tipo_extracao": "DUAL_PENTA", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "radar_ativo": True },
    "LOTEP": { "display_name": "🎯 LOTEP", "nome_aba": "LOTEP_MILHAR", "slug": "lotep", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"], "radar_ativo": True },
    "CAMINHO": { "display_name": "🎯 CAMINHO DA SORTE", "nome_aba": "CAMINHO_MILHAR", "slug": "caminho-da-sorte", "tipo_extracao": "DUAL_PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"], "radar_ativo": True },
    "MONTE": { "display_name": "🎯 MONTE CARLOS", "nome_aba": "MONTE_MILHAR", "slug": "nordeste-monte-carlos", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"], "radar_ativo": True }
}

NOME_GRUPOS = [
    "0-Erro", "1-Avestruz", "2-Águia", "3-Burro", "4-Borboleta", "5-Cachorro",
    "6-Cabra", "7-Carneiro", "8-Camelo", "9-Cobra", "10-Coelho",
    "11-Cavalo", "12-Elefante", "13-Galo", "14-Gato", "15-Jacaré",
    "16-Leão", "17-Macaco", "18-Porco", "19-Pavão", "20-Peru",
    "21-Touro", "22-Tigre", "23-Urso", "24-Veado", "25-Vaca"
]

def get_dezenas_grupo(grupo):
    if grupo == 25: return "97, 98, 99, 00"
    if 1 <= grupo <= 24:
        return f"{(grupo*4)-3:02d}, {(grupo*4)-2:02d}, {(grupo*4)-1:02d}, {grupo*4:02d}"
    return ""

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #ffd700 !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .card-ranking { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #ff4b4b; }
    .card-alvo { background-color: #1a0000; border: 2px solid #ff0000; border-radius: 8px; padding: 20px; text-align: center; }
    .card-recorde { background-color: #1a1a00; border: 1px solid #cca300; border-radius: 8px; padding: 10px; margin-bottom: 10px; border-left: 5px solid #ffcc00; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO SEGURA COM GOOGLE SHEETS ---
# =============================================================================

@st.cache_resource(ttl=3600, show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    return None

def conectar_planilha(nome_aba):
    gc = get_gspread_client()
    if gc:
        try: return gc.open("CentralBichos").worksheet(nome_aba)
        except: return None
    return None

@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados_hibridos(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 3:
                    data_str = str(row[0]).strip()
                    hr_str = str(row[1]).strip()
                    h_clean = re.sub(r'[a-zA-Z]', '', hr_str).strip()
                    if len(h_clean) > 5: h_clean = h_clean[:5] 
                    if ':' not in h_clean and len(h_clean) >= 2: h_clean = f"{int(h_clean):02}:00"
                    
                    chave = f"{data_str}|{h_clean}"
                    premios = []
                    for i in range(2, 7):
                        if i < len(row):
                            p_str = str(row[i]).strip()
                            premios.append(p_str.zfill(4) if p_str.isdigit() else "0000")
                        else: premios.append("0000")
                    
                    dados_unicos[chave] = {
                        "data": data_str,
                        "horario": h_clean,
                        "premios": premios
                    }
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda x: f"{x['data']} {x['horario']}")
            return lista_final
        except: return [] 
    return []

def normalizar_data(data_str):
    data_str = str(data_str).strip()
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]
    for fmt in formatos:
        try: return datetime.strptime(data_str, fmt).date()
        except: continue
    return None

def normalizar_hora(hora_str):
    h_str = str(hora_str).strip()
    h_clean = re.sub(r'[a-zA-Z]', '', h_str).strip()
    if len(h_clean) > 5: h_clean = h_clean[:5] 
    try:
        if ':' in h_clean: return f"{int(h_clean.split(':')[0]):02}:{int(h_clean.split(':')[1]):02}"
        else: return f"{int(h_clean):02}:00"
    except: return "00:00"

def get_grupo(milhar_str):
    try:
        dezena = int(str(milhar_str)[-2:])
        if dezena == 0: return 25
        return (dezena - 1) // 4 + 1
    except:
        return 0

# =============================================================================
# --- 3. EXTRATOR UNIVERSAL BLINDADO ---
# =============================================================================

def raspar_dados_hibrido(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    tipo_ext = config.get('tipo_extracao', 'DUAL_PENTA')
    slug = config['slug']
    
    url = f"https://playbicho.com/resultado-jogo-do-bicho/{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Cache-Control': 'no-cache'
        }
        
        for _ in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200: break
            except requests.exceptions.RequestException:
                time.sleep(1)
                
        if r.status_code == 404 and data_alvo == date.today():
            url_fallback = f"https://playbicho.com/resultado-jogo-do-bicho/{slug}"
            r = requests.get(url_fallback, headers=headers, timeout=10)
            
        if r.status_code != 200: return None, f"Acesso negado. Servidor {r.status_code}."
            
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        try: target_h, target_m = map(int, horario_alvo.split(':'))
        except: return None, "Formato de hora inválido."
        
        for tabela in tabelas:
            txt_tabela = tabela.get_text().lower()
            if "federal" in txt_tabela and "federal" not in banca_key.lower(): continue 
            
            texto_analise = txt_tabela + " "
            cabecalho = tabela.find_previous(['h2', 'h3', 'h4', 'h5', 'caption'])
            if cabecalho: texto_analise += cabecalho.get_text().lower() + " "
                
            if tabela.parent:
                txt_parent = tabela.parent.get_text().lower()
                if len(txt_parent) < 4000:  
                    texto_analise += txt_parent + " "
            
            prev = tabela.previous_sibling
            for _ in range(5):
                if prev:
                    if prev.name == 'table': break 
                    if prev.name and prev.get_text(): texto_analise += prev.get_text().lower() + " "
                    elif isinstance(prev, str): texto_analise += prev.lower() + " "
                    prev = prev.previous_sibling

            times_parsed = []
            for h, m in re.findall(r'(?<!\d)(\d{1,2})[:hH]s?(\d{2})(?!\d)', texto_analise):
                times_parsed.append((int(h), int(m)))
            for h in re.findall(r'(?<!\d)(\d{1,2})\s?[hH]s?(?!\w)', texto_analise):
                times_parsed.append((int(h), 0))
            
            match_found = False
            target_total_mins = target_h * 60 + target_m
            
            for h, m in times_parsed:
                found_total_mins = h * 60 + m
                if abs(found_total_mins - target_total_mins) <= 30:
                    match_found = True
                    break
            
            if match_found:
                dezenas_encontradas = []
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 2:
                        numero_txt = cols[1].get_text().strip()
                        nums_premio = re.findall(r'\d+', cols[0].get_text())
                        if nums_premio:
                            p_idx = int(nums_premio[0])
                            limite = 5
                            if 1 <= p_idx <= limite:
                                clean_num = re.sub(r'\D', '', numero_txt)
                                if len(clean_num) >= 2: 
                                    dezenas_encontradas.append(clean_num[-4:].zfill(4))
                
                if len(dezenas_encontradas) >= 1: 
                    return dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas)), "Sucesso"
                return None, "Tabela Encontrada, mas falha ao ler as milhares."
                
        return None, f"Horário ({horario_alvo}) não encontrado na página."
    except Exception as e: return None, f"Erro de Varredura: {e}"

# =============================================================================
# --- 4. CÉREBRO MATEMÁTICO: PERSEGUIÇÃO DE GRUPOS (23x1) E RECORDES ---
# =============================================================================

@st.cache_data(show_spinner=False)
def analisar_atraso_grupos(history_slice):
    if len(history_slice) < 20: return None, None

    # Estrutura: 5 prêmios (0 a 4). Para cada prêmio, 25 grupos.
    stats = {
        premio_idx: {grupo: {'atraso': 0, 'max_atraso': 0} for grupo in range(1, 26)}
        for premio_idx in range(5)
    }

    # Varredura do Histórico do mais antigo ao mais novo
    for draw in history_slice:
        for premio_idx in range(5):
            milhar = draw['premios'][premio_idx]
            grupo_sorteado = get_grupo(milhar)
            
            for g in range(1, 26):
                if g == grupo_sorteado:
                    # O grupo saiu, atualizamos o teto máximo e zeramos o atraso
                    if stats[premio_idx][g]['atraso'] > stats[premio_idx][g]['max_atraso']:
                        stats[premio_idx][g]['max_atraso'] = stats[premio_idx][g]['atraso']
                    stats[premio_idx][g]['atraso'] = 0
                else:
                    # O grupo não saiu neste prêmio, soma 1 no atraso
                    stats[premio_idx][g]['atraso'] += 1

    # Após o loop, garantir que o atraso final não seja maior que o max histórico
    for premio_idx in range(5):
        for g in range(1, 26):
            if stats[premio_idx][g]['atraso'] > stats[premio_idx][g]['max_atraso']:
                stats[premio_idx][g]['max_atraso'] = stats[premio_idx][g]['atraso']

    # Compilar a lista de todos os grupos com suas estatísticas
    todos_grupos = []
    for premio_idx in range(5):
        for g in range(1, 26):
            a_atual = stats[premio_idx][g]['atraso']
            max_a = stats[premio_idx][g]['max_atraso']
            tensao = (a_atual / max_a * 100) if max_a > 0 else 0.0
            
            todos_grupos.append({
                "premio": premio_idx + 1,
                "grupo": g,
                "nome_grupo": NOME_GRUPOS[g],
                "atraso": a_atual,
                "max_atraso": max_a,
                "tensao": tensao
            })

    # Filtrar os Melhores Alvos Atuais (Atrasos reais rodando agora)
    alvos_ativos = [g for g in todos_grupos if g['atraso'] >= 12 and g['max_atraso'] > 0]
    alvos_ativos.sort(key=lambda x: x['atraso'], reverse=True)
    
    # Extrair os Recordes Históricos (Os maiores 'max_atraso' registrados na história da banca)
    recordes = sorted(todos_grupos, key=lambda x: x['max_atraso'], reverse=True)

    return alvos_ativos, recordes[:5] # Retorna os alvos ativos e o Top 5 de recordes da banca

# =============================================================================
# --- 5. INTERFACE NAVEGAÇÃO E TELAS ---
# =============================================================================

if "menu_nav" not in st.session_state:
    st.session_state.menu_nav = "🏠 ALVOS DE CAÇADA (Grupos)"

menu_opcoes = ["🏠 ALVOS DE CAÇADA (Grupos)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes, key="menu_nav")

st.sidebar.markdown("---")

if escolha_menu == "🏠 ALVOS DE CAÇADA (Grupos)":
    st.title("🎯 COMANDO CENTRAL (Perseguição 23x1)")
    st.markdown("O sistema vasculha **todos os prêmios isoladamente** buscando o **Grupo** que atingiu o limite de tensão.")
    
    ranking_global = []
    recordes_globais = []
    
    with st.spinner("📡 Rastreiando Grupos Atrasados e Quebras de Recorde..."):
        for banca_key, config in CONFIG_BANCAS.items():
            if config.get('radar_ativo') == True:
                historico = carregar_dados_hibridos(config['nome_aba'])
                if len(historico) >= 20:
                    alvos_banca, recordes_banca = analisar_atraso_grupos(historico)
                    
                    if alvos_banca:
                        # Pega os 2 melhores alvos absolutos da banca
                        melhores = alvos_banca[:2]
                        for alvo in melhores:
                            alvo['banca'] = config['display_name'].replace("🎯 ", "")
                            ranking_global.append(alvo)
                            
                    if recordes_banca:
                        for rec in recordes_banca:
                            rec['banca'] = config['display_name'].replace("🎯 ", "")
                            recordes_globais.append(rec)

    # --- ABA DE ALVOS ATIVOS ---
    st.markdown("### 🚨 TOP 5 ALVOS EM PERSEGUIÇÃO")
    if not ranking_global:
        st.info("⚠️ Sem dados suficientes ou sem grupos com atrasos críticos no momento.")
    else:
        ranking_global.sort(key=lambda x: x['atraso'], reverse=True)
        
        html_final = ""
        for idx, alvo in enumerate(ranking_global[:5]):
            banca = alvo['banca']
            premio = alvo['premio']
            grupo = alvo['grupo']
            nome = alvo['nome_grupo']
            atraso = alvo['atraso']
            teto = alvo['max_atraso']
            tensao = alvo['tensao']
            dezenas_do_grupo = get_dezenas_grupo(grupo)
            
            html_ranking = (
                f'<div class="card-ranking">'
                f'<h3 style="margin:0 0 10px 0; color:#fff;">#{idx+1} | BANCA: {banca} | {premio}º PRÊMIO</h3>'
                f'<div class="card-alvo">'
                f'  <h1 style="margin:0; color:#ff3333; font-size:2.5em;">GRUPO {grupo} ({nome})</h1>'
                f'  <p style="margin:5px 0 0 0; color:#ffcc00; font-size:1.1em;">Dezenas: <b>{dezenas_do_grupo}</b></p>'
                f'  <p style="margin:15px 0 0 0; color:#fff; font-size:1.1em;">Aposte o <b>Grupo {grupo}</b> isoladamente no <b>{premio}º Prêmio</b>.</p>'
                f'</div>'
                f'<div style="margin-top:15px; display:flex; justify-content:space-around; font-size:1.1em; color:#ddd; background:#222; padding:10px; border-radius:5px;">'
                f'  <span style="color:#ffaa00;"><b>⏳ Atraso Atual:</b> {atraso} sorteios</span>'
                f'  <span><b>🛑 Teto Histórico:</b> {teto} sorteios</span>'
                f'  <span><b>🔥 Tensão:</b> {tensao:.1f}%</span>'
                f'</div>'
                f'</div>'
            )
            html_final += html_ranking
            
        st.markdown(html_final, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # --- NOVO: O LIVRO DOS RECORDES ---
    st.markdown("### 🏆 HALL DA FAMA DOS ATRASOS (O Limite da Máquina)")
    st.markdown("Use esta tabela como sua régua de medição. Aqui estão os **5 maiores atrasos já registrados na história** do seu banco de dados. Nunca inicie uma perseguição muito longe destes limites.")
    
    if not recordes_globais:
        st.info("⚠️ Dados insuficientes para gerar os recordes.")
    else:
        recordes_globais.sort(key=lambda x: x['max_atraso'], reverse=True)
        
        html_recordes = ""
        for idx, rec in enumerate(recordes_globais[:5]): # Pega os Top 5 gerais do Brasil
            html_recordes += (
                f'<div class="card-recorde">'
                f'  <span style="font-size:1.2em; font-weight:bold; color:#ffd700;">#{idx+1} - {rec["max_atraso"]} Sorteios Seguidos</span><br>'
                f'  <span style="color:#ccc;">Aconteceu na <b>{rec["banca"]}</b>, no <b>{rec["premio"]}º Prêmio</b>. O alvo foi o <b>Grupo {rec["grupo"]} ({rec["nome_grupo"]})</b>.</span>'
                f'</div>'
            )
        st.markdown(html_recordes, unsafe_allow_html=True)
        
else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    
    url_banca = f"https://playbicho.com/resultado-jogo-do-bicho/{config['slug']}-do-dia-{date.today().strftime('%Y-%m-%d')}"
        
    st.sidebar.markdown(f"<a href='{url_banca}' target='_blank'><button style='width: 100%; border-radius: 5px; font-weight: bold; background-color: #007bff; color: white; padding: 8px 10px; border: none; cursor: pointer; margin-bottom: 10px;'>🌐 Visitar Site da Banca</button></a>", unsafe_allow_html=True)
    
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)", "✍️ Manual"])
    
    if modo_extracao == "🎯 Unitária":
        data_busca = date.today()
        horario_busca = config['horarios'][0]
        
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key=f"rad_dt_{banca_selecionada}")
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.date_input("Escolha:", date.today(), key=f"dt_pk_{banca_selecionada}")
            
            lista_horarios = config['horarios'].copy()
            horario_busca = st.selectbox("Horário:", lista_horarios, key=f"sel_hr_{banca_selecionada}")
            
            if st.button("🚀 Baixar & Salvar", key=f"btn_b_stb_{banca_selecionada}"):
                ws_milhar = conectar_planilha(config['nome_aba'])
                if ws_milhar:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try: 
                            existentes = ws_milhar.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                            if premios:
                                ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                st.toast(f"Sucesso!", icon="✅")
                                st.cache_data.clear() 
                                time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro na Planilha do Google")

    elif modo_extracao == "🌪️ Em Massa (Turbo)": 
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1), key=f"dt_ini_{banca_selecionada}")
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today(), key=f"dt_fim_{banca_selecionada}")
        
        if st.sidebar.button("🚀 INICIAR TURBO", key=f"btn_tb_stb_{banca_selecionada}"):
            ws_milhar = conectar_planilha(config['nome_aba'])
            if ws_milhar:
                status = st.sidebar.empty(); bar = st.sidebar.progress(0)
                try: chaves_m = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_milhar.get_all_values() if len(r) >= 2 and normalizar_data(r[0])]
                except: chaves_m = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config['horarios']); op_atual = 0; sucessos = 0
                buffer_m = []
                
                for dia in lista_datas:
                    for hora_base in config['horarios']:
                        hora_efetiva = hora_base
                                
                        op_atual += 1; bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora_efetiva}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{normalizar_hora(hora_efetiva)}"
                        
                        if chave_atual in chaves_m: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora_efetiva > datetime.now().strftime("%H:%M"): continue
                        
                        premios, msg = raspar_dados_hibrido(banca_selecionada, dia, hora_efetiva)
                        if premios:
                            buffer_m.append([dia.strftime('%Y-%m-%d'), hora_efetiva] + premios); chaves_m.append(chave_atual)
                            sucessos += 1
                        time.sleep(1.0) 
                status.text("🚚 Salvando no Banco de Dados...")
                if buffer_m: ws_milhar.append_rows(buffer_m)
                st.cache_data.clear() 
                bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos registros."); time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão Google")

    elif modo_extracao == "✍️ Manual":
        data_busca_man = date.today()
        
        with st.sidebar.expander("📝 Lançar Manualmente", expanded=True):
            opcao_data_man = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key=f"rad_man_{banca_selecionada}")
            if opcao_data_man == "Hoje": data_busca_man = date.today()
            elif opcao_data_man == "Ontem": data_busca_man = date.today() - timedelta(days=1)
            else: data_busca_man = st.date_input("Escolha:", date.today(), key=f"dt_man_{banca_selecionada}")
            
            lista_horarios_man = config['horarios'].copy()
            horario_busca_man = st.selectbox("Horário:", lista_horarios_man, key=f"hr_man_{banca_selecionada}")
            
            st.markdown("🎯 **Preencha as Milhares (4 dígitos):**")
            p1 = st.text_input("1º Prêmio", max_chars=4, key=f"man_p1_{banca_selecionada}")
            p2 = st.text_input("2º Prêmio", max_chars=4, key=f"man_p2_{banca_selecionada}")
            p3 = st.text_input("3º Prêmio", max_chars=4, key=f"man_p3_{banca_selecionada}")
            p4 = st.text_input("4º Prêmio", max_chars=4, key=f"man_p4_{banca_selecionada}")
            p5 = st.text_input("5º Prêmio", max_chars=4, key=f"man_p5_{banca_selecionada}")
            
            if st.button("💾 Salvar Resultado", key=f"btn_salvar_man_{banca_selecionada}", use_container_width=True):
                def limpar_milhar(m):
                    num = re.sub(r'\D', '', str(m))
                    return num.zfill(4) if num else "0000"
                
                premios_finais = [limpar_milhar(p1), limpar_milhar(p2), limpar_milhar(p3), limpar_milhar(p4), limpar_milhar(p5)]
                ws_milhar = conectar_planilha(config['nome_aba'])
                
                if ws_milhar:
                    with st.spinner(f"Salvando {horario_busca_man} manualmente..."):
                        try: 
                            existentes = ws_milhar.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual_man = f"{data_busca_man.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca_man)}"
                        
                        if chave_atual_man in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            ws_milhar.append_row([data_busca_man.strftime('%Y-%m-%d'), horario_busca_man] + premios_finais)
                            st.toast(f"Salvo!", icon="✅")
                            st.cache_data.clear() 
                            time.sleep(1); st.rerun()
                else: st.error("Erro na Planilha")

    # --- PÁGINA DA BANCA ---
    st.header(f"{config['display_name']} - Status dos Grupos")
    
    with st.spinner("Analisando Atrasos em 5 Dimensões..."):
        historico = carregar_dados_hibridos(config['nome_aba'])
        
    if len(historico) > 0:
        ult = historico[-1]
        st.success(f"📅 **Último Sorteio Lido:** {ult['data']} às {ult['horario']}")
        
        # --- ALARME DE PERSEGUIÇÃO LOCAL ---
        alvos_locais, _ = analisar_atraso_grupos(historico)
        if alvos_locais:
            st.markdown("### 🚨 ALVOS EM PERSEGUIÇÃO ATIVA NESTA BANCA")
            for alvo in alvos_locais:
                dez_str = get_dezenas_grupo(alvo['grupo'])
                st.markdown(f"""
                <div style='background-color:#4a0000; border-left: 4px solid #ff0000; padding: 15px; margin-bottom: 10px; border-radius: 4px;'>
                    <span style='color:#fff; font-size:1.2em;'><b>{alvo['premio']}º PRÊMIO</b> ➔ <b>Grupo {alvo['grupo']} ({alvo['nome_grupo']})</b></span><br>
                    <span style='color:#ffcc00; font-size:1.0em;'>Dezenas Associadas: <b>{dez_str}</b></span><br>
                    <span style='color:#aaa; font-size:0.95em;'>⏳ Atraso Atual: {alvo['atraso']} sorteios | 🛑 Teto Histórico: {alvo['max_atraso']} sorteios</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("✅ Área limpa. Nenhum grupo em estado crítico de perseguição nesta banca no momento.")
        
        st.markdown("### 📊 Banco de Dados Bruto (Últimos Sorteios)")
        df_show = pd.DataFrame(historico)
        st.dataframe(df_show.tail(15), use_container_width=True)
    else:
        st.warning("⚠️ Base vazia. Extraia os dados primeiro através do menu ao lado.")
