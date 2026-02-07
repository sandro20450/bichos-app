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

# =============================================================================
# --- 1. CONFIGURAÇÕES E DADOS ---
# =============================================================================
st.set_page_config(page_title="CENTURION 75 - V5.1 Saturation", page_icon="🛡️", layout="wide")

# Configuração das Bancas e Abas (Dezenas)
CONFIG_BANCAS = {
    "LOTEP": { 
        "display": "LOTEP (Dezenas)", 
        "aba": "BASE_LOTEP_DEZ", 
        "slug": "lotep", 
        "horarios": ["10:45", "12:45", "15:45", "18:00"] 
    },
    "CAMINHO": { 
        "display": "CAMINHO (Dezenas)", 
        "aba": "BASE_CAMINHO_DEZ", 
        "slug": "caminho-da-sorte", 
        "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] 
    },
    "MONTE": { 
        "display": "MONTE CARLOS (Dezenas)", 
        "aba": "BASE_MONTE_DEZ", 
        "slug": "nordeste-monte-carlos", 
        "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] 
    }
}

# Mapeamento: Quais dezenas pertencem a qual grupo?
GRUPOS_BICHOS = {}
for g in range(1, 26):
    fim = g * 4
    inicio = fim - 3
    dezenas = []
    for n in range(inicio, fim + 1):
        if n == 100: dezenas.append("00")
        else: dezenas.append(f"{n:02}")
    GRUPOS_BICHOS[g] = dezenas 

# Mapeamento Inverso: Dezena -> Grupo
DEZENA_PARA_GRUPO = {}
for g, dzs in GRUPOS_BICHOS.items():
    for d in dzs:
        DEZENA_PARA_GRUPO[d] = g

