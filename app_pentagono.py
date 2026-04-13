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
st.set_page_config(page_title="PENTÁGONO V145.0 - Seca Absoluta", page_icon="🎯", layout="wide")

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
    if 1 <= grupo <= 24: return f"{(grupo*4)-3:02d}, {(grupo*4)-2:02d}, {(grupo*4)-1:02d}, {grupo*4:02d}"
    return ""

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fff; }
    div[data-testid="stTable"] table { color: white; }
    .stMetric label { color: #aaaaaa !important; }
    h1, h2, h3 { color: #ffd700 !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .card-ranking { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #ff4b4b; }
    .card-seca { background-color: #001a33; border: 1px solid #0055ff; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #00aaff; }
    .card-alvo { background-color: #1a0000; border: 2px solid #ff0000; border-radius: 8px; padding: 20px; text-align: center; }
    .card-recorde { background-color: #1a1a00; border: 1px solid #cca300; border-radius: 8px; padding: 10px; margin-bottom: 10px; border-left: 5px solid #ffcc00; }
</style>
""", unsafe_allow_html=True)

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
                    
                    dados_unicos[chave] = { "data": data_str, "horario": h_clean, "premios": premios }
            lista_final = list(dados_unicos.values())
            lista_final.sort(key=lambda x: f"{x['data']} {x['horario']}")
            return lista_final
        except: return [] 
    return []

def normalizar_data(data_str):
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]
    for fmt in formatos:
        try: return datetime.strptime(str(data_str).strip(), fmt).date()
        except: continue
    return None

def normalizar_hora(hora_str):
    h_clean = re.sub(r'[a-zA-Z]', '', str(hora_str).strip())
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
    except: return 0

def raspar_dados_hibrido(banca_key, data_alvo, horario_alvo):
    config = CONFIG_BANCAS[banca_key]
    slug = config['slug']
    url = f"https://playbicho.com/resultado-jogo-do-bicho/{slug}-do-dia-{data_alvo.strftime('%Y-%m-%d')}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        for _ in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200: break
            except: time.sleep(1)
        if r.status_code == 404 and data_alvo == date.today():
            r = requests.get(f"https://playbicho.com/resultado-jogo-do-bicho/{slug}", headers=headers, timeout=10)
        if r.status_code != 200: return None, f"Erro {r.status_code}."
            
        soup = BeautifulSoup(r.text, 'html.parser')
        try: target_h, target_m = map(int, horario_alvo.split(':'))
        except: return None, "Formato de hora inválido."
        
        for tabela in soup.find_all('table'):
            txt_tabela = tabela.get_text().lower()
            if "federal" in txt_tabela and "federal" not in banca_key.lower(): continue 
            
            texto_analise = txt_tabela + " "
            if tabela.find_previous(['h2', 'h3']): texto_analise += tabela.find_previous(['h2', 'h3']).get_text().lower() + " "
                
            times_parsed = []
            for h, m in re.findall(r'(?<!\d)(\d{1,2})[:hH]s?(\d{2})(?!\d)', texto_analise): times_parsed.append((int(h), int(m)))
            for h in re.findall(r'(?<!\d)(\d{1,2})\s?[hH]s?(?!\w)', texto_analise): times_parsed.append((int(h), 0))
            
            match_found = False
            target_total_mins = target_h * 60 + target_m
            for h, m in times_parsed:
                if abs((h * 60 + m) - target_total_mins) <= 30: match_found = True; break
            
            if match_found:
                dezenas_encontradas = []
                for linha in tabela.find_all('tr'):
                    cols = linha.find_all('td')
                    if len(cols) >= 2:
                        nums_premio = re.findall(r'\d+', cols[0].get_text())
                        if nums_premio and 1 <= int(nums_premio[0]) <= 5:
                            clean_num = re.sub(r'\D', '', cols[1].get_text().strip())
                            if len(clean_num) >= 2: dezenas_encontradas.append(clean_num[-4:].zfill(4))
                if len(dezenas_encontradas) >= 1: return dezenas_encontradas + ["0000"]*(5-len(dezenas_encontradas)), "Sucesso"
        return None, "Horário não encontrado."
    except Exception as e: return None, f"Erro: {e}"

# =============================================================================
# --- 4. CÉREBRO MATEMÁTICO: ISOLADO E 1º AO 5º ---
# =============================================================================

@st.cache_data(show_spinner=False)
def analisar_atraso_grupos_isolado(history_slice):
    if len(history_slice) < 20: return None, None
    stats = { p_idx: {g: {'atraso': 0, 'max_atraso': 0, 'soma_ciclos': 0, 'qtd_ciclos': 0} for g in range(1, 26)} for p_idx in range(5) }

    for draw in history_slice:
        for p_idx in range(5):
            grupo_sorteado = get_grupo(draw['premios'][p_idx])
            for g in range(1, 26):
                if g == grupo_sorteado:
                    if stats[p_idx][g]['atraso'] > stats[p_idx][g]['max_atraso']:
                        stats[p_idx][g]['max_atraso'] = stats[p_idx][g]['atraso']
                    stats[p_idx][g]['soma_ciclos'] += stats[p_idx][g]['atraso']
                    stats[p_idx][g]['qtd_ciclos'] += 1
                    stats[p_idx][g]['atraso'] = 0
                else:
                    stats[p_idx][g]['atraso'] += 1

    for p_idx in range(5):
        for g in range(1, 26):
            if stats[p_idx][g]['atraso'] > stats[p_idx][g]['max_atraso']: stats[p_idx][g]['max_atraso'] = stats[p_idx][g]['atraso']

    todos_grupos = []
    for p_idx in range(5):
        for g in range(1, 26):
            a_atual = stats[p_idx][g]['atraso']
            media = (stats[p_idx][g]['soma_ciclos'] / stats[p_idx][g]['qtd_ciclos']) if stats[p_idx][g]['qtd_ciclos'] > 0 else 25.0
            todos_grupos.append({
                "premio": p_idx + 1, "grupo": g, "nome_grupo": NOME_GRUPOS[g],
                "atraso": a_atual, "max_atraso": stats[p_idx][g]['max_atraso'], "media": media
            })

    alvos_ativos = [g for g in todos_grupos if g['atraso'] >= 75]
    alvos_ativos.sort(key=lambda x: x['atraso'], reverse=True)
    recordes = sorted(todos_grupos, key=lambda x: x['max_atraso'], reverse=True)
    return alvos_ativos, recordes[:5]

@st.cache_data(show_spinner=False)
def analisar_atraso_1_ao_5(history_slice):
    if len(history_slice) < 5: return []
    stats = {g: {'atraso': 0, 'max_atraso': 0, 'soma_ciclos': 0, 'qtd_ciclos': 0} for g in range(1, 26)}
    
    for draw in history_slice:
        grupos_sorteio = set()
        for p_idx in range(5):
            try:
                g = get_grupo(draw['premios'][p_idx])
                if g > 0: grupos_sorteio.add(g)
            except: pass
            
        for g in range(1, 26):
            if g in grupos_sorteio:
                if stats[g]['atraso'] > stats[g]['max_atraso']: stats[g]['max_atraso'] = stats[g]['atraso']
                stats[g]['soma_ciclos'] += stats[g]['atraso']
                stats[g]['qtd_ciclos'] += 1
                stats[g]['atraso'] = 0
            else:
                stats[g]['atraso'] += 1
                
    for g in range(1, 26):
        if stats[g]['atraso'] > stats[g]['max_atraso']: stats[g]['max_atraso'] = stats[g]['atraso']
            
    resultado = []
    for g in range(1, 26):
        media = (stats[g]['soma_ciclos'] / stats[g]['qtd_ciclos']) if stats[g]['qtd_ciclos'] > 0 else 5.0
        resultado.append({
            "grupo": g, "nome_grupo": NOME_GRUPOS[g],
            "atraso": stats[g]['atraso'], "max_atraso": stats[g]['max_atraso'], "media": media
        })
        
    resultado.sort(key=lambda x: x['atraso'], reverse=True)
    return resultado

if "menu_nav" not in st.session_state: st.session_state.menu_nav = "🏠 ALVOS DE CAÇADA (Grupos)"
escolha_menu = st.sidebar.selectbox("Navegação Principal", ["🏠 ALVOS DE CAÇADA (Grupos)"] + list(CONFIG_BANCAS.keys()), key="menu_nav")
st.sidebar.markdown("---")

if escolha_menu == "🏠 ALVOS DE CAÇADA (Grupos)":
    st.title("🎯 COMANDO CENTRAL (Perseguição de Grupos)")
    
    aba_seca, aba_sniper, aba_recordes = st.tabs(["🌪️ SECA ABSOLUTA (1º ao 5º - 4x1)", "🎯 TIRO DE SNIPER (Isolado - 23x1)", "🏆 RECORDES (Isolado)"])
    
    ranking_isolado = []
    ranking_seca = []
    recordes_globais = []
    
    with st.spinner("📡 Rastreiando 1º ao 5º e Prêmios Isolados simultaneamente..."):
        for banca_key, config in CONFIG_BANCAS.items():
            if config.get('radar_ativo') == True:
                historico = carregar_dados_hibridos(config['nome_aba'])
                if len(historico) >= 20:
                    # Análise Isolada
                    alvos_isolados, rec_banca = analisar_atraso_grupos_isolado(historico)
                    if alvos_isolados:
                        for alvo in alvos_isolados[:2]:
                            alvo['banca'] = config['display_name'].replace("🎯 ", "")
                            ranking_isolado.append(alvo)
                    if rec_banca:
                        for rec in rec_banca:
                            rec['banca'] = config['display_name'].replace("🎯 ", "")
                            recordes_globais.append(rec)
                            
                    # Análise Seca Absoluta 1 ao 5
                    alvos_seca = analisar_atraso_1_ao_5(historico)
                    if alvos_seca:
                        # Filtro da seca: Ponto de fervura 1 ao 5 é > 18 sorteios (Média natural é ~5)
                        top_seca = [s for s in alvos_seca if s['atraso'] >= 18]
                        for s in top_seca[:2]:
                            s['banca'] = config['display_name'].replace("🎯 ", "")
                            ranking_seca.append(s)

    # --- ABA SECA ABSOLUTA (1 AO 5) ---
    with aba_seca:
        st.markdown("O sistema vasculha o placar inteiro. Mostra grupos que não aparecem em **nenhum dos 5 prêmios**. O ciclo normal é sair a cada ~5 sorteios. Entramos apenas quando o atraso bate o triplo (Fervura: > 18 atrasos).")
        if not ranking_seca: st.success("✅ Nenhum alvo no Ponto de Fervura 1 ao 5 no momento.")
        else:
            ranking_seca.sort(key=lambda x: x['atraso'], reverse=True)
            html_seca = ""
            for idx, alvo in enumerate(ranking_seca[:5]):
                dez_str = get_dezenas_grupo(alvo['grupo'])
                html_seca += (
                    f'<div class="card-seca">'
                    f'<h3 style="margin:0 0 10px 0; color:#00aaff;">#{idx+1} | BANCA: {alvo["banca"]} | 1º AO 5º PRÊMIO</h3>'
                    f'<div style="background-color:#000d1a; padding:15px; border-radius:5px; text-align:center;">'
                    f'  <h2 style="margin:0; color:#fff;">GRUPO {alvo["grupo"]} ({alvo["nome_grupo"]})</h2>'
                    f'  <p style="margin:5px 0 0 0; color:#00aaff; font-size:1.1em;">Dezenas: <b>{dez_str}</b></p>'
                    f'</div>'
                    f'<div style="margin-top:10px; display:flex; justify-content:space-around; font-size:1.0em; color:#ddd;">'
                    f'  <span style="color:#ffaa00;">⏳ Seca Atual: {alvo["atraso"]} sorteios </span>'
                    f'  <span style="color:#00ff00;">📊 Média: {alvo["media"]:.1f} sorteios </span>'
                    f'  <span>🛑 Teto da Banca: {alvo["max_atraso"]} sorteios </span>'
                    f'</div></div>'
                )
            st.markdown(html_seca, unsafe_allow_html=True)

    # --- ABA TIRO DE SNIPER (ISOLADO) ---
    with aba_sniper:
        st.markdown("Busca grupos atrasados em **prêmios específicos** (Pagamento maior: 23x1). Zona de Fervura calibrada para **> 75 sorteios**.")
        if not ranking_isolado: st.success("✅ Nenhum alvo isolado no Ponto de Fervura no momento.")
        else:
            ranking_isolado.sort(key=lambda x: x['atraso'], reverse=True)
            html_isolado = ""
            for idx, alvo in enumerate(ranking_isolado[:5]):
                dez_str = get_dezenas_grupo(alvo['grupo'])
                html_isolado += (
                    f'<div class="card-ranking">'
                    f'<h3 style="margin:0 0 10px 0; color:#fff;">#{idx+1} | BANCA: {alvo["banca"]} | {alvo["premio"]}º PRÊMIO</h3>'
                    f'<div class="card-alvo">'
                    f'  <h1 style="margin:0; color:#ff3333; font-size:2.5em;">GRUPO {alvo["grupo"]} ({alvo["nome_grupo"]})</h1>'
                    f'  <p style="margin:5px 0 0 0; color:#ffcc00; font-size:1.1em;">Dezenas: <b>{dez_str}</b></p>'
                    f'</div>'
                    f'<div style="margin-top:15px; display:flex; justify-content:space-around; font-size:1.1em; color:#ddd; background:#222; padding:10px; border-radius:5px;">'
                    f'  <span style="color:#ffaa00;"><b>⏳ Atraso:</b> {alvo["atraso"]} </span>'
                    f'  <span style="color:#00ff00;"><b>📊 Média:</b> {alvo["media"]:.0f} </span>'
                    f'  <span><b>🛑 Teto Banca:</b> {alvo["max_atraso"]} </span>'
                    f'</div></div>'
                )
            st.markdown(html_isolado, unsafe_allow_html=True)
            
    # --- ABA RECORDES ---
    with aba_recordes:
        if recordes_globais:
            recordes_globais.sort(key=lambda x: x['max_atraso'], reverse=True)
            html_recordes = ""
            for idx, rec in enumerate(recordes_globais[:5]):
                html_recordes += f'<div class="card-recorde"><span style="font-size:1.2em; font-weight:bold; color:#ffd700;">#{idx+1} - {rec["max_atraso"]} Sorteios Seguidos</span><br><span style="color:#ccc;">Aconteceu na <b>{rec["banca"]}</b>, no <b>{rec["premio"]}º Prêmio</b>. O alvo foi o <b>Grupo {rec["grupo"]} ({rec["nome_grupo"]})</b>.</span></div>'
            st.markdown(html_recordes, unsafe_allow_html=True)
        
else:
    banca_selecionada = escolha_menu
    config = CONFIG_BANCAS[banca_selecionada]
    
    st.sidebar.markdown(f"<a href='https://playbicho.com/resultado-jogo-do-bicho/{config['slug']}-do-dia-{date.today().strftime('%Y-%m-%d')}' target='_blank'><button style='width: 100%; border-radius: 5px; font-weight: bold; background-color: #007bff; color: white; padding: 8px 10px; border: none; cursor: pointer; margin-bottom: 10px;'>🌐 Visitar Site da Banca</button></a>", unsafe_allow_html=True)
    modo_extracao = st.sidebar.radio("🔧 Modo de Extração:", ["🎯 Unitária", "✍️ Manual"])
    
    if modo_extracao == "🎯 Unitária":
        with st.sidebar.expander("📥 Importar Resultado", expanded=True):
            data_busca = st.date_input("Data:", date.today(), key=f"dt_pk_{banca_selecionada}")
            horario_busca = st.selectbox("Horário:", config['horarios'].copy(), key=f"sel_hr_{banca_selecionada}")
            if st.button("🚀 Baixar & Salvar", key=f"btn_b_stb_{banca_selecionada}"):
                ws_milhar = conectar_planilha(config['nome_aba'])
                if ws_milhar:
                    with st.spinner(f"Buscando..."):
                        chaves = [f"{normalizar_data(r[0]).strftime('%Y-%m-%d')}|{normalizar_hora(r[1])}" for r in ws_milhar.get_all_values() if len(r) >= 2 and normalizar_data(r[0])]
                        if f"{data_busca.strftime('%Y-%m-%d')}|{normalizar_hora(horario_busca)}" in chaves: st.warning("Já existe!")
                        else:
                            premios, msg = raspar_dados_hibrido(banca_selecionada, data_busca, horario_busca)
                            if premios:
                                ws_milhar.append_row([data_busca.strftime('%Y-%m-%d'), horario_busca] + premios)
                                st.cache_data.clear(); st.rerun()
                            else: st.error(msg)

    elif modo_extracao == "✍️ Manual":
        with st.sidebar.expander("📝 Lançar Manualmente", expanded=True):
            data_busca_man = st.date_input("Data:", date.today(), key=f"dt_man_{banca_selecionada}")
            horario_busca_man = st.selectbox("Horário:", config['horarios'].copy(), key=f"hr_man_{banca_selecionada}")
            p1 = st.text_input("1º Prêmio", max_chars=4, key="m_p1"); p2 = st.text_input("2º", max_chars=4, key="m_p2"); p3 = st.text_input("3º", max_chars=4, key="m_p3"); p4 = st.text_input("4º", max_chars=4, key="m_p4"); p5 = st.text_input("5º", max_chars=4, key="m_p5")
            if st.button("💾 Salvar Resultado", use_container_width=True):
                premios_finais = [(re.sub(r'\D', '', p) or "0000").zfill(4) for p in [p1, p2, p3, p4, p5]]
                ws_milhar = conectar_planilha(config['nome_aba'])
                if ws_milhar:
                    ws_milhar.append_row([data_busca_man.strftime('%Y-%m-%d'), horario_busca_man] + premios_finais)
                    st.cache_data.clear(); st.rerun()

    st.header(f"{config['display_name']} - Status")
    with st.spinner("Analisando..."): historico = carregar_dados_hibridos(config['nome_aba'])
    if len(historico) > 0:
        st.success(f"📅 **Último Sorteio:** {historico[-1]['data']} às {historico[-1]['horario']}")
        
        alvos_seca = analisar_atraso_1_ao_5(historico)
        top_seca_local = [s for s in alvos_seca if s['atraso'] >= 18]
        if top_seca_local:
            st.markdown("### 🌪️ ALVOS EM SECA ABSOLUTA NESTA BANCA (1º ao 5º)")
            for alvo in top_seca_local[:3]:
                st.markdown(f"<div style='background-color:#001a33; border-left: 4px solid #0055ff; padding: 15px; margin-bottom: 10px;'><span style='color:#00aaff; font-size:1.2em;'><b>1º AO 5º PRÊMIO</b> ➔ <b>Grupo {alvo['grupo']} ({alvo['nome_grupo']})</b></span><br><span style='color:#ffcc00;'>Dezenas: <b>{get_dezenas_grupo(alvo['grupo'])}</b></span><br><span style='color:#aaa;'>⏳ Seca: {alvo['atraso']} | 📊 Média: {alvo['media']:.1f} | 🛑 Teto: {alvo['max_atraso']}</span></div>", unsafe_allow_html=True)
                
        alvos_locais, _ = analisar_atraso_grupos_isolado(historico)
        if alvos_locais:
            st.markdown("### 🚨 ALVOS ISOLADOS NESTA BANCA (>75 Atrasos)")
            for alvo in alvos_locais:
                st.markdown(f"<div style='background-color:#4a0000; border-left: 4px solid #ff0000; padding: 15px; margin-bottom: 10px;'><span style='color:#fff; font-size:1.2em;'><b>{alvo['premio']}º PRÊMIO</b> ➔ <b>Grupo {alvo['grupo']} ({alvo['nome_grupo']})</b></span><br><span style='color:#ffcc00;'>Dezenas: <b>{get_dezenas_grupo(alvo['grupo'])}</b></span><br><span style='color:#aaa;'>⏳ Atraso: {alvo['atraso']} | 📊 Média: {alvo['media']:.0f} | 🛑 Teto: {alvo['max_atraso']}</span></div>", unsafe_allow_html=True)

        st.dataframe(pd.DataFrame(historico).tail(15), use_container_width=True)
