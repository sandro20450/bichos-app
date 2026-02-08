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
st.set_page_config(page_title="CENTURION 75 - V7.4 Scanner", page_icon="🛡️", layout="wide")

# Configuração das Bancas
CONFIG_BANCAS = {
    "LOTEP": { "display": "LOTEP (Dezenas)", "aba": "BASE_LOTEP_DEZ", "slug": "lotep", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHO": { "display": "CAMINHO (Dezenas)", "aba": "BASE_CAMINHO_DEZ", "slug": "caminho-da-sorte", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "MONTE": { "display": "MONTE CARLOS (Dezenas)", "aba": "BASE_MONTE_DEZ", "slug": "nordeste-monte-carlos", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] }
}

# Mapeamento Grupos
GRUPOS_BICHOS = {}
for g in range(1, 26):
    fim = g * 4; inicio = fim - 3
    dezenas = [("00" if n == 100 else f"{n:02}") for n in range(inicio, fim + 1)]
    GRUPOS_BICHOS[g] = dezenas 

# Estilo Visual
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    .box-centurion {
        background: linear-gradient(135deg, #5c0000, #2b0000);
        border: 2px solid #ffd700; padding: 20px; border-radius: 12px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 0 25px rgba(255, 215, 0, 0.15);
    }
    .box-alert {
        background-color: #4a0000; border: 2px solid #ff0000;
        padding: 15px; border-radius: 10px; text-align: center;
        margin: 15px 0; animation: pulse 2s infinite; font-size: 18px; font-weight: bold;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
    }
    .titulo-gold { color: #ffd700; font-weight: 900; font-size: 26px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }
    .subtitulo { color: #cccccc; font-size: 14px; margin-bottom: 20px; font-style: italic; }
    .nums-destaque { font-size: 20px; color: #ffffff; font-weight: bold; word-wrap: break-word; line-height: 1.8; letter-spacing: 1px; }
    .lucro-info { background-color: rgba(0, 255, 0, 0.05); border: 1px solid #00ff00; padding: 10px; border-radius: 8px; color: #00ff00; font-weight: bold; margin-top: 20px; font-size: 16px; }
    .info-pill { padding: 5px 15px; border-radius: 5px; font-weight: bold; font-size: 13px; display: inline-block; margin: 5px; }
    .pill-sat { background-color: #330000; color: #ff4b4b; border: 1px solid #ff4b4b; }
    .pill-ref { background-color: #003300; color: #00ff00; border: 1px solid #00ff00; }
    .pill-final { background-color: #4a004a; color: #ff00ff; border: 1px solid #ff00ff; }
    .backtest-container { display: flex; justify-content: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
    .bt-card { background-color: rgba(30, 30, 30, 0.9); border-radius: 8px; padding: 10px; width: 90px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
    .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
    .bt-icon { font-size: 20px; margin-bottom: 2px; }
    .bt-num { font-size: 14px; font-weight: bold; }
    .bt-label { font-size: 10px; opacity: 0.8; text-transform: uppercase; }
    .max-loss-pill { background-color: rgba(255, 0, 0, 0.15); border: 1px solid #ff4b4b; color: #ffcccc; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 15px; }
    div[data-testid="stTable"] table { color: white; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E RASPAGEM (Scanner V7.4) ---
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
                if len(dezenas) == 5: dados.append({"data": row[0], "hora": row[1], "dezenas": dezenas})
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
        
        # --- LÓGICA DE SCANNER V7.4 (Busca Exata no Texto) ---
        for tabela in tabelas:
            if "Prêmio" in tabela.get_text() or "1º" in tabela.get_text():
                # Encontra o texto imediatamente anterior à tabela (o cabeçalho)
                prev_element = tabela.find_previous(string=True)
                
                # Se o elemento anterior for vazio, tenta subir mais um pouco
                if not prev_element or not prev_element.strip():
                    prev_element = tabela.find_previous('div', class_='title')
                    if prev_element: text_header = prev_element.get_text()
                    else: text_header = ""
                else:
                    # Tenta pegar o texto do container pai se for string solta
                    if prev_element.parent: text_header = prev_element.parent.get_text()
                    else: text_header = prev_element
                
                text_header_upper = text_header.upper()
                
                # 1. Filtro Federal
                if "RESULTADO DO DIA" in text_header_upper and "FEDERAL" in text_header_upper:
                    continue 

                # 2. Verifica se o horário alvo está CONTIDO no cabeçalho
                # Ex: horario_alvo="19:30" e header="Caminho... 19:30..." -> MATCH!
                if horario_alvo in text_header:
                    dezenas_encontradas = []
                    linhas = tabela.find_all('tr')
                    for linha in linhas:
                        cols = linha.find_all('td')
                        if len(cols) >= 2:
                            premio_txt = cols[0].get_text().strip(); numero_txt = cols[1].get_text().strip()
                            nums_premio = re.findall(r'\d+', premio_txt)
                            if nums_premio and 1 <= int(nums_premio[0]) <= 5:
                                if numero_txt.isdigit() and len(numero_txt) >= 2:
                                    dezena = numero_txt[-2:]
                                    dezenas_encontradas.append(dezena)
                    if len(dezenas_encontradas) >= 5: return dezenas_encontradas[:5], "Sucesso"
                    
        return None, f"Horário {horario_alvo} não encontrado na página."
    except Exception as e: return None, f"Erro Técnico: {e}"

# =============================================================================
# --- 3. CÉREBRO: LÓGICA V7.3 + STRESS CALCULATOR ---
# =============================================================================
def gerar_matriz_hibrida(historico, indice_premio):
    if not historico:
        padrao = []
        for g in range(1, 26): padrao.extend(GRUPOS_BICHOS[g][:3])
        return padrao, [], None, [], None

    ultimo_jogo = historico[-1]
    ultima_dezena = ultimo_jogo['dezenas'][indice_premio]
    final_bloqueado = ultima_dezena[-1] 

    tamanho_analise = 50
    if len(historico) < 50: tamanho_analise = len(historico)
    recorte = historico[-tamanho_analise:]
    dezenas_historico = []
    for jogo in recorte:
        try: dezenas_historico.append(jogo['dezenas'][indice_premio])
        except: pass
    contagem_dezenas = Counter(dezenas_historico)

    contagem_grupos = {}
    for g, dzs in GRUPOS_BICHOS.items():
        soma = 0
        for d in dzs: soma += contagem_dezenas.get(d, 0)
        contagem_grupos[g] = soma
        
    rank_grupos = sorted(contagem_grupos.items(), key=lambda x: x[1], reverse=True)
    grupo_saturado = rank_grupos[0][0]; freq_saturado = rank_grupos[0][1]
    grupos_reforco = [x[0] for x in rank_grupos[-3:]]

    palpite_inicial = []
    reservas_disponiveis = []
    dezenas_cortadas_log = []

    for grupo, lista_dezenas in GRUPOS_BICHOS.items():
        if grupo == grupo_saturado:
            for d in lista_dezenas: reservas_disponiveis.append(d)
            dezenas_cortadas_log.append(f"G{grupo} (Saturado)")
            continue 
        elif grupo in grupos_reforco:
            palpite_inicial.extend(lista_dezenas)
            continue
        else:
            rank_dz = []
            for d in lista_dezenas:
                freq = contagem_dezenas.get(d, 0)
                rank_dz.append((d, freq))
            rank_dz.sort(key=lambda x: x[1])
            dezena_removida = rank_dz[0][0]
            dezenas_vencedoras = [x[0] for x in rank_dz[1:]]
            palpite_inicial.extend(dezenas_vencedoras)
            reservas_disponiveis.append(dezena_removida)

    palpite_filtrado = []
    for d in palpite_inicial:
        if not d.endswith(final_bloqueado): palpite_filtrado.append(d)
    
    vagas_abertas = 75 - len(palpite_filtrado)
    reservas_validas = [d for d in reservas_disponiveis if not d.endswith(final_bloqueado)]
    reservas_rank = []
    for d in reservas_validas: reservas_rank.append((d, contagem_dezenas.get(d, 0)))
    reservas_rank.sort(key=lambda x: x[1], reverse=True)
    
    for i in range(min(vagas_abertas, len(reservas_rank))):
        palpite_filtrado.append(reservas_rank[i][0])
        
    palpite_final = sorted(list(set(palpite_filtrado)))
    dados_sat = (grupo_saturado, freq_saturado, tamanho_analise)
    return palpite_final, dezenas_cortadas_log, dados_sat, grupos_reforco, final_bloqueado

def calcular_stress_atual(historico, indice_premio):
    if len(historico) < 10: return 0, 0
    
    offset_treino = 50
    total_disponivel = len(historico)
    inicio_simulacao = max(offset_treino, total_disponivel - 50)
    max_derrotas = 0; derrotas_consecutivas = 0
    
    for i in range(inicio_simulacao, total_disponivel):
        target_game = historico[i]
        target_dezena = target_game['dezenas'][indice_premio]
        hist_treino = historico[:i]
        palpite, _, _, _, _ = gerar_matriz_hibrida(hist_treino, indice_premio)
        win = target_dezena in palpite
        if not win: derrotas_consecutivas += 1
        else:
            if derrotas_consecutivas > max_derrotas: max_derrotas = derrotas_consecutivas
            derrotas_consecutivas = 0
    if derrotas_consecutivas > max_derrotas: max_derrotas = derrotas_consecutivas
    
    stress_atual = 0
    for i in range(1, 20): 
        idx = -i
        target_game = historico[idx]
        target_dezena = target_game['dezenas'][indice_premio]
        hist_treino = historico[:idx] 
        palpite, _, _, _, _ = gerar_matriz_hibrida(hist_treino, indice_premio)
        win = target_dezena in palpite
        if not win: stress_atual += 1
        else: break
        
    return stress_atual, max_derrotas

def executar_backtest_centurion(historico, indice_premio):
    if len(historico) < 60: return []
    resultados = []
    for i in range(1, 5):
        target_idx = -i
        target_game = historico[target_idx]
        target_dezena = target_game['dezenas'][indice_premio]
        hist_treino = historico[:target_idx]
        palpite, _, _, _, _ = gerar_matriz_hibrida(hist_treino, indice_premio)
        vitoria = target_dezena in palpite
        resultados.append({'index': i, 'dezena': target_dezena, 'win': vitoria})
    return resultados

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
st.title("🛡️ CENTURION 75")
st.markdown("**Estratégia Híbrida: Saturação + Final Killer + Reposição (75 Dezenas)**")

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

    # === MODO 1: UNITÁRIO ===
    if modo_extracao == "🎯 Unitária (1 Sorteio)":
        st.subheader("Extração Unitária")
        opt_data = st.radio("Data:", ["Hoje", "Ontem", "Outra"])
        if opt_data == "Hoje": data_busca = date.today()
        elif opt_data == "Ontem": data_busca = date.today() - timedelta(days=1)
        else: data_busca = st.date_input("Escolha a Data:", date.today())
        
        # --- AJUSTE DE HORÁRIO CAMINHO (QUA e SAB) ---
        lista_horarios = conf['horarios'].copy()
        
        # Verifica se é Caminho da Sorte E se é Quarta (2) ou Sábado (5)
        if banca_sel == "CAMINHO" and (data_busca.weekday() == 2 or data_busca.weekday() == 5):
            # Substituição FORÇADA da lista para garantir 19:30
            lista_horarios = [
                "09:40", "11:00", "12:40", "14:00", "15:40", 
                "17:00", "18:30", "19:30", "21:00"
            ]
        # -----------------------------------------------

        hora_busca = st.selectbox("Horário:", lista_horarios)
        
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

    # === MODO 2: EM MASSA ===
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
                
                # Calcula total aproximado para a barra
                total_ops = len(lista_datas) * 8 # Estimativa
                op_atual = 0; sucessos = 0
                
                for dia in lista_datas:
                    # --- LÓGICA DE HORÁRIO TURBO ---
                    horarios_do_dia = conf['horarios'].copy()
                    if banca_sel == "CAMINHO" and (dia.weekday() == 2 or dia.weekday() == 5):
                        horarios_do_dia = [
                            "09:40", "11:00", "12:40", "14:00", "15:40", 
                            "17:00", "18:30", "19:30", "21:00"
                        ]
                    # -------------------------------

                    for hora in horarios_do_dia:
                        op_atual += 1
                        if op_atual <= total_ops: bar.progress(op_atual / total_ops)
                        
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
else:
    # --- MONITOR DE ÚLTIMA ATUALIZAÇÃO ---
    ult = historico[-1]
    st.info(f"📅 **STATUS ATUAL:** O último sorteio registrado nesta banca foi em **{ult['data']}** às **{ult['hora']}**.")

tabs = st.tabs(["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"])

for i, tab in enumerate(tabs):
    with tab:
        lista_final, cortadas, sat, reforcos, final_bloq = gerar_matriz_hibrida(historico, i)
        
        stress_atual, max_loss = calcular_stress_atual(historico, i)
        
        aviso_alerta = ""
        if stress_atual >= max_loss and max_loss > 0:
            aviso_alerta = f"<div class='box-alert'>🚨 <b>ALERTA MÁXIMO:</b> {stress_atual} Derrotas Seguidas (Recorde Atingido!)</div>"
        
        info_sat = f"<span class='info-pill pill-sat'>🚫 GRUPO SATURADO: {sat[0]} ({sat[1]}x)</span>" if sat else ""
        info_ref = f"<span class='info-pill pill-ref'>✅ REFORÇOS: {', '.join(map(str, reforcos))}</span>" if reforcos else ""
        info_final = f"<span class='info-pill pill-final'>🛑 FINAL BLOQUEADO: {final_bloq}</span>" if final_bloq else ""
        
        qtd_final = len(lista_final) 
        
        html_content = f"""
        {aviso_alerta}
        <div class='box-centurion'>
            {info_sat} {info_ref} {info_final}
            <div class='titulo-gold'>LEGIÃO {qtd_final} - {i+1}º PRÊMIO</div>
            <div class='subtitulo'>Estratégia Completa: Saturação + Final Killer + Reposição</div>
            <div class='nums-destaque'>{', '.join(lista_final)}</div>
            <div class='lucro-info'>💰 Custo: R$ {qtd_final},00 | Retorno: R$ 92,00 | Lucro: R$ {92 - qtd_final},00</div>
        </div>
        """
        st.markdown(html_content, unsafe_allow_html=True)
        
        cor_stress = "#ff4b4b" if stress_atual >= max_loss else "#00ff00"
        st.markdown(f"<div style='text-align: center; margin-bottom:10px;'><span class='max-loss-pill'>📉 Recorde Histórico (50 Jogos): {max_loss} | <b>Atual: <span style='color:{cor_stress}'>{stress_atual}</span></b></span></div>", unsafe_allow_html=True)

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
            st.caption("ℹ️ Baixe mais resultados (mínimo 60) para ver o Backtest e Risco.")

        st.markdown("---")
        with st.expander("✂️ Ver Detalhes (Grupos e Cortes)"):
            st.write(f"Grupos Cortados na Saturação: {', '.join(cortadas)}")
