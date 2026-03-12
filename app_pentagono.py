import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import time
from collections import Counter

# --- IMPORTAÇÃO DA INTELIGÊNCIA ARTIFICIAL ---
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    HAS_AI = True
except ImportError:
    HAS_AI = False

# =============================================================================
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V95.0 Sniper 8D", page_icon="👑", layout="wide")

CONFIG_BANCAS = {
    "TRADICIONAL": { "display_name": "TRADICIONAL (Dezenas)", "nome_aba": "BASE_TRADICIONAL_DEZ", "slug": "loteria-tradicional", "tipo": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"] },
    
    "TRADICIONAL_MILHAR": { "display_name": "👑 TRADICIONAL (Vitorino)", "nome_aba": "TRADICIONAL_MILHAR", "slug": "loteria-tradicional", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_SOLO", "horarios": ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"], "base_dez": "BASE_TRADICIONAL_DEZ" },
    
    "LOTEP_MILHAR": { "display_name": "👑 LOTEP (Vitorino)", "nome_aba": "LOTEP_MILHAR", "slug": "lotep", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:45", "12:45", "15:45", "18:00"], "base_dez": "LOTEP_TOP5" },
    
    "CAMINHO_MILHAR": { "display_name": "👑 CAMINHO (Vitorino)", "nome_aba": "CAMINHO_MILHAR", "slug": "caminho-da-sorte", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"], "base_dez": "CAMINHO_TOP5" },
    
    "MONTE_MILHAR": { "display_name": "👑 MONTE CARLOS (Vitorino)", "nome_aba": "MONTE_MILHAR", "slug": "nordeste-monte-carlos", "tipo": "MILHAR_VIEW", "tipo_extracao": "DUAL_PENTA", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"], "base_dez": "MONTE_TOP5" }
}

GRUPO_TO_DEZENAS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
    dezenas_do_grupo = []
    for n in range(inicio, fim + 1):
        d_str = "00" if n == 100 else f"{n:02}"
        dezenas_do_grupo.append(d_str)
    GRUPO_TO_DEZENAS[g] = dezenas_do_grupo

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #ffd700 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #00ff00; }
    .css-1wivap2 { font-size: 14px !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM ---
# =============================================================================

def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

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

def carregar_dados_hibridos(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return []
            
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 3:
                    dt_obj = normalizar_data(row[0])
                    hr_str = normalizar_hora(row[1])
                    if dt_obj:
                        chave = f"{dt_obj.strftime('%Y-%m-%d')}|{hr_str}"
                        premios = []
                        for i in range(2, 7):
                            if i < len(row):
                                p_str = str(row[i]).strip()
                                if p_str.isdigit(): premios.append(p_str.zfill(2))
                                else: premios.append("00")
                            else: premios.append("00")
                        
                        dados_unicos[chave] = {
                            "data": dt_obj.strftime('%Y-%m-%d'),
                            "horario": hr_str,
                            "premios": premios
                        }
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda x: datetime.strptime(f"{x['data']} {x['horario']}", "%Y-%m-%d %H:%M"))
            return lista_final
        except: return [] 
    return []

def raspar_dados_hibrido(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    tipo_ext = config.get('tipo_extracao', config['tipo'])
    
    url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    if data_alvo == date.today(): url = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
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
                        
                        if normalizar_hora(h_detect) == normalizar_hora(horario_alvo):
                            dezenas_encontradas = []
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                cols = linha.find_all('td')
                                if len(cols) >= 2:
                                    premio_txt = cols[0].get_text().strip()
                                    numero_txt = cols[1].get_text().strip()
                                    nums_premio = re.findall(r'\d+', premio_txt)
                                    if nums_premio:
                                        p_idx = int(nums_premio[0])
                                        limite = 5 if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW", "PENTA"] else 1
                                        if 1 <= p_idx <= limite:
                                            clean_num = re.sub(r'\D', '', numero_txt)
                                            if len(clean_num) >= 2: 
                                                if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]:
                                                    dezenas_encontradas.append(clean_num[-4:].zfill(4))
                                                else:
                                                    dezenas_encontradas.append(clean_num[-2:])
                                                
                            if tipo_ext in ["DUAL_SOLO", "DUAL_PENTA", "MILHAR_VIEW"]:
                                if len(dezenas_encontradas) >= 1: 
                                    res = dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas))
                                    return res[:5], "Sucesso"
                            else:
                                if tipo_ext == "SOLO" and len(dezenas_encontradas) >= 1: return [dezenas_encontradas[0], "00", "00", "00", "00"], "Sucesso"
                                elif len(dezenas_encontradas) >= 5: return dezenas_encontradas[:5], "Sucesso"
                            return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. NOVO CÉREBRO: MARKOV SNIPER 8D ---
# =============================================================================

def calcular_radar_sniper_8d(hist_milhar):
    if len(hist_milhar) < 40: return []
    resultados_radar = []
    
    for p_idx in range(5):
        milhares_do_premio = []
        for row in hist_milhar:
            try:
                m = str(row['premios'][p_idx]).zfill(4)
                if m != "0000": milhares_do_premio.append(m[-4:])
            except: pass
            
        if len(milhares_do_premio) < 40: continue
            
        ult_milhar = milhares_do_premio[-1]
        cabeca_atual = ult_milhar[0]
        
        # --- FUNÇÃO DE CORTES MARKOV ---
        def get_cuts_markov(history_slice):
            if len(history_slice) < 2: return "0", "1", 0
            last_m = history_slice[-1]
            head = last_m[0]
            next_milhares = []
            
            for j in range(len(history_slice)-1):
                if history_slice[j][0] == head:
                    next_milhares.append(history_slice[j+1])
                    
            overall_digits = "".join(history_slice[-100:])
            overall_counts = {str(d): overall_digits.count(str(d)) for d in range(10)}
            
            # Se não tiver histórico suficiente para a cabeça, olha os últimos 50 gerais
            if len(next_milhares) < 3:
                all_digits = "".join(history_slice[-50:])
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                occ = len(next_milhares)
            else:
                all_digits = "".join(next_milhares)
                counts = {str(d): all_digits.count(str(d)) for d in range(10)}
                occ = len(next_milhares)
                
            # Ordena pelo que menos saiu. Critério de desempate: frequência global nos 100
            sorted_digits = sorted(counts.items(), key=lambda x: (x[1], overall_counts[x[0]], x[0]))
            return sorted_digits[0][0], sorted_digits[1][0], occ

        corte1_atual, corte2_atual, ocorrencias = get_cuts_markov(milhares_do_premio)
        
        # Cria a array de 8 dígitos limpos
        esquadrao_base = [str(d) for d in range(10) if str(d) not in [corte1_atual, corte2_atual]]
        # Transforma na string duplicada pronta para colar no app da banca (Ex: 1,1,2,2)
        esquadrao_formatado = ",".join([f"{d},{d}" for d in esquadrao_base])
        
        rec_msg = f"🧠 **Inteligência de Repulsão (Markov):** A última milhar foi `{ult_milhar}` (Cabeça **{cabeca_atual}**). Analisando os últimos {ocorrencias} eventos idênticos no histórico, os dígitos `{corte1_atual}` e `{corte2_atual}` somem totalmente do globo na rodada seguinte."
        
        simulacoes_disponiveis = min(30, len(milhares_do_premio) - 10)
        backtest_hist = []
        vitorias = 0
        derrotas = 0
        
        # --- TÚNEL DO TEMPO (BACKTEST DA ESTRATÉGIA 8D) ---
        for i in range(simulacoes_disponiveis, 0, -1):
            alvo_real = milhares_do_premio[-i]
            
            idx_fim_hist = len(milhares_do_premio) - i
            janela_hist = milhares_do_premio[:idx_fim_hist]
            
            if not janela_hist: continue
                
            c1_hist, c2_hist, _ = get_cuts_markov(janela_hist)
            esq_hist = [str(d) for d in range(10) if str(d) not in [c1_hist, c2_hist]]
            
            # Condição de Vitória 8D Invertida: NENHUM dígito sorteado pode ser os que nós cortamos.
            # Se os 4 dígitos do sorteio estiverem no nosso esquadrão, ganhamos os R$ 92,00.
            venceu = all(d in esq_hist for d in alvo_real)
            
            if venceu:
                vitorias += 1
                if i <= 5: backtest_hist.append("✅")
            else:
                derrotas += 1
                if i <= 5: backtest_hist.append("❌")

        total_simulado = vitorias + derrotas
        taxa_acerto = (vitorias / total_simulado) * 100 if total_simulado > 0 else 0
        
        resultados_radar.append({
            "premio": p_idx + 1,
            "ult_milhar": ult_milhar,
            "rec_msg": rec_msg,
            "cortes": f"{corte1_atual} e {corte2_atual}",
            "esquadrao": esquadrao_formatado,
            "backtest": backtest_hist,
            "vitorias": vitorias,
            "derrotas": derrotas,
            "taxa_valor": taxa_acerto,
            "taxa": f"{taxa_acerto:.1f}%"
        })
    return resultados_radar


# =============================================================================
# --- 5. INTERFACE NAVEGAÇÃO E TELAS ---
# =============================================================================

if "menu_nav" not in st.session_state:
    st.session_state.menu_nav = "🏠 RADAR GERAL (Home)"

def acionar_teletransporte(destino):
    st.session_state.menu_nav = destino

menu_opcoes = ["🏠 RADAR GERAL (Home)"] + list(CONFIG_BANCAS.keys())
escolha_menu = st.sidebar.selectbox("Navegação Principal", menu_opcoes, key="menu_nav")

def acao_limpar_banco(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        try:
            raw = ws.get_all_values()
            if len(raw) < 2: return "Banco vazio"
            cabecalho = raw[0]
            dados_unicos = {}
            for row in raw[1:]:
                if len(row) >= 2:
                    dt = normalizar_data(row[0])
                    hr = normalizar_hora(row[1])
                    if dt:
                        chave = f"{dt.strftime('%Y-%m-%d')}|{hr}"
                        row[0] = dt.strftime('%Y-%m-%d')
                        row[1] = hr
                        dados_unicos[chave] = row
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda r: datetime.strptime(f"{r[0]} {r[1]}", "%Y-%m-%d %H:%M"))
            ws.clear()
            ws.append_row(cabecalho)
            if lista_final: ws.append_rows(lista_final)
            return f"Sucesso! Reduzido de {len(raw)-1} para {len(lista_final)} registros."
        except Exception as e: return f"Erro: {e}"
    return "Erro Conexão"

st.sidebar.markdown("---")

if escolha_menu == "🏠 RADAR GERAL (Home)":
    st.title("🛡️ PENTÁGONO - SCANNER DE MARKOV (8D)")
    st.markdown("O sistema está varrendo os globos elegíveis. O foco agora é achar o prêmio que está com a maior **Vantagem Matemática (Taxa de Acerto)** usando a Estratégia de 16 números (8 Dígitos Duplos).")
    
    alertas_sniper = []
    
    with st.spinner("📡 Scanner Ativo: Analisando Efeito Sombra e Repulsões..."):
        for banca_key, config in CONFIG_BANCAS.items():
            if config['tipo'] == 'MILHAR_VIEW' and "TRADICIONAL" not in banca_key:
                hist_milhar = carregar_dados_hibridos(config['nome_aba'])
                if len(hist_milhar) >= 40:
                    radar_dados = calcular_radar_sniper_8d(hist_milhar)
                    
                    for alvo in radar_dados:
                        nome_banca_limpo = config['display_name'].replace("👑 ", "")
                        
                        # ALERTA DE ESTATÍSTICA ALTA: Se a taxa for maior que 46% (A chance nua é 40.9%), temos uma Edge gigante.
                        if alvo['taxa_valor'] >= 46.0:
                            alertas_sniper.append({
                                "banca_key": banca_key,
                                "banca": nome_banca_limpo,
                                "premio": alvo['premio'],
                                "taxa": alvo['taxa'],
                                "cortes": alvo['cortes']
                            })

    if not alertas_sniper:
        st.info("⚠️ O Globo está estável e imprevisível agora. Nenhuma banca apresenta uma vantagem matemática segura (acima de 46%) neste momento. Mantenha os recursos guardados.")
    else:
        st.markdown("### 🎯 ALVOS TRAVADOS (Vantagem Matemática Detectada)")
        for a in alertas_sniper:
            with st.container(border=True):
                col_txt, col_btn = st.columns([4, 1])
                with col_txt:
                    st.success(f"🔥 **{a['banca']} - {a['premio']}º Prêmio** | Taxa de Vitória da Estratégia: **{a['taxa']}**! Os dígitos para corte são `{a['cortes']}`.")
                with col_btn:
                    st.button("🎯 Abrir Banca", key=f"go_{a['banca_key']}_{a['premio']}", on_click=acionar_teletransporte, args=(a['banca_key'],), use_container_width=True)

else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    
    url_banca = f"https://www.resultadofacil.com.br/resultados-{config['slug']}-de-hoje"
    st.sidebar.markdown(f"<a href='{url_banca}' target='_blank'><button style='width: 100%; border-radius: 5px; font-weight: bold; background-color: #007bff; color: white; padding: 8px 10px; border: none; cursor: pointer; margin-bottom: 10px;'>🌐 Visitar Site da Banca</button></a>", unsafe_allow_html=True)
    
    if st.sidebar.button("🧹 EXECUTAR FAXINA NO BANCO DE DADOS"):
        with st.spinner("Limpando e reescrevendo planilha..."):
            res_principal = acao_limpar_banco(config['nome_aba'])
            if 'base_dez' in config: acao_limpar_banco(config['base_dez'])
            if "Sucesso" in res_principal: st.sidebar.success("Faxina Dupla Concluída com Sucesso!")
            else: st.sidebar.error(res_principal)
            time.sleep(2)
            st.rerun()
            
    st.sidebar.markdown("---")
    
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "🌪️ Em Massa (Turbo)", "✍️ Manual"])
    
    if modo_extracao == "🎯 Unitária":
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            opcao_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
            if opcao_data == "Hoje": data_busca = date.today()
            elif opcao_data == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.sidebar.date_input("Escolha:", date.today())
            
            lista_horarios = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca.weekday() in [2, 5]: 
                if "20:00" in lista_horarios:
                    lista_horarios[lista_horarios.index("20:00")] = "19:30"
                    
            horario_busca = st.selectbox("Horário:", lista_horarios)
            
            if st.button("🚀 Baixar & Salvar"):
                aba_dez = config.get('base_dez', config['nome_aba'])
                aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
                tipo_ext = config.get('tipo_extracao', config['tipo'])
                
                ws_dez = conectar_planilha(aba_dez)
                ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
                
                if ws_dez:
                    with st.spinner(f"Buscando {horario_busca}..."):
                        try: 
                            existentes = ws_dez.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                            if premios:
                                if tipo_ext == "DUAL_SOLO":
                                    row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca, premios[0][-2:], "00", "00", "00", "00"]
                                    ws_dez.append_row(row_dez)
                                    if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                    st.toast(f"Duplo Sucesso! Inteligência atualizada.", icon="✅")
                                elif tipo_ext == "DUAL_PENTA":
                                    row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios]
                                    ws_dez.append_row(row_dez)
                                    if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                    st.toast(f"Motor Duplo Acionado! Dados salvos na base e no Vitorino.", icon="✅")
                                time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.error("Erro na Planilha")
                
    elif modo_extracao == "🌪️ Em Massa (Turbo)": 
        st.sidebar.subheader("🌪️ Extração Turbo")
        col1, col2 = st.sidebar.columns(2)
        with col1: data_ini = st.sidebar.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.sidebar.date_input("Fim:", date.today())
        
        if st.sidebar.button("🚀 INICIAR TURBO"):
            aba_dez = config.get('base_dez', config['nome_aba'])
            aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
            tipo_ext = config.get('tipo_extracao', config['tipo'])
            
            ws_dez = conectar_planilha(aba_dez)
            ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
            
            if ws_dez:
                status = st.sidebar.empty(); bar = st.sidebar.progress(0)
                try: chaves_d = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_dez.get_all_values() if len(r) >= 2 and normalizar_data(r[0])]
                except: chaves_d = []
                try: chaves_m = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_milhar.get_all_values() if len(r) >= 2 and normalizar_data(r[0])] if ws_milhar else []
                except: chaves_m = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(config['horarios']); op_atual = 0; sucessos = 0
                buffer_dez = []
                buffer_m = []
                
                for dia in lista_datas:
                    for hora_base in config['horarios']:
                        hora_efetiva = hora_base
                        if "CAMINHO" in banca_selecionada and dia.weekday() in [2, 5]:
                            if hora_base == "20:00":
                                hora_efetiva = "19:30"
                                
                        op_atual += 1; bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora_efetiva}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{normalizar_hora(hora_efetiva)}"
                        
                        if chave_atual in chaves_d: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora_efetiva > datetime.now().strftime("%H:%M"): continue
                        
                        premios, msg = raspar_dados_hibrido(banca_selecionada, dia, hora_efetiva)
                        if premios:
                            if tipo_ext == "DUAL_SOLO":
                                row_d = [dia.strftime('%Y-%m-%d'), hora_efetiva, premios[0][-2:], "00", "00", "00", "00"]
                                buffer_dez.append(row_d); chaves_d.append(chave_atual)
                                if ws_milhar and chave_atual not in chaves_m: buffer_m.append([dia.strftime('%Y-%m-%d'), hora_efetiva] + premios); chaves_m.append(chave_atual)
                            elif tipo_ext == "DUAL_PENTA":
                                row_d = [dia.strftime('%Y-%m-%d'), hora_efetiva] + [p[-2:] for p in premios]
                                buffer_dez.append(row_d); chaves_d.append(chave_atual)
                                if ws_milhar and chave_atual not in chaves_m: buffer_m.append([dia.strftime('%Y-%m-%d'), hora_efetiva] + premios); chaves_m.append(chave_atual)
                            sucessos += 1
                        time.sleep(1.0)
                status.text("🚚 Sincronizando Matrizes Fantasmas e Visuais...")
                if buffer_dez: ws_dez.append_rows(buffer_dez)
                if buffer_m and ws_milhar: ws_milhar.append_rows(buffer_m)
                bar.progress(100); status.success(f"🏁 Concluído! {sucessos} novos registros."); time.sleep(2); st.rerun()
            else: st.sidebar.error("Erro Conexão")
            
    elif modo_extracao == "✍️ Manual":
        with st.sidebar.expander("📝 Lançar Manualmente", expanded=True):
            opcao_data_man = st.radio("Data:", ["Hoje", "Ontem", "Outra"], key="data_man")
            if opcao_data_man == "Hoje": data_busca = date.today()
            elif opcao_data_man == "Ontem": data_busca = date.today() - timedelta(days=1)
            else: data_busca = st.date_input("Escolha:", date.today(), key="data_pick_man")
            
            lista_horarios = config['horarios'].copy()
            if "CAMINHO" in banca_selecionada and data_busca.weekday() in [2, 5]: 
                if "20:00" in lista_horarios:
                    lista_horarios[lista_horarios.index("20:00")] = "19:30"
                    
            horario_busca = st.selectbox("Horário:", lista_horarios, key="hora_man")
            
            st.markdown("🎯 **Preencha as Milhares (4 dígitos):**")
            p1 = st.text_input("1º Prêmio", max_chars=4, key="man_p1")
            p2 = st.text_input("2º Prêmio", max_chars=4, key="man_p2")
            p3 = st.text_input("3º Prêmio", max_chars=4, key="man_p3")
            p4 = st.text_input("4º Prêmio", max_chars=4, key="man_p4")
            p5 = st.text_input("5º Prêmio", max_chars=4, key="man_p5")
            
            if st.button("💾 Salvar Resultado", key="btn_salvar_man", use_container_width=True):
                def limpar_milhar(m):
                    num = re.sub(r'\D', '', str(m))
                    return num.zfill(4) if num else "0000"
                
                premios_finais = [limpar_milhar(p1), limpar_milhar(p2), limpar_milhar(p3), limpar_milhar(p4), limpar_milhar(p5)]
                
                aba_dez = config.get('base_dez', config['nome_aba'])
                aba_milhar = config['nome_aba'] if 'MILHAR' in config['nome_aba'] else f"{banca_selecionada}_MILHAR"
                tipo_ext = config.get('tipo_extracao', config['tipo'])
                
                ws_dez = conectar_planilha(aba_dez)
                ws_milhar = conectar_planilha(aba_milhar) if 'MILHAR' in aba_milhar else None
                
                if ws_dez:
                    with st.spinner(f"Salvando {horario_busca} manualmente..."):
                        try: 
                            existentes = ws_dez.get_all_values()
                            chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in existentes if len(r) >= 2 and normalizar_data(r[0])]
                        except: chaves = []
                        chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}"
                        
                        if chave_atual in chaves: st.warning("Resultado já existe no banco de dados!")
                        else:
                            if tipo_ext == "DUAL_SOLO":
                                row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca, premios_finais[0][-2:], "00", "00", "00", "00"]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios_finais)
                                st.toast(f"Lançamento Manual Salvo!", icon="✅")
                            elif tipo_ext == "DUAL_PENTA":
                                row_dez = [data_busca.strftime('%Y-%m-%d'), horario_busca] + [p[-2:] for p in premios_finais]
                                ws_dez.append_row(row_dez)
                                if ws_milhar: ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios_finais)
                                st.toast(f"Lançamento Manual Salvo com Sucesso!", icon="✅")
                            time.sleep(1); st.rerun()
                else: st.error("Erro na Planilha")

    # --- PÁGINA DA BANCA ---
    
    if config['tipo'] == "MILHAR_VIEW":
        st.header(f"👑 Estratégia Sniper 8D (Motor de Markov)")
        
        with st.spinner("Lendo matrizes históricas e calculando o Efeito Sombra..."):
            hist_milhar = carregar_dados_hibridos(config['nome_aba'])
            
        if len(hist_milhar) > 0:
            ult = hist_milhar[-1]
            st.success(f"📅 **Último Sorteio Lido:** {ult['data']} às {ult['horario']}")

            st.markdown("### 🎯 Radar Sniper 8D (Colete de 16 Números)")
            st.write("O algoritmo varre a história para descobrir quais **2 dígitos** desaparecem após a cabeça da milhar atual. Jogue com os **8 dígitos restantes duplicados**.")
            
            radar_inv = calcular_radar_sniper_8d(hist_milhar)
            
            for alvo in radar_inv:
                with st.container(border=True):
                    c_topo1, c_topo2 = st.columns([3, 1])
                    with c_topo1:
                        st.subheader(f"🏆 {alvo['premio']}º Prêmio | Última: `{alvo['ult_milhar']}`")
                    with c_topo2:
                        st.metric("Teto de Acerto (Histórico)", alvo['taxa'])
                        
                    st.info(alvo['rec_msg'])
                    
                    st.markdown(f"**✂️ O Corte:** Elimine os números `{alvo['cortes']}`")
                    st.code(alvo['esquadrao'], language="text")
                    st.caption("☝️ Copie a linha acima e cole no aplicativo de aposta. (Combinação 8D Duplicada = 4.096 milhares).")
                    
                    st.markdown("---")
                    st.markdown(f"**🕰️ Backtest (Últimos 5 jogos testando esse corte):** {' | '.join(alvo['backtest'])}")
                    st.caption(f"Nos últimos 30 simulados: ✅ {alvo['vitorias']} Acertos | ❌ {alvo['derrotas']} Falhas")

            # --- CALCULADORA DE HEDGE ---
            st.markdown("---")
            st.subheader("🛡️ Calculadora de Hedge (Seguro de Banca)")
            
            with st.container(border=True):
                col_calc1, col_calc2 = st.columns(2)
                with col_calc1:
                    valor_milhar = st.number_input("💰 Valor da Invertida 8D (R$):", min_value=1.0, value=40.96, step=1.0)
                
                # Hedge para R$ 41:
                seguro_recomendado = valor_milhar / 21 
                custo_total = valor_milhar + seguro_recomendado
                retorno_seguro = seguro_recomendado * 23
                
                with col_calc2:
                    st.info(f"**🛡️ Jogue no Grupo da Milhar Sorteada:** R$ {seguro_recomendado:.2f}")
                    st.caption(f"Custo Total: R$ {custo_total:.2f} | Prêmio Grupo: R$ {retorno_seguro:.2f}")

        else:
            st.warning("⚠️ Base vazia. Extraia os dados primeiro através do menu ao lado.")

    # ==========================================
    # PAINEL DE EXTRAÇÃO BASE (DEZENAS/DUAL)
    # ==========================================
    else:
        st.header(f"🔭 {config['display_name']} - Oracle 46")
        with st.spinner("Carregando e Limpando dados..."):
            historico = carregar_dados_hibridos(config['nome_aba'])
            
        if len(historico) > 0:
            ult = historico[-1]
            if config['tipo'] == "DUAL_SOLO": st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **1º Prêmio:** {str(ult['premios'][0])[-2:]}")
            else: st.info(f"📅 **Último Sorteio:** {ult['data']} às {ult['horario']} | **P1:** {ult['premios'][0]} ... **P5:** {ult['premios'][4]}")
            
            range_abas = [0, 1] 
            abas = st.tabs(["🔮 Oracle 46", "🎯 Unidades"])
            
            for idx_aba in range_abas:
                with abas[idx_aba]:
                    if idx_aba == 1:
                        st.markdown("### 🏹 The Chaser (Perseguição de Ciclo de 8 Jogos)")
                        estado_chaser = rastrear_estado_chaser(historico, 0)
                        if estado_chaser['target'] is not None:
                            col_gold, col_info = st.columns([1, 2])
                            with col_gold: st.metric("🌟 Alvo Principal", f"Final {estado_chaser['target']}")
                            with col_info:
                                if estado_chaser['status'] == 'ativo': st.warning(f"🔒 **PERSEGUIÇÃO (TENTATIVA {estado_chaser['attempts']+1} DE 8)**")
                                else: st.success("🎯 **NOVO CICLO (TENTATIVA 1 DE 8)**")
                                st.caption(f"Base Matemática: {estado_chaser['prob']:.1f}%")
                        st.markdown("---")
                        markov, ciclo, quente = calcular_3_estrategias_unidade(historico, 0)
                        c_m, c_c, c_q = st.columns(3)
                        c_m.metric('1. Ímã (Markov)', f"Final {markov}", "Maior atração")
                        c_c.metric('2. Fechamento Ciclo', f"Final {ciclo}", "Mais atrasada", delta_color="off")
                        c_q.metric('3. Tendência Quente', f"Final {quente}", "Moda repetição")
                    else:
                        lista_matrix, conf_total, info_predator, dados_oracle = gerar_estrategia_oracle_46(historico, idx_aba)
                        if HAS_AI:
                            c_ima, c_rep = st.columns(2)
                            with c_ima: st.success(f"🧲 **ÍMÃS:** {dados_oracle['imas']}")
                            with c_rep: st.error(f"⛔ **REPELIDOS:** {dados_oracle['repelidos']}")
                        with st.container(border=True): st.code(", ".join(lista_matrix), language="text")
        else:
            st.warning("⚠️ Base vazia. Extraia os dados primeiro através do menu ao lado.")