# Estilo Visual (CSS - Tema Centurião + Backtest)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    
    .box-centurion {
        background: linear-gradient(135deg, #5c0000, #2b0000);
        border: 2px solid #ffd700;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 0 25px rgba(255, 215, 0, 0.15);
    }
    
    .titulo-gold { 
        color: #ffd700; 
        font-weight: 900; 
        font-size: 26px; 
        text-transform: uppercase; 
        letter-spacing: 2px; 
        margin-bottom: 5px;
    }
    
    .subtitulo { 
        color: #cccccc; 
        font-size: 14px; 
        margin-bottom: 20px; 
        font-style: italic;
    }
    
    .nums-destaque { 
        font-size: 20px; 
        color: #ffffff; 
        font-weight: bold; 
        word-wrap: break-word; 
        line-height: 1.8;
        letter-spacing: 1px;
    }
    
    .lucro-info { 
        background-color: rgba(0, 255, 0, 0.05); 
        border: 1px solid #00ff00; 
        padding: 10px; 
        border-radius: 8px; 
        color: #00ff00; 
        font-weight: bold; 
        margin-top: 20px;
        font-size: 16px;
    }
    
    .info-pill {
        padding: 5px 15px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 13px;
        display: inline-block;
        margin: 5px;
    }
    .pill-sat { background-color: #330000; color: #ff4b4b; border: 1px solid #ff4b4b; }
    .pill-reforco { background-color: #003300; color: #00ff00; border: 1px solid #00ff00; }
    
    /* BACKTEST ESTILO */
    .backtest-container { display: flex; justify-content: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
    .bt-card { 
        background-color: rgba(30, 30, 30, 0.9); 
        border-radius: 8px; 
        padding: 10px; 
        width: 90px; 
        text-align: center; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
    }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 20px; margin-bottom: 2px; }
    .bt-num { font-size: 14px; font-weight: bold; }
    .bt-label { font-size: 10px; opacity: 0.8; text-transform: uppercase; }

    /* MAX LOSS PILL */
    .max-loss-pill {
        background-color: rgba(255, 0, 0, 0.15);
        border: 1px solid #ff4b4b;
        color: #ffcccc;
        padding: 8px 20px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
        margin-bottom: 15px;
    }

    div[data-testid="stTable"] table { color: white; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (EXTRAÇÃO) ---
# =============================================================================
def conectar_planilha(nome_aba):
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        gc = gspread.authorize(creds)
        sh = gc.open("CentralBichos")
        try: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_historico_dezenas(nome_aba):
    ws = conectar_planilha(nome_aba)
    if ws:
        raw = ws.get_all_values()
        if len(raw) < 2: return []
        dados = []
        for row in raw[1:]:
            if len(row) >= 7:
                dezenas = [str(d).strip().zfill(2) for d in row[2:7] if d.strip().isdigit()]
                if len(dezenas) == 5:
                    dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
        return dados
    return []

def raspar_dezenas_site(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    hoje = date.today()
    delta = (hoje - data_alvo).days
    base = "https://www.resultadofacil.com.br"
    
    if delta == 0: url = f"{base}/resultados-{config['slug']}-de-hoje"
    elif delta == 1: url = f"{base}/resultados-{config['slug']}-de-ontem"
    else: url = f"{base}/resultados-{config['slug']}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"

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
                            dezenas_encontradas = []
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                cols = linha.find_all('td')
                                if len(cols) >= 2:
                                    premio_txt = cols[0].get_text().strip()
                                    numero_txt = cols[1].get_text().strip()
                                    
                                    nums_premio = re.findall(r'\d+', premio_txt)
                                    if nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                        if numero_txt.isdigit() and len(numero_txt) >= 2:
                                            dezena = numero_txt[-2:]
                                            dezenas_encontradas.append(dezena)
                            
                            if len(dezenas_encontradas) >= 5:
                                return dezenas_encontradas[:5], "Sucesso"
                            else: return None, "Incompleto"
        return None, "Horário não encontrado"
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 3. CÉREBRO: LÓGICA DE SATURAÇÃO E TROCA ---
# =============================================================================
def gerar_matriz_75_saturation(historico, indice_premio):
    if not historico:
        padrao = []
        cortadas = []
        for g in range(1, 26):
            dzs = GRUPOS_BICHOS[g]
            padrao.extend(dzs[:3])
            cortadas.append(f"G{g}:{dzs[3]}")
        return padrao, cortadas, None, []

    # 1. Analisa frequência das dezenas (Últimos 30 jogos)
    dezenas_historico = []
    recorte = historico[-30:] 
    for jogo in recorte:
        try: dezenas_historico.append(jogo['dezenas'][indice_premio])
        except: pass
    
    contagem_dezenas = Counter(dezenas_historico)
    
    # 2. Analisa frequência dos GRUPOS (Soma das dezenas)
    contagem_grupos = {}
    for g, dzs in GRUPOS_BICHOS.items():
        soma = 0
        for d in dzs:
            soma += contagem_dezenas.get(d, 0)
        contagem_grupos[g] = soma
        
    # Rankeia Grupos: Mais frequentes (Saturados) -> Menos (Atrasados)
    rank_grupos = sorted(contagem_grupos.items(), key=lambda x: x[1], reverse=True)
    
    # IDENTIFICA O VILÃO (Saturado #1)
    grupo_saturado = rank_grupos[0][0] # O mais frequente
    
    # IDENTIFICA OS HERÓIS (3 Atrasados) - Os últimos da lista
    # Pegamos os 3 últimos
    grupos_reforco = [x[0] for x in rank_grupos[-3:]]
    
    palpite_final = []
    dezenas_cortadas = []
    
    # 3. Processamento Grupo a Grupo
    for grupo, lista_dezenas in GRUPOS_BICHOS.items():
        
        # CASO 1: É O GRUPO SATURADO?
        if grupo == grupo_saturado:
            # Elimina TODAS as dezenas
            dezenas_cortadas.append(f"🔴 G{grupo} (SATURADO): {', '.join(lista_dezenas)}")
            continue # Pula para o próximo, não adiciona nada
            
        # CASO 2: É UM GRUPO DE REFORÇO?
        elif grupo in grupos_reforco:
            # Adiciona TODAS as 4 dezenas
            palpite_final.extend(lista_dezenas)
            # Não corta nenhuma
            continue
            
        # CASO 3: GRUPO NORMAL (21 Grupos)
        else:
            # Regra Padrão: Elimina a pior dezena
            rank_dz = []
            for d in lista_dezenas:
                freq = contagem_dezenas.get(d, 0)
                rank_dz.append((d, freq))
            
            rank_dz.sort(key=lambda x: x[1]) # Menor freq primeiro
            dezena_removida = rank_dz[0][0]
            dezenas_selecionadas = [x[0] for x in rank_dz[1:]] # Pega 3
            
            palpite_final.extend(dezenas_selecionadas)
            dezenas_cortadas.append(f"G{grupo}: {dezena_removida}")
            
    # Ordena para ficar bonito
    palpite_final = sorted(list(set(palpite_final))) # Set remove duplicidade por segurança
    
    return palpite_final, dezenas_cortadas, grupo_saturado, grupos_reforco

def executar_backtest_centurion(historico, indice_premio):
    if len(historico) < 35: return []
    resultados = []
    for i in range(1, 5):
        target_idx = -i
        target_game = historico[target_idx]
        target_dezena = target_game['dezenas'][indice_premio]
        hist_treino = historico[:target_idx]
        
        palpite_ia, _, _, _ = gerar_matriz_75_saturation(hist_treino, indice_premio)
        vitoria = target_dezena in palpite_ia
        resultados.append({'index': i, 'dezena': target_dezena, 'win': vitoria})
    return resultados

def calcular_pior_sequencia_50(historico, indice_premio):
    if len(historico) < 40: return 0
    offset_treino = 30
    total_disponivel = len(historico)
    if total_disponivel <= offset_treino: return 0
    inicio_simulacao = max(offset_treino, total_disponivel - 50)
    max_derrotas = 0
    derrotas_consecutivas = 0
    for i in range(inicio_simulacao, total_disponivel):
        target_game = historico[i]
        target_dezena = target_game['dezenas'][indice_premio]
        hist_treino = historico[:i]
        palpite, _, _, _ = gerar_matriz_75_saturation(hist_treino, indice_premio)
        win = target_dezena in palpite
        if not win: derrotas_consecutivas += 1
        else:
            if derrotas_consecutivas > max_derrotas: max_derrotas = derrotas_consecutivas
            derrotas_consecutivas = 0
    if derrotas_consecutivas > max_derrotas: max_derrotas = derrotas_consecutivas
    return max_derrotas

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
st.title("🛡️ CENTURION 75")
st.markdown("**Estratégia: Rotação de Saturação (75 Dezenas)**")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuração")
    banca_sel = st.selectbox("Escolha a Banca:", list(CONFIG_BANCAS.keys()))
    conf = CONFIG_BANCAS[banca_sel]
    
    url_site_base = f"https://www.resultadofacil.com.br/resultados-{conf['slug']}-de-hoje"
    st.link_button("🔗 Ver Site Oficial", url_site_base)
    st.markdown("---")

    modo_extracao = st.radio("🔧 Modo de Extração:", ["🎯 Unitária (1 Sorteio)", "🌪️ Em Massa (Turbo)"])
    st.markdown("---")

    if modo_extracao == "🎯 Unitária (1 Sorteio)":
        st.subheader("Extração Unitária")
        opt_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
        if opt_data == "Hoje": data_busca = date.today()
        elif opt_data == "Ontem": data_busca = date.today() - timedelta(days=1)
        else: data_busca = st.date_input("Escolha a Data:", date.today())
        
        hora_busca = st.selectbox("Horário:", conf['horarios'])
        
        if st.button("🚀 Baixar Sorteio"):
            ws = conectar_planilha(conf['aba'])
            if ws:
                with st.spinner(f"Buscando {hora_busca}..."):
                    try:
                        existentes = ws.get_all_values()
                        chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
                    except: chaves = []
                    chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{hora_busca}"
                    if chave_atual in chaves:
                        try: idx = chaves.index(chave_atual) + 2
                        except: idx = "?"
                        st.warning(f"⚠️ Resultado já existe na Linha {idx}!")
                    else:
                        dezenas, msg = raspar_dezenas_site(banca_sel, data_busca, hora_busca)
                        if dezenas:
                            ws.append_row([data_busca.strftime('%Y-%m-%d'), hora_busca] + dezenas)
                            st.success(f"✅ Salvo! Dezenas: {dezenas}")
                            time.sleep(1)
                            st.rerun()
                        else: st.error(f"❌ {msg}")
            else: st.error("Erro Conexão Planilha")

    else:
        st.subheader("Extração em Massa")
        col1, col2 = st.columns(2)
        with col1: data_ini = st.date_input("Início:", date.today() - timedelta(days=1))
        with col2: data_fim = st.date_input("Fim:", date.today())
        
        if st.button("🚀 INICIAR TURBO"):
            ws = conectar_planilha(conf['aba'])
            if ws:
                status = st.empty()
                bar = st.progress(0)
                try:
                    existentes = ws.get_all_values()
                    chaves = [f"{str(r[0]).strip()}|{str(r[1]).strip()}" for r in existentes if len(r) > 1]
                except: chaves = []
                
                delta = data_fim - data_ini
                lista_datas = [data_ini + timedelta(days=i) for i in range(delta.days + 1)]
                total_ops = len(lista_datas) * len(conf['horarios'])
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    for hora in conf['horarios']:
                        op_atual += 1
                        bar.progress(op_atual / total_ops)
                        status.text(f"🔍 Buscando: {dia.strftime('%d/%m')} às {hora}...")
                        chave_atual = f"{dia.strftime('%Y-%m-%d')}|{hora}"
                        if chave_atual in chaves: continue
                        if dia > date.today(): continue
                        if dia == date.today() and hora > datetime.now().strftime("%H:%M"): continue

                        dezenas, msg = raspar_dezenas_site(banca_sel, dia, hora)
                        if dezenas:
                            ws.append_row([dia.strftime('%Y-%m-%d'), hora] + dezenas)
                            sucessos += 1
                            chaves.append(chave_atual)
                        time.sleep(1.0)
                bar.progress(100)
                status.success(f"🏁 Concluído! {sucessos} novos sorteios.")
                time.sleep(2)
                st.rerun()
            else: st.error("Erro Conexão Planilha")

# --- TELA PRINCIPAL ---
conf_atual = CONFIG_BANCAS[banca_sel]
st.subheader(f"Analise: {conf_atual['display']}")

historico = carregar_historico_dezenas(conf_atual['aba'])

if len(historico) == 0:
    st.warning("⚠️ Base de dados vazia para esta banca.")
    st.info("👉 Use o menu lateral para baixar os primeiros resultados.")
    st.stop()

tabs = st.tabs(["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"])

for i, tab in enumerate(tabs):
    with tab:
        lista_75, cortadas, sat, reforcos = gerar_matriz_75_saturation(historico, i)
        
        info_sat = f"<span class='info-pill pill-sat'>🚫 GRUPO SATURADO: {sat} (Removido)</span>" if sat else ""
        info_ref = f"<span class='info-pill pill-reforco'>✅ GRUPOS REFORÇADOS: {', '.join(map(str, reforcos))} (Completos)</span>" if reforcos else ""
        
        html_content = f"<div class='box-centurion'>{info_sat} {info_ref}<div class='titulo-gold'>LEGIÃO 75 - {i+1}º PRÊMIO</div><div class='subtitulo'>Estratégia: Eliminar Grupo Saturado + Reforçar Atrasados</div><div class='nums-destaque'>{', '.join(lista_75)}</div><div class='lucro-info'>💰 Custo: R$ 75,00 | Retorno: R$ 92,00 | Lucro: R$ 17,00 (22%)</div></div>"
        
        st.markdown(html_content, unsafe_allow_html=True)
        
        max_loss = calcular_pior_sequencia_50(historico, i)
        st.markdown(f"<div style='text-align: center;'><span class='max-loss-pill'>📉 Pior Sequência (50 Jogos): {max_loss} Derrotas</span></div>", unsafe_allow_html=True)

        bt_results = executar_backtest_centurion(historico, i)
        
        if bt_results:
            st.markdown("### ⏪ Performance Recente")
            cards_html = ""
            for res in reversed(bt_results):
                c_res = "bt-win" if res['win'] else "bt-loss"
                ico = "🟢" if res['win'] else "🔴"
                lbl = "WIN" if res['win'] else "LOSS"
                num = res['dezena']
                cards_html += f"<div class='bt-card {c_res}'><div class='bt-icon'>{ico}</div><div class='bt-num'>{num}</div><div class='bt-label'>{lbl}</div></div>"
            
            st.markdown(f"<div class='backtest-container'>{cards_html}</div>", unsafe_allow_html=True)
        
        else:
            st.caption("ℹ️ Baixe mais resultados (mínimo 40) para ver o Backtest e Risco.")

        st.markdown("---")
        with st.expander("✂️ Ver Dezenas Eliminadas (Detalhes)"):
            st.write(", ".join(cortadas))
