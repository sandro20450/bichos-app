import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
google_creds_str = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    if len(mensagem) > 4000:
        partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
        for parte in partes: requests.post(url, data={"chat_id": CHAT_ID, "text": parte, "parse_mode": "HTML"})
    else:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "HTML"})

def conectar_sheets():
    try:
        creds_dict = json.loads(google_creds_str)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("CentralBichos")
    except Exception as e:
        enviar_telegram(f"❌ <b>ERRO NO DRONE:</b> Falha ao conectar no Google Sheets. Erro: {e}")
        return None

# =============================================================================
# 🐺 NOVO MOTOR: CAÇA 9D POR ANOMALIA (EXCLUSÃO DE DÍGITO FRIO)
# =============================================================================
def processar_caca_9d_anomalia(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = []
    
    for val in valores:
        m = val.strip().zfill(4)
        if m != "----" and m != "0nan" and m != "nan" and m.strip():
            try:
                _ = int(m)
                validos.append(m)
            except: pass
            
    if len(validos) < 2: return None
    
    c1 = validos[-1][-3:] 
    c2 = validos[-2][-3:] 
    
    if len(set(c1)) < 3 and len(set(c2)) < 3:
        seen_digits = set()
        cold_digit = None
        
        for val in reversed(validos):
            centena = val[-3:]
            for char in centena:
                d = int(char)
                if d not in seen_digits:
                    seen_digits.add(d)
                    if len(seen_digits) == 9:
                        cold_digit = (set(range(10)) - seen_digits).pop()
                        break
            if cold_digit is not None:
                break
                
        if cold_digit is not None:
            seq = [str((cold_digit - i) % 10) for i in range(9)]
            seq_str = " - ".join(seq)
            excluido = (cold_digit + 1) % 10 
            return cold_digit, seq_str, excluido
            
    return None

def get_grupo_int(m):
    try: d = int(str(m)[-2:]); return 25 if d == 0 else math.ceil(d/4)
    except: return None

def gerar_matrizes_taticas():
    esquadroes = []; cms = []
    cms.append({'c_min': 0, 'c_max': 499, 'm_min': 0, 'm_max': 4999})
    cms.append({'c_min': 500, 'c_max': 999, 'm_min': 5000, 'm_max': 9999})
    
    for cm in cms:
        for g in range(1, 14): esquadroes.append({'alvos': set(range(g, g+13)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G13: {str(g).zfill(2)}-{str(g+12).zfill(2)}", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(51, 100))|{0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS", 'lim': 9, **cm})
        
        bases_inv_8 = [[0,1,2,3,4,5,6,7], [1,2,3,4,5,6,7,8]]
        for b in bases_inv_8: esquadroes.append({'alvos': {int(f"{d1}{d2}") for d1 in b for d2 in b if d1!=d2}, 'modo': 'dezena', 'tipo': 'dez', 'nome': f"D: INV 8D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
            
        bases_inv_9 = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9]]
        for b in bases_inv_9: esquadroes.append({'alvos': {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1!=d2 and d2!=d3 and d1!=d3}, 'modo': 'centena', 'tipo': 'seq', 'nome': f"C: INV 9D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    cur_p, cur_c, cur_m = 0, 0, 0
    max_p, max_c, max_m = 0, 0, 0
    
    valores = df_analise[coluna].astype(str).tolist()
    for val in valores:
        milhar = val.strip().zfill(4)
        if milhar == "----" or milhar == "0nan" or milhar == "nan" or not milhar: continue
        try:
            m = int(milhar); c = int(milhar[-3:]); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: continue
        
        g = 25 if d == 0 else math.ceil(d/4)
        hit_p = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos) or (modo == 'centena' and c in alvos)
        
        if hit_p: cur_p = 0
        else: cur_p += 1; max_p = max(max_p, cur_p)
        if (c_min <= c <= c_max): cur_c = 0
        else: cur_c += 1; max_c = max(max_c, cur_c)
        if (m_min <= m <= m_max): cur_m = 0
        else: cur_m += 1; max_m = max(max_m, cur_m)
            
    return cur_p, cur_c, cur_m, max(max_p, cur_p), max(max_c, cur_c), max(max_m, cur_m)

def direcao_pendulo(prev, curr):
    if prev == curr: return "="
    dist_c = (curr - prev) % 25
    dist_d = (prev - curr) % 25
    if 1 <= dist_c <= 6: return "C"
    if 1 <= dist_d <= 6: return "D"
    return "-" 

def processar_pendulo(df, coluna):
    all_groups = []
    valores = df[coluna].astype(str).tolist()
    for val in valores:
        m = val.strip().zfill(4)
        if m != "----" and m != "0nan" and m != "nan" and m.strip():
            try:
                d = int(m[-2:])
                g = 25 if d == 0 else math.ceil(d/4)
                all_groups.append(g)
            except: pass
                
    if len(all_groups) < 6: return None
    dirs_history = []
    for i in range(1, len(all_groups)):
        dirs_history.append(direcao_pendulo(all_groups[i-1], all_groups[i]))
        
    curr_streak = 0
    curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
            
    if curr_streak >= 5:
        jogos = []; curr = all_groups[-1]
        if curr_dir == "C":
            for _ in range(15): jogos.append(str(curr).zfill(2)); curr = 25 if curr-1 < 1 else curr-1
        else:
            for _ in range(15): jogos.append(str(curr).zfill(2)); curr = 1 if curr+1 > 25 else curr+1
        return curr_streak, curr_dir, jogos
    return None

def get_hedge_grupos(df, col, cfg_matriz, metrics_cache):
    grupos = list(cfg_matriz['alvos'])
    scores = {g: 0 for g in grupos}
    col_delays = {k_name: val[0] for (k_name, k_col, k_cm), val in metrics_cache.items() if k_col == col and k_cm == cfg_matriz['c_min']}
    mass_max = max([col_delays.get('G: ÍMPARES', 0), col_delays.get('G: PARES', 0), col_delays.get('D: ALTAS (51-00)', 0), col_delays.get('D: BAIXAS (01-50)', 0)])

    if mass_max >= 3:
        if col_delays.get('G: ÍMPARES', 0) >= 3:
            for g in grupos:
                if g % 2 == 0: scores[g] += 1
        if col_delays.get('G: PARES', 0) >= 3:
            for g in grupos:
                if g % 2 != 0: scores[g] += 1
    else:
        uni_max = max([col_delays.get('U: ÍMPARES', 0), col_delays.get('U: PARES', 0), col_delays.get('U: ALTAS (6-0)', 0), col_delays.get('U: BAIXAS (1-5)', 0)])
        if uni_max >= 3:
            if col_delays.get('U: ÍMPARES', 0) >= 3:
                for g in grupos:
                    if (g % 10) % 2 == 0: scores[g] += 1

    sorted_g = sorted(grupos, key=lambda x: scores[x], reverse=True)
    eliminar = [g for g in sorted_g[:2] if scores[g] > 0] 
    if not eliminar: return None 

    seguro = {}
    valores = df[col].astype(str).tolist()
    for g in eliminar:
        dezenas = [g*4 - 3, g*4 - 2, g*4 - 1, g*4]
        if g == 25: dezenas = [97, 98, 99, 0]
        max_d_delay = -1; best_d = -1
        for d in dezenas:
            delay_d = 0
            for val in reversed(valores):
                m = val.strip().zfill(4)
                if m == "----" or m == "0nan" or m == "nan": continue
                try: dez_val = int(m[-2:])
                except: dez_val = -1
                if dez_val == d: break
                delay_d += 1
            if delay_d > max_d_delay: max_d_delay = delay_d; best_d = d
        seguro[g] = (best_d, max_d_delay)

    manter = [g for g in grupos if g not in eliminar]
    return {'eliminar': sorted(eliminar), 'manter': sorted(manter), 'seguro': seguro}

def get_cobertura_massa(df, col, cfg_nome):
    opostos = {
        "G: PARES": ("Grupo Ímpar", [1,3,5,7,9,11,13,15,17,19,21,23,25]),
        "G: ÍMPARES": ("Grupo Par", [2,4,6,8,10,12,14,16,18,20,22,24])
    }
    if cfg_nome not in opostos: return None
    desc_oposto, lista_grupos = opostos[cfg_nome]
    max_delay = -1; best_g = -1
    valores = df[col].astype(str).tolist()
    
    for g in lista_grupos:
        delay_g = 0
        for val in reversed(valores):
            m = val.strip().zfill(4)
            if m == "----" or m == "0nan" or m == "nan": continue
            try: d = int(m[-2:])
            except: continue
            g_val = 25 if d == 0 else math.ceil(d/4)
            if g_val == g: break
            delay_g += 1
        if delay_g > max_delay: max_delay = delay_g; best_g = g
            
    return best_g, max_delay, desc_oposto

def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        vistos_assinaturas = set() 
        for tab in tabelas:
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th + " " + txt_prev
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
                    vistos_assinaturas.add(assinatura)
                    resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    dt = date.today()
    total_salvos = 0; dados_bancas = {}
    
    for banca_nome, aba_nome in MAPA_ABAS.items():
        res = extrair_dia(banca_nome, dt)
        ws = sh.worksheet(aba_nome)
        
        if res:
            existentes = ws.get_all_values()
            set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
            p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
            if p_ins:
                ws.append_rows(p_ins, value_input_option="RAW")
                total_salvos += len(p_ins)
        
        dados_atualizados = ws.get_all_values()
        if len(dados_atualizados) > 1:
            df = pd.DataFrame(dados_atualizados[1:], columns=["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"])
            df = df[df["P1"].astype(str).str.strip() != ""]
            dados_bancas[banca_nome] = df

    todos_esq = gerar_matrizes_taticas()
    msg_telegram = ""; achou_algo = False; alvos_vistos = set()

    for banca_nome, df in dados_bancas.items():
        if df.empty: continue
        ultimo_sorteio = str(df.iloc[-1]["Sorteio"])

        for i, col in enumerate(COLUNAS_DF):
            if banca_nome == "Tradicional" and col != "P1": continue
            
            # 1. PÊNDULO
            res_pendulo = processar_pendulo(df, col)
            if res_pendulo:
                curr_streak, curr_dir, jogos = res_pendulo
                dir_texto = "Decrescente" if curr_dir == "C" else "Crescente"
                sig_pendulo = f"PENDULO_{banca_nome}_{col}"
                if sig_pendulo not in alvos_vistos:
                    msg_telegram += f"🧲 <b>PÊNDULO ({curr_streak}x)</b>\n🏦 {banca_nome} | 🏆 {TITULOS_PREMIOS[i]}\nDireção: {dir_texto}\nJogar: {', '.join(jogos)}\n\n"
                    achou_algo = True; alvos_vistos.add(sig_pendulo)

            # 2. CAÇA 9D POR ANOMALIA (GATILHO IMEDIATO)
            res_caca = processar_caca_9d_anomalia(df, col)
            if res_caca:
                cold_digit, seq_str, excluido = res_caca
                sig_caca = f"CACA9D_{banca_nome}_{col}"
                if sig_caca not in alvos_vistos:
                    msg_telegram += f"🐺 <b>CAÇA 9D POR ANOMALIA (IMEDIATO)</b>\n🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {TITULOS_PREMIOS[i]}\n⚠️ Gatilho: 2x Centenas Duplicadas Consecutivas\n❄️ Dígito Frio: <b>{cold_digit}</b>\n🎯 <b>Ataque 9D:</b> {seq_str}\n❌ Excluir: {excluido}\n\n"
                    achou_algo = True; alvos_vistos.add(sig_caca)

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
                
                is_anomaly = False; is_alerta = False; tipo_ataque = ""
                
                if am >= 9 and ac >= 9 and ap >= ap_lim: is_anomaly = True; tipo_ataque = "🔥 ATAQUE TOTAL (G+C+M)"
                elif am >= 9: is_anomaly = True; tipo_ataque = f"🔵 ATAQUE MILHAR ({am}x)"
                elif ac >= 9: is_anomaly = True; tipo_ataque = f"🟢 ATAQUE CENTENA ({ac}x)"
                elif ap >= ap_lim: is_anomaly = True; tipo_ataque = f"🟡 ATAQUE FORTE ({cfg['modo'].upper()})"
                elif am >= 7 and ac >= 7 and ap >= (ap_lim - 2): is_alerta = True; tipo_ataque = "🟠 ALERTA: APROXIMAÇÃO TETO TOTAL"
                elif am >= 7: is_alerta = True; tipo_ataque = f"🟠 ALERTA: MILHAR PRÓXIMO AO TETO ({am}/9)"
                elif ac >= 7: is_alerta = True; tipo_ataque = f"🟠 ALERTA: CENTENA PRÓXIMA AO TETO ({ac}/9)"
                elif ap >= (ap_lim - 2): is_alerta = True; tipo_ataque = f"🟠 ALERTA: {cfg['modo'].upper()} PRÓXIMO AO TETO ({ap}/{ap_lim})"

                if is_anomaly or is_alerta:
                    c_min, c_max, m_min, m_max = cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
                    
                    if "MILHAR" in tipo_ataque: sig = f"{banca_nome}_{col}_M_{m_min}"
                    elif "CENTENA" in tipo_ataque: sig = f"{banca_nome}_{col}_C_{c_min}"
                    else: sig = f"{banca_nome}_{col}_{cfg['nome']}"
                    
                    if sig in alvos_vistos: continue
                    alvos_vistos.add(sig)

                    msg_telegram += f"🎯 <b>{tipo_ataque}</b>\n🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {TITULOS_PREMIOS[i]}\nAlvo: <b>{cfg['nome']}</b>\nAtraso Principal: {ap}x\n"
                    msg_telegram += f"Base C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}\nAtraso C: {ac}x | Atraso M: {am}x\n"

                    # -------- RADAR DE RISCO DE ANOMALIA (DRONE) --------
                    if is_anomaly:
                        teto_alvo = 9 if "MILHAR" in tipo_ataque or "CENTENA" in tipo_ataque or "TOTAL" in tipo_ataque else ap_lim
                        # AQUI PUXAMOS A MEMÓRIA DE RECORDE
                        _, _, _, mp_r, mc_r, mm_r = calcular_metricas_fantasma(df, col, cfg) 
                        recorde_alvo = mp_r
                        if "MILHAR" in tipo_ataque: recorde_alvo = mm_r
                        elif "CENTENA" in tipo_ataque: recorde_alvo = mc_r
                        elif "TOTAL" in tipo_ataque: recorde_alvo = max(mp_r, mc_r, mm_r)
                        
                        if recorde_alvo > teto_alvo + 2:
                            espera_sugerida = teto_alvo + 2
                            msg_telegram += f"🚨 <b>PERIGO DE ANOMALIA:</b>\nRecorde Histórico é {recorde_alvo}x. Risco de quebra de Martingale!\n⚠️ Sugestão: Aguarde o atraso bater {espera_sugerida}x ou aplique gestão mínima.\n"
                    # ----------------------------------------------------

                    if cfg['modo'] == 'grupo' and cfg['tipo'] == 'seq':
                        hedge_data = get_hedge_grupos(df, col, cfg, metrics_cache)
                        if hedge_data:
                            elim_str = ", ".join([str(x).zfill(2) for x in hedge_data['eliminar']])
                            mant_str = ", ".join([str(x).zfill(2) for x in hedge_data['manter']])
                            seg_list = [f"D:{str(d).zfill(2)} ({delay}x)" for g, (d, delay) in hedge_data['seguro'].items()]
                            msg_telegram += f"🛡️ <b>Desdobramento:</b>\n❌ Cortar: G {elim_str}\n✅ Jogar: {mant_str}\n🆘 Seguro: {' | '.join(seg_list)}\n"
                        else: msg_telegram += f"🛡️ <b>Desdobramento:</b> Neutro. Jogar Integral.\n"
                    else:
                        cob_data = get_cobertura_massa(df, col, cfg['nome'])
                        if cob_data:
                            g_alvo, delay_g, desc_oposto = cob_data
                            msg_telegram += f"🛡️ <b>Cobertura:</b> O {desc_oposto} mais perigoso é o <b>G{str(g_alvo).zfill(2)}</b> ({delay_g}x).\n🎯 Aposta Sniper nele.\n"
                            
                    msg_telegram += "\n"
                    achou_algo = True

    if achou_algo: enviar_telegram("🛸 <b>DRONE PENTÁGONO - RUPTURAS DETECTADAS</b> 🛸\n\n" + msg_telegram)
    elif total_salvos > 0: enviar_telegram(f"🟢 <b>ROTAÇÃO CONCLUÍDA</b>\n{total_salvos} novos sorteios salvos. Mercado estável.")

if __name__ == "__main__":
    rodar_drone()
