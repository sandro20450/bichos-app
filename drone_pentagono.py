import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# =============================================================================
# --- 1. CONFIGURAÇÕES INICIAIS E TELEGRAM ---
# =============================================================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
google_creds_str = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {"Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"}
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

def enviar_telegram(mensagem):
    """Envia a mensagem formatada em HTML para o celular do Comandante."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    if len(mensagem) > 4000:
        partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
        for parte in partes: requests.post(url, data={"chat_id": CHAT_ID, "text": parte, "parse_mode": "HTML"})
    else: requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "HTML"})

def conectar_sheets():
    """Autentica o robô no banco de dados do Google Sheets."""
    try:
        creds_dict = json.loads(google_creds_str)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("CentralBichos")
    except Exception as e: return None

# =============================================================================
# --- NOVO: RELATÓRIO DIÁRIO DE SAÚDE (BOM DIA) ---
# =============================================================================
def verificar_relatorio_matinal(dados_bancas):
    """
    Verifica se já passou das 08:00 da manhã. Se sim, envia um relatório 
    informando que o robô está ativo e o status do banco de dados.
    Usa um arquivo de texto para lembrar se já enviou hoje.
    """
    agora = datetime.now()
    # Verifica se já são 8h da manhã ou mais
    if agora.hour >= 8:
        hoje_str = agora.strftime("%Y-%m-%d")
        arquivo_memoria = "memoria_bom_dia.txt"
        ja_enviou_hoje = False
        
        # Lê a memória do robô para saber se ele já deu bom dia hoje
        if os.path.exists(arquivo_memoria):
            with open(arquivo_memoria, "r") as f:
                data_salva = f.read().strip()
                if data_salva == hoje_str:
                    ja_enviou_hoje = True
                    
        # Se ainda não enviou hoje, prepara e dispara o relatório
        if not ja_enviou_hoje:
            resumo_bancas = ""
            for nome, df in dados_bancas.items():
                if not df.empty:
                    ult_sorteio = str(df.iloc[-1]["Sorteio"])
                    total_linhas = len(df)
                    resumo_bancas += f"▫️ <b>{nome}:</b> {total_linhas} registros (Último: {ult_sorteio})\n"
            
            msg_bom_dia = (
                "☀️ <b>BOM DIA, COMANDANTE!</b>\n\n"
                "🤖 <b>Status do Drone:</b> 100% ONLINE E VIGIANDO.\n"
                "📡 <b>Conexão Google Sheets:</b> ESTÁVEL.\n\n"
                "📊 <b>Resumo do Banco de Dados:</b>\n"
                f"{resumo_bancas}\n"
                "🎯 <i>Modo Stealth Ativado. Aguardando alvos atingirem o Teto ou dispararem Gatilhos de Duplas.</i>"
            )
            
            enviar_telegram(msg_bom_dia)
            
            # Grava na memória que o bom dia de hoje já foi dado
            with open(arquivo_memoria, "w") as f:
                f.write(hoje_str)

# =============================================================================
# --- 3. MOTORES DE ANÁLISE (GATILHOS E TETOS) ---
# =============================================================================
def processar_anomalia_duplas(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = [m.strip().zfill(4) for m in valores if m.strip().zfill(4) not in ["----", "0nan", "nan", ""]]
    if len(validos) < 2: return None
    
    streak_counts = {}
    temp_streak = 0
    for val in validos:
        c = val[-3:]
        if len(set(c)) < 3: 
            temp_streak += 1
        else:
            if temp_streak > 0:
                streak_counts[temp_streak] = streak_counts.get(temp_streak, 0) + 1
                temp_streak = 0
                
    current_streak = temp_streak
    
    if current_streak >= 2:
        seen_digits_set = set(); seen_digits_list = []; cold_digit = None
        for val in reversed(validos):
            for char in val[-3:]:
                d = int(char)
                if d not in seen_digits_set: 
                    seen_digits_set.add(d)
                    seen_digits_list.append(str(d))
                if len(seen_digits_set) == 9: 
                    cold_digit = (set(range(10)) - seen_digits_set).pop()
                    break
            if cold_digit is not None: break
        
        if cold_digit is not None:
            excluido = seen_digits_list[4] 
            seen_digits_list.append(str(cold_digit))
            seq_str = " - ".join(seen_digits_list)
            max_historico = max(list(streak_counts.keys()) + [current_streak]) if streak_counts else current_streak
            
            # Tendência Preditiva
            total_reached = sum(v for k, v in streak_counts.items() if k >= current_streak) + 1
            broke_at_current = streak_counts.get(current_streak, 0)
            prob_break = (broke_at_current / total_reached) * 100 if total_reached > 0 else 0
            prob_cont = 100 - prob_break
            trend_text = f"Quebra Agora: {prob_break:.1f}% | Avança pra {current_streak+1}x: {prob_cont:.1f}%"
            
            return cold_digit, seq_str, excluido, current_streak, max_historico, streak_counts, trend_text
            
    return None

def gerar_matrizes_taticas():
    esquadroes = []; cms = [{'c_min': 0, 'c_max': 499, 'm_min': 0, 'm_max': 4999}, {'c_min': 500, 'c_max': 999, 'm_min': 5000, 'm_max': 9999}]
    for cm in cms:
        for g in range(1, 14): esquadroes.append({'alvos': set(range(g, g+13)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G13: {str(g).zfill(2)}-{str(g+12).zfill(2)}", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(51, 100))|{0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS", 'lim': 9, **cm})
    
    esquadroes.extend([
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ])
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo, c_min, c_max, m_min, m_max = cfg['alvos'], cfg['modo'], cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
    cur_p, cur_c, cur_m, max_p, max_c, max_m = 0, 0, 0, 0, 0, 0
    valores = df_analise[coluna].astype(str).tolist()
    for val in valores:
        milhar = val.strip().zfill(4)
        if milhar in ["----", "0nan", "nan", ""]: continue
        try: m = int(milhar); c = int(milhar[-3:]); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: continue
        g = 25 if d == 0 else math.ceil(d/4)
        hit_p = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos) or (modo == 'centena' and c in alvos)
        
        if hit_p: cur_p = 0
        else: cur_p += 1; max_p = max(max_p, cur_p)
        if (c_min <= c <= c_max): cur_c = 0
        else: cur_c += 1; max_c = max(max_c, cur_c)
        if (m_min <= m <= m_max): cur_m = 0
        else: cur_m += 1; max_m = max(max_m, cur_m)
    return cur_p, cur_c, cur_m, max_p, max_c, max_m

def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        resultados = []; vistos_assinaturas = set() 
        for tab in soup.find_all('table'):
            th_tag = tab.find('th')
            texto_alvo = (th_tag.get_text().upper() if th_tag else "") + " " + (tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b']).get_text().upper() if tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b']) else "")
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            nome = f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora and match_hora.group(1) else "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                assinatura = "".join(milhares)
                if assinatura not in vistos_assinaturas and milhares[0] != "----":
                    vistos_assinaturas.add(assinatura); resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 4. MOTOR PRINCIPAL DO DRONE ---
# =============================================================================
def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    dt = date.today()
    total_salvos = 0; dados_bancas = {}
    
    # Etapa 1: Atualização dos Dados
    for banca_nome, aba_nome in MAPA_ABAS.items():
        res = extrair_dia(banca_nome, dt)
        ws = sh.worksheet(aba_nome)
        if res:
            existentes = ws.get_all_values()
            set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
            p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
            if p_ins: ws.append_rows(p_ins, value_input_option="RAW"); total_salvos += len(p_ins)
        
        dados_atualizados = ws.get_all_values()
        if len(dados_atualizados) > 1:
            df = pd.DataFrame(dados_atualizados[1:], columns=["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"])
            df = df[df["P1"].astype(str).str.strip() != ""]
            dados_bancas[banca_nome] = df

    # Etapa 2: Checagem Matinal (Novo Recurso)
    if dados_bancas:
        verificar_relatorio_matinal(dados_bancas)

    # Etapa 3: Varredura de Anomalias (Stealth Mode)
    todos_esq = gerar_matrizes_taticas()
    msg_telegram = ""; achou_algo = False; alvos_vistos = set()

    for banca_nome, df in dados_bancas.items():
        if df.empty: continue
        ultimo_sorteio = str(df.iloc[-1]["Sorteio"])

        for i, col in enumerate(COLUNAS_DF):
            if banca_nome == "Tradicional" and col != "P1": continue
            
            # Análise de Duplas Seguidas
            res_duplas = processar_anomalia_duplas(df, col)
            if res_duplas:
                cold_d, seq_s, excl, streak, max_hist, historico, trend_txt = res_duplas
                sig_dupla = f"DUPLA_{banca_nome}_{col}_{streak}"
                
                if sig_dupla not in alvos_vistos:
                    freq_str = f"2x: {historico.get(2, 0)}v"
                    if 3 in historico: freq_str += f" | 3x: {historico.get(3, 0)}v"
                    if 4 in historico: freq_str += f" | 4x: {historico.get(4, 0)}v"
                    if max_hist > 4: freq_str += f" | {max_hist}x: {historico.get(max_hist, 0)}v"

                    icone_cor = "🟡" if streak == 2 else "🟢"
                    msg_telegram += f"{icone_cor} <b>GATILHO DE ANOMALIA ({streak}x DUPLAS SEGUIDAS)</b>\n"
                    msg_telegram += f"🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {TITULOS_PREMIOS[i]}\n"
                    msg_telegram += f"📊 <b>HISTÓRICO (RAIO-X DO PRÊMIO):</b>\n"
                    msg_telegram += f"Recorde: {max_hist}x | Freq: {freq_str}\n"
                    msg_telegram += f"📈 <b>TENDÊNCIA:</b> {trend_txt}\n\n"
                    msg_telegram += f"🎯 <b>Ataque Recomendado (10D):</b> {seq_s}\n"
                    msg_telegram += f"❌ Excluir Ponto Cego: {excl}\n\n"
                    achou_algo = True; alvos_vistos.add(sig_dupla)

        # Análise das Matrizes Regulares
        metrics_cache = {}
        for cfg in todos_esq:
            for col in COLUNAS_DF:
                if banca_nome == "Tradicional" and col != "P1": continue
                ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                metrics_cache[(cfg['nome'], cfg['c_min'], col)] = (ap, ac, am)

        for cfg in todos_esq:
            for i, col in enumerate(COLUNAS_DF):
                if (cfg['nome'], cfg['c_min'], col) not in metrics_cache: continue
                ap, ac, am = metrics_cache[(cfg['nome'], cfg['c_min'], col)]
                ap_lim = cfg['lim']
                
                is_anomaly = False; tipo_ataque = ""
                
                # Gatilho Silencioso (Somente no Teto Exato)
                if am >= 9 and ac >= 9 and ap >= ap_lim: is_anomaly = True; tipo_ataque = "🔥 ATAQUE TOTAL (G+C+M)"
                elif am >= 9: is_anomaly = True; tipo_ataque = f"🔵 ATAQUE MILHAR ({am}x)"
                elif ac >= 9: is_anomaly = True; tipo_ataque = f"🟢 ATAQUE CENTENA ({ac}x)"
                elif ap >= ap_lim: is_anomaly = True; tipo_ataque = f"🟡 ATAQUE FORTE ({cfg['modo'].upper()})"

                if is_anomaly:
                    c_min, c_max, m_min, m_max = cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
                    
                    if "MILHAR" in tipo_ataque: sig = f"{banca_nome}_{col}_M_{m_min}"
                    elif "CENTENA" in tipo_ataque: sig = f"{banca_nome}_{col}_C_{c_min}"
                    else: sig = f"{banca_nome}_{col}_{cfg['nome']}"
                    
                    if sig in alvos_vistos: continue
                    alvos_vistos.add(sig)

                    msg_telegram += f"🎯 <b>{tipo_ataque}</b>\n🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {TITULOS_PREMIOS[i]}\nAlvo: <b>{cfg['nome']}</b>\nAtraso Principal: {ap}x\n"
                    msg_telegram += f"Base C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}\nAtraso C: {ac}x | Atraso M: {am}x\n\n"
                    
                    teto_alvo = 9 if "MILHAR" in tipo_ataque or "CENTENA" in tipo_ataque or "TOTAL" in tipo_ataque else ap_lim
                    _, _, _, mp_r, mc_r, mm_r = calcular_metricas_fantasma(df, col, cfg) 
                    recorde_alvo = mp_r
                    if "MILHAR" in tipo_ataque: recorde_alvo = mm_r
                    elif "CENTENA" in tipo_ataque: recorde_alvo = mc_r
                    elif "TOTAL" in tipo_ataque: recorde_alvo = max(mp_r, mc_r, mm_r)
                    
                    if recorde_alvo > teto_alvo + 2:
                        espera_sugerida = teto_alvo + 2
                        msg_telegram += f"🚨 <b>PERIGO DE ANOMALIA:</b>\nRecorde Histórico é {recorde_alvo}x. Risco de quebra de Martingale!\n⚠️ Sugestão: Aguarde o atraso bater {espera_sugerida}x ou aplique gestão mínima.\n\n"
                    
                    achou_algo = True

    # Se achou anomalia no radar, envia. Caso contrário, só avisa se for a primeira rodada do dia com dados novos.
    if achou_algo: 
        enviar_telegram("🛸 <b>DRONE PENTÁGONO - ALVOS ENGATILHADOS</b> 🛸\n\n" + msg_telegram)
    elif total_salvos > 0: 
        enviar_telegram(f"🟢 <b>ROTAÇÃO CONCLUÍDA</b>\n{total_salvos} novos sorteios salvos. Mercado em Stealth (Nenhum teto rompido).")

if __name__ == "__main__":
    rodar_drone()
