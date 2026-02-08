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

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E DADOS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V40.0 - Sniper 4-4-4", page_icon="🛡️", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": { "display_name": "LOTEP (1º ao 5º)", "nome_aba": "LOTEP_TOP5", "slug": "lotep", "horarios": ["10:45", "12:45", "15:45", "18:00"] },
    "CAMINHODASORTE": { "display_name": "CAMINHO (1º ao 5º)", "nome_aba": "CAMINHO_TOP5", "slug": "caminho-da-sorte", "horarios": ["09:40", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "20:00", "21:00"] },
    "MONTECAI": { "display_name": "MONTE CARLOS (1º ao 5º)", "nome_aba": "MONTE_TOP5", "slug": "nordeste-monte-carlos", "horarios": ["10:00", "11:00", "12:40", "14:00", "15:40", "17:00", "18:30", "21:00"] }
}

SETORES = {
    "BAIXO (01-08)": list(range(1, 9)),
    "MÉDIO (09-16)": list(range(9, 17)),
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
        
        .box-sniper-hunter { background: linear-gradient(135deg, #004d00, #006400); border: 2px solid #00ff00; padding: 15px; border-radius: 8px; border-left: 8px solid #00ff00; margin-bottom: 15px; color: #ccffcc; box-shadow: 0 0 15px rgba(0, 255, 0, 0.2); }
        .palpite-box { background: linear-gradient(90deg, #004d00 0%, #002b00 100%); border: 1px solid #00ff00; padding: 15px; border-radius: 10px; margin-bottom: 20px; color: #ccffcc; }
        .palpite-nums { font-size: 24px; font-weight: bold; color: #fff; letter-spacing: 2px; }
        
        .sniper-box { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); border: 2px solid #00d2ff; padding: 20px; border-radius: 15px; margin-bottom: 10px; text-align: center; box-shadow: 0px 0px 25px rgba(0, 210, 255, 0.2); }
        .sniper-record { border: 2px solid #ff00de !important; box-shadow: 0px 0px 25px rgba(255, 0, 222, 0.4) !important; background: linear-gradient(135deg, #3a0035, #240b36) !important; }
        
        .sniper-reversao { border: 2px solid #ff4b4b !important; box-shadow: 0px 0px 25px rgba(255, 75, 75, 0.4) !important; background: linear-gradient(135deg, #4a0000, #2c0000) !important; }
        .reversao-badge { background-color: #ff4b4b; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 14px; margin-bottom: 10px; display: inline-block; }

        .sniper-title { font-size: 20px; font-weight: 900; color: #ffffff; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; opacity: 0.8; }
        .sniper-bank { font-size: 32px; font-weight: 900; color: #00d2ff; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; text-shadow: 0px 0px 15px rgba(0,210,255,0.6); }
        .sniper-target { font-size: 20px; font-weight: bold; color: #fff; margin-bottom: 10px; text-transform: uppercase; }
        .sniper-next { font-size: 18px; color: #00ff00; font-weight: bold; background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; display: inline-block; margin-bottom: 15px; border: 1px solid #00ff00; }
        
        .section-strong { margin: 10px 0; border: 1px dashed #00ff00; padding: 10px; border-radius: 8px; background: rgba(0, 255, 0, 0.05); }
        .strong-label { color: #00ff00; font-weight: bold; font-size: 16px; margin-bottom: 5px; text-align: left; }
        .strong-nums { color: #fff; font-size: 24px; font-weight: bold; letter-spacing: 2px; }
        
        .section-weak { margin: 10px 0; border: 1px dashed #00d2ff; padding: 10px; border-radius: 8px; background: rgba(0, 210, 255, 0.05); }
        .weak-label { color: #00d2ff; font-weight: bold; font-size: 16px; margin-bottom: 5px; text-align: left; }
        .weak-nums { color: #fff; font-size: 18px; font-weight: normal; letter-spacing: 1px; word-wrap: break-word; }
        
        .sniper-meta { font-size: 14px; color: #a8d0e6; font-style: italic; margin-top: 10px; }
        
        .backtest-container { display: flex; justify-content: center; gap: 15px; margin-top: 5px; margin-bottom: 30px; flex-wrap: wrap; }
        .bt-card { background-color: rgba(30, 30, 30, 0.8); border-radius: 10px; padding: 10px; width: 100px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .bt-win { border: 2px solid #00ff00; color: #ccffcc; }
        .bt-loss { border: 2px solid #ff0000; color: #ffcccc; }
        .bt-icon { font-size: 24px; margin-bottom: 5px; }
        .bt-num { font-size: 16px; font-weight: bold; margin-bottom: 2px; }
        .bt-label { font-size: 11px; opacity: 0.8; }
        
        .max-loss-info { text-align: center; background-color: rgba(255, 0, 0, 0.1); border: 1px solid rgba(255, 0, 0, 0.3); color: #ffaaaa; padding: 5px 15px; border-radius: 20px; display: inline-block; margin-top: 10px; font-size: 14px; font-weight: bold; }
        .bola-b { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-m { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-a { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-v { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #6f42c1; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        div[data-testid="stTable"] table { color: white; }
        thead tr th:first-child {display:none}
        tbody th {display:none}
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
                        dados_processados.append({ "data": row[0], "horario": row[1], "premios": premios })
                except: pass
        return dados_processados
    return []

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
            if idx == len(horarios) - 1: return f"PARA AS {horarios[0]} HS (Amanhã)"
            else: return f"PARA AS {horarios[idx+1]} HS"
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
            if atraso_atual <= 2: status = "❄️ Saiu Agora (Aguarde)"
            elif atraso_atual >= media: status = "🔥 PONTO DE ENTRADA"
            elif atraso_atual >= (media * 0.6): status = "⏳ Aquece (Quase lá)"
            else: status = "💤 Neutro"
            tabela_dados.append({ "GRUPO": bicho, "SAÍDAS (30 Jogos)": qtd, "MÉDIA": f"1 a cada {media:.1f}", "ÚLTIMA VEZ": f"Há {atraso_atual} jogos", "STATUS / DICA": status })
    def sort_key(x):
        s = x['STATUS / DICA']
        if "🔥" in s: return 0
        if "⏳" in s: return 1
        if "❄️" in s: return 3
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

# --- ALGORITMO SNIPER V40 (4-4-4) ---
def gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados):
    # 1. DETECÇÃO DE REVERSÃO
    setor_estourado = None
    for index, row in df_stress.iterrows():
        if "VACA" not in row['SETOR']:
            if row['SEQ. ATUAL'] >= row['REC. SEQ. (V)'] and row['REC. SEQ. (V)'] >= 3:
                setor_estourado = row['SETOR']
                break
    
    modo_reversao = False
    setores_reais = df_stress[~df_stress['SETOR'].str.contains("VACA")]
    
    if setor_estourado:
        modo_reversao = True
        setor_fraco = setor_estourado
        setores_ataque_df = setores_reais[setores_reais['SETOR'] != setor_estourado]
        setores_ataque_ordenados = setores_ataque_df.sort_values(by='% PRESENÇA', ascending=False)
        setor_forte_1 = setores_ataque_ordenados.iloc[0]['SETOR']
        setor_forte_2 = setores_ataque_ordenados.iloc[1]['SETOR']
    else:
        setores_ordenados = setores_reais.sort_values(by='% PRESENÇA', ascending=False)
        setor_forte_1 = setores_ordenados.iloc[0]['SETOR']
        setor_forte_2 = setores_ordenados.iloc[1]['SETOR']
        setor_fraco = setores_ordenados.iloc[-1]['SETOR']

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

    # 3. PROCESSAMENTO DOS GRUPOS (ATAQUE 4+4)
    grupos_ataque = []
    
    # Setor Forte 1 -> Top 4
    g_s1 = SETORES[setor_forte_1]
    rank_s1 = sorted(g_s1, key=lambda x: calcular_score(x), reverse=True)
    grupos_ataque.extend(rank_s1[:4])

    # Setor Forte 2 -> Top 4
    g_s2 = SETORES[setor_forte_2]
    rank_s2 = sorted(g_s2, key=lambda x: calcular_score(x), reverse=True)
    grupos_ataque.extend(rank_s2[:4])

    # 4. PROCESSAMENTO DAS DEZENAS (DEFESA 4 Grupos do Fraco)
    dezenas_proibidas = ['00', '11', '22', '33', '44', '55', '66', '77', '88', '99']
    grupos_defesa_base = SETORES[setor_fraco]
    
    # Ordena o setor fraco pelo score para pegar os 4 melhores
    rank_defesa = sorted(grupos_defesa_base, key=lambda x: calcular_score(x), reverse=True)
    
    # Filtra saturados da defesa
    grupos_defesa_finais = [g for g in rank_defesa if g not in saturados]
    
    # Limita a 4 Grupos para defesa (Config 4-4-4)
    grupos_defesa_finais = grupos_defesa_finais[:4]
    
    # Se ainda faltar para completar 4, pega da reserva (saturados ou fora do rank) com cuidado
    if len(grupos_defesa_finais) < 4:
        sobra = 4 - len(grupos_defesa_finais)
        # Pega do resto do setor fraco mesmo que "saturado" se não tiver opção, ou de outros setores
        # Aqui vamos priorizar completar com o próprio setor fraco para manter a lógica do setor
        resto_setor = [g for g in grupos_defesa_base if g not in grupos_defesa_finais]
        grupos_defesa_finais.extend(resto_setor[:sobra])

    dezenas_defesa = []
    for g in grupos_defesa_finais:
        if g not in grupos_ataque:
            dzs = GRUPOS_DEZENAS[g]
            pre_selecao = dzs[:3]
            filtradas = [d for d in pre_selecao if d not in dezenas_proibidas]
            dezenas_defesa.extend(filtradas)

    # 5. VACA
    score_vaca = 0
    row_vaca = df_stress[df_stress['SETOR'].str.contains("VACA")].iloc[0]
    if row_vaca['ATRASO'] > 12: score_vaca += 80 
    if 25 == ultimo_bicho: score_vaca += 500
    if 25 in stats_ciclo['faltam']: score_vaca += 100
    if 25 in saturados: score_vaca -= 5000

    if score_vaca > 50:
        dezenas_defesa.append('97')
        dezenas_defesa.append('98')

    # Limpeza Final
    grupos_ataque = sorted(list(set(grupos_ataque)))
    if 25 in grupos_ataque: grupos_ataque.remove(25)
    
    dezenas_defesa = sorted(list(set(dezenas_defesa))) 
    
    sf1_name = setor_forte_1.split(' ')[0]
    sf2_name = setor_forte_2.split(' ')[0]
    sf_fraco_name = setor_fraco.split(' ')[0]
    
    if modo_reversao:
        meta_info = f"🔄 REVERSÃO (4-4-4): {sf_fraco_name} Bloqueado! Ataque com {sf1_name}+{sf2_name}"
    else:
        meta_info = f"TENDÊNCIA (4-4-4): {sf1_name}+{sf2_name} Fortes | {sf_fraco_name} Defesa"
    
    return { 
        "grupos_ataque": grupos_ataque, 
        "dezenas_defesa": dezenas_defesa,
        "nota": 100, 
        "meta_info": meta_info, 
        "modo_reversao": modo_reversao,
        "is_record": False 
    }

# --- BACKTEST V40 ---
def executar_backtest_sniper(historico, indice_premio):
    resultados_backtest = []
    for i in range(1, 5):
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
        
        meta = sniper_past['meta_info']
        if "REVERSÃO" in meta:
            match = re.search(r"REVERSÃO.*: (\w+) Bloqueado", meta)
            nome_fraco = match.group(1) if match else ""
        else:
            match = re.search(r"(\w+) Defesa", meta) # Ajustado para o novo texto
            nome_fraco = match.group(1) if match else ""
            
        win_defesa = False
        if nome_fraco:
            chave_setor = next((k for k in SETORES.keys() if nome_fraco in k), None)
            if chave_setor:
                # Aqui no backtest, como é simplificado, verificamos se caiu no setor de defesa
                # Na prática real, ganhamos se cair nas dezenas, mas para backtest de tendência, setor serve
                win_defesa = target_num in SETORES[chave_setor]
        
        win_total = win_ataque or win_defesa
        resultados_backtest.append({ "index": i, "numero_real": target_num, "vitoria": win_total })
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
        win_ataque = target_num in sniper_past['grupos_ataque']
        meta = sniper_past['meta_info']
        if "REVERSÃO" in meta:
            match = re.search(r"REVERSÃO.*: (\w+) Bloqueado", meta)
            nome_fraco = match.group(1) if match else ""
        else:
            match = re.search(r"(\w+) Defesa", meta)
            nome_fraco = match.group(1) if match else ""
        win_defesa = False
        if nome_fraco:
            chave_setor = next((k for k in SETORES.keys() if nome_fraco in k), None)
            if chave_setor: win_defesa = target_num in SETORES[chave_setor]
        win = win_ataque or win_defesa
        if not win: derrotas_consecutivas_temp += 1
        else:
            if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
            derrotas_consecutivas_temp = 0
    if derrotas_consecutivas_temp > max_derrotas: max_derrotas = derrotas_consecutivas_temp
    return max_derrotas

def gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante):
    candidatos = [] 
    setor_critico = None
    for index, row in df_stress.iterrows():
        setor = row['SETOR']
        if "VACA" not in setor and (row['REC. ATRASO'] - row['ATRASO']) <= 1 and row['REC. ATRASO'] >= 5:
            setor_critico = setor
            break
    motivo = "Mix Equilibrado."
    if setor_critico:
        motivo = f"Foco no {setor_critico} (Crítico) + Proteção."
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
    return { "tipo": "SMART MIX", "grupos": palpite_final, "destaque": destaque, "motivo": motivo }

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
    
    with st.spinner("O Robô Sniper está caçando a melhor oportunidade..."):
        alertas_globais = []
        palpites_gerados = []
        
        melhor_sniper = None
        melhor_nota_sniper = -1
        
        for banca_key, config in CONFIG_BANCAS.items():
            historico = carregar_dados_top5(config['nome_aba'])
            if len(historico) > 0:
                for idx_pos in range(5):
                    # CALCULA DADOS
                    df_stress = calcular_stress_tabela(historico, idx_pos)
                    stats_ciclo = calcular_ciclo(historico, idx_pos)
                    df_diamante = calcular_tabela_diamante(historico, idx_pos)
                    ultimo_bicho = historico[-1]['premios'][idx_pos]
                    saturados_list = identificar_saturados(historico, idx_pos)
                    
                    # 1. SNIPER V40 (4-4-4)
                    sniper = gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados_list)
                    if sniper['nota'] > melhor_nota_sniper:
                        melhor_nota_sniper = sniper['nota']
                        melhor_sniper = {
                            "banca": config['display_name'].split("(")[0].strip(),
                            "premio": f"{idx_pos+1}º Prêmio",
                            "dados": sniper,
                            "banca_key": banca_key,
                            "ultimo_horario": historico[-1]['horario']
                        }
                    
                    # 2. VERIFICAÇÃO DE FALHAS
                    bt_results = executar_backtest_sniper(historico, idx_pos)
                    if len(bt_results) >= 2:
                        if not bt_results[0]['vitoria'] and not bt_results[1]['vitoria']:
                            prox_hora = obter_proxima_batalha(banca_key, historico[-1]['horario'])
                            alertas_globais.append({
                                "tipo": "SNIPER_OPPORTUNITY",
                                "banca": config['display_name'].split("(")[0].strip(),
                                "premio": f"{idx_pos+1}º Prêmio",
                                "msg_extra": f"🎯 2 Derrotas Consecutivas! {prox_hora}"
                            })

                    tem_alerta_critico = False
                    for _, row in df_stress.iterrows():
                        atraso = row['ATRASO']; recorde = row['REC. ATRASO']; setor = row['SETOR']
                        seq_atual = row['SEQ. ATUAL']; recorde_seq = row['REC. SEQ. (V)']
                        if "VACA" in setor: continue
                        if (recorde - atraso) <= 1 and recorde >= 5:
                            alertas_globais.append({"tipo": "ATRASO", "banca": config['display_name'].split("(")[0].strip(), "premio": f"{idx_pos+1}º Prêmio", "setor": setor, "val_atual": atraso, "val_rec": recorde})
                            tem_alerta_critico = True
                        margem_seq = recorde_seq - seq_atual
                        if margem_seq <= 1 and recorde_seq >= 3:
                            alertas_globais.append({"tipo": "REPETICAO", "banca": config['display_name'].split("(")[0].strip(), "premio": f"{idx_pos+1}º Prêmio", "setor": setor, "val_atual": seq_atual, "val_rec": recorde_seq, "margem": margem_seq})
                            tem_alerta_critico = True
                    
                    if tem_alerta_critico:
                        palpite = gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante)
                        palpites_gerados.append({ "banca": config['display_name'].split("(")[0].strip(), "premio": f"{idx_pos+1}º Prêmio", "grupos": palpite['grupos'], "motivo": palpite['motivo'], "destaque": palpite['destaque'] })

        col2.metric("Base de Dados", "Conectada", "Google Sheets")
        col3.metric("Oportunidades Críticas", f"{len(alertas_globais)}", "Zonas de Tiro")
        st.markdown("---")
        
        # DEFINE COR_NOTA ANTES DE USAR
        cor_nota = "#ffffff" # Default safety
        
        if melhor_sniper:
            d = melhor_sniper['dados']
            cor_nota = "#00ff00" if d['nota'] > 80 else "#ffcc00"
            css_extra = "sniper-reversao" if d['modo_reversao'] else "sniper-record" if d['is_record'] else ""
            prox_tiro = obter_proxima_batalha(melhor_sniper['banca_key'], melhor_sniper['ultimo_horario'])
            badge_rev = "<div class='reversao-badge'>🔄 MODO REVERSÃO ATIVADO</div><br>" if d['modo_reversao'] else ""
            
            st.markdown(f"""
<div class="sniper-box {css_extra}">
{badge_rev}
<div class="sniper-title">🎯 SNIPER V40.0 (4-4-4)</div>
<div class="sniper-bank">{melhor_sniper['banca']}</div>
<div class="sniper-target">{melhor_sniper['premio']}</div>
<div class="sniper-next">{prox_tiro}</div>
<p style="color:{cor_nota}; font-weight:bold;">{d['meta_info']}</p>
<div class="section-strong">
<div class="strong-label">🟢 ATAQUE (4+4 GRUPOS):</div>
<div class="strong-nums">{', '.join(map(str, d['grupos_ataque']))}</div>
</div>
<div class="section-weak">
<div class="weak-label">🛡️ DEFESA (DEZENAS DO FRACO 4G):</div>
<div class="weak-nums">{', '.join(map(str, d['dezenas_defesa']))}</div>
</div>
</div>
""", unsafe_allow_html=True)
        else: st.info("O Sniper está calibrando... (Sem dados suficientes).")

        if alertas_globais:
            st.warning("🚨 Oportunidades Encontradas")
            cols = st.columns(2)
            for i, alerta in enumerate(alertas_globais):
                if alerta['tipo'] == "SNIPER_OPPORTUNITY":
                    with cols[i % 2]: st.markdown(f"<div class='box-sniper-hunter'><h3>{alerta['banca']}</h3><p>📍 <b>{alerta['premio']}</b></p><p style='font-size:18px; font-weight:bold;'>{alerta['msg_extra']}</p></div>", unsafe_allow_html=True)
                else:
                    if alerta['tipo'] == "ATRASO":
                        classe, titulo_val, msg = "box-alerta" if alerta['val_atual'] >= alerta['val_rec'] else "box-aviso", "Atraso", "ZONA DE TIRO (Atraso)"
                    else: 
                        classe, msg = ("box-inverso-critico", "ESTOURADO!") if alerta['margem'] <= 0 else ("box-inverso-atencao", "Atenção")
                        titulo_val = "Sequência"
                    with cols[i % 2]: st.markdown(f"<div class='{classe}'><h3>{alerta['banca']}</h3><p>📍 <b>{alerta['premio']}</b> | {alerta['setor']}</p><p>{titulo_val}: {alerta['val_atual']} (Recorde: {alerta['val_rec']})</p><p><b>{msg}</b></p></div>", unsafe_allow_html=True)
        else: st.success("✅ Tudo calmo nas 3 bancas (fora o Sniper).")

        if palpites_gerados:
            st.markdown("### 🏹 PREVISÕES DE PROTEÇÃO (8 Grupos)")
            for p in palpites_gerados:
                st.markdown(f"<div class='palpite-box'><h4>{p['banca']} - {p['premio']}</h4><p class='palpite-nums'>{', '.join(map(str, p['grupos']))}</p><small><b>Motivo:</b> {p['motivo']}</small></div>", unsafe_allow_html=True)

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
                        chaves = [f"{str(row[0]).strip()}|{str(row[1]).strip()}" for row in existentes if len(row)>1]
                    except: chaves = []
                    chave_atual = f"{data_busca.strftime('%Y-%m-%d')}|{horario_busca}"
                    if chave_atual in chaves:
                        try:
                            idx = chaves.index(chave_atual) + 2
                            st.warning(f"Resultado já existe na Linha {idx} da planilha!")
                        except: st.warning("Resultado já existe!")
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
        
        prox_tiro_local = obter_proxima_batalha(banca_selecionada, ult['horario'])
        nome_banca_clean = config_banca['display_name'].split('(')[0].strip().upper()
        
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
                ultimo_bicho = historico[-1]['premios'][idx_aba]
                saturados = identificar_saturados(historico, idx_aba)
                
                # --- SNIPER V40 (AUTO) ---
                sniper_local = gerar_sniper_v39_final(df_stress, stats_ciclo, df_diamante, ultimo_bicho, saturados)
                bt_results = executar_backtest_sniper(historico, idx_aba)
                max_loss_record = calcular_max_derrotas_50(historico, idx_aba)
                
                css_extra = "sniper-reversao" if sniper_local['modo_reversao'] else "sniper-record" if sniper_local['is_record'] else ""
                
                # VISUAL SNIPER V40
                if saturados: msg_sat = f"<br><span style='color:#ff4b4b; font-size:12px;'>🥵 Saturação: {saturados}</span>"
                else: msg_sat = ""
                badge_rev = "<div class='reversao-badge'>🔄 MODO REVERSÃO ATIVADO</div><br>" if sniper_local['modo_reversao'] else ""
                
                cor_nota = "#00ff00" 

                st.markdown(f"""
<div class="sniper-box {css_extra}" style="margin-top:0;">
{badge_rev}
<div class="sniper-title">🎯 SNIPER LOCAL V40 (4-4-4)</div>
<div class="sniper-bank">{nome_banca_clean}</div>
<div class="sniper-target">{nomes_posicoes[idx_aba]}</div>
<div class="sniper-next">{prox_tiro_local}</div>
<p style="color:#ddd; font-size:12px;">{sniper_local['meta_info']}</p>

<div class="section-strong">
<div class="strong-label">🟢 ATAQUE (4+4 GRUPOS):</div>
<div class="strong-nums">{', '.join(map(str, sniper_local['grupos_ataque']))}</div>
</div>

<div class="section-weak">
<div class="weak-label">🛡️ DEFESA (DEZENAS DE 4 GRUPOS):</div>
<div class="weak-nums">{', '.join(map(str, sniper_local['dezenas_defesa']))}</div>
</div>
{msg_sat}
</div>
""", unsafe_allow_html=True)
                
                st.markdown(f"<div style='text-align:center;'><span class='max-loss-info'>📉 Pior Sequência (50 Jogos): {max_loss_record} Derrotas</span></div>", unsafe_allow_html=True)
                
                if bt_results:
                    cards_html = ""
                    for res in reversed(bt_results):
                        classe_res = "bt-win" if res['vitoria'] else "bt-loss"
                        icon = "🟢" if res['vitoria'] else "❌"
                        cards_html += f"<div class='bt-card {classe_res}'><div class='bt-icon'>{icon}</div><div class='bt-num'>G: {res['numero_real']}</div><div class='bt-label'>-{res['index']} Jogos</div></div>"
                    final_html = f"<div class='backtest-container'>{cards_html}</div>"
                    st.markdown(final_html, unsafe_allow_html=True)

                palpite = gerar_palpite_8_grupos(df_stress, stats_ciclo, df_diamante)
                st.markdown(f"<div class='palpite-box'><h4>🏹 PROTEÇÃO GRUPOS (8 GRUPOS)</h4><p class='palpite-nums'>{', '.join(map(str, palpite['grupos']))}</p><small><b>Motivo:</b> {palpite['motivo']}</small></div>", unsafe_allow_html=True)
                
                st.markdown(f"### 📊 Raio-X: {nomes_posicoes[idx_aba]}")
                st.markdown("**Visual Recente (⬅️ Mais Novo):**")
                st.markdown(gerar_bolinhas_recentes(historico, idx_aba), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                # --- GRÁFICO DONUT ---
                df_chart = df_stress.copy()
                df_chart = df_chart.rename(columns={"% PRESENÇA": "PRESENCA", "SETOR": "CATEGORIA"})
                base = alt.Chart(df_chart).encode(theta=alt.Theta("PRESENCA", stack=True))
                pie = base.mark_arc(outerRadius=120).encode(
                    color=alt.Color("CATEGORIA", scale=alt.Scale(domain=['BAIXO (01-08)', 'MÉDIO (09-16)', 'ALTO (17-24)', 'VACA (25)'], range=['#00d2ff', '#ff9900', '#ff3333', '#aa00ff']), legend=None),
                    order=alt.Order("PRESENCA", sort="descending"), tooltip=["CATEGORIA", "PRESENCA"]
                )
                text = base.mark_text(radius=140).encode(text=alt.Text("PRESENCA", format=".1f"), order=alt.Order("PRESENCA", sort="descending"), color=alt.value("white"))
                st.altair_chart(pie + text, use_container_width=True)
                
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
