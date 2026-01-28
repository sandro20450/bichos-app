import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V3 - Legacy", page_icon="🎯", layout="wide")

CONFIG_BANCAS = {
    "LOTEP": {
        "display_name": "LOTEP (1º ao 5º)",
        "nome_aba": "LOTEP_TOP5",
    },
    "CAMINHODASORTE": {
        "display_name": "CAMINHO (1º ao 5º)",
        "nome_aba": "CAMINHO_TOP5",
    },
    "MONTECAI": {
        "display_name": "MONTE CARLOS (1º ao 5º)",
        "nome_aba": "MONTE_TOP5",
    }
}

# LÓGICA CLÁSSICA (BICHOS APP)
SETORES = {
    "BAIXO (01-08)": list(range(1, 9)),
    "MÉDIO (09-16)": list(range(9, 17)),
    "ALTO (17-24)": list(range(17, 25)),
    "VACA (25)": [25]
}

def aplicar_estilo():
    st.markdown("""
    <style>
        .stMetric { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }
        .box-alerta { background-color: #580000; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; color: #ffcccc; }
        .box-aviso { background-color: #584e00; padding: 15px; border-radius: 8px; border-left: 5px solid #ffd700; margin-bottom: 15px; color: #fffacd; }
        
        /* Estilo das Bolinhas */
        .bola-b { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-m { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-a { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        .bola-v { display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #6f42c1; color: white; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }
        
        /* Tabela Personalizada */
        div[data-testid="stTable"] table { color: white; }
        thead tr th:first-child {display:none}
        tbody th {display:none}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO E DADOS ---
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

# =============================================================================
# --- 3. CÁLCULO DE STRESS (LÓGICA ANTIGA) ---
# =============================================================================
def calcular_stress_tabela(historico, indice_premio):
    """
    Gera a tabela exata: SETOR | ATRASO | REC. ATRASO | REC. SEQ. (V)
    """
    stats = []
    
    for nome_setor, lista_bichos in SETORES.items():
        # Variáveis de cálculo
        max_atraso = 0
        curr_atraso = 0
        max_seq_v = 0
        curr_seq_v = 0
        
        # 1. Varredura Histórica (Recordes)
        for jogo in historico:
            bicho = jogo['premios'][indice_premio]
            
            if bicho in lista_bichos:
                # ACERTOU O SETOR
                curr_seq_v += 1 # Aumenta sequencia de vitoria
                if curr_atraso > max_atraso: max_atraso = curr_atraso # Salva recorde de atraso antes de zerar
                curr_atraso = 0 # Zera atraso
            else:
                # ERROU O SETOR
                curr_atraso += 1 # Aumenta atraso
                if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v # Salva recorde de vitoria antes de zerar
                curr_seq_v = 0 # Zera sequencia vitoria
        
        # Checks finais do loop
        if curr_atraso > max_atraso: max_atraso = curr_atraso
        if curr_seq_v > max_seq_v: max_seq_v = curr_seq_v
        
        # 2. Atraso Real (Contando de trás pra frente)
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

def gerar_bolinhas_recentes(historico, indice_premio):
    # Pega os últimos 12 resultados
    html = "<div>"
    for jogo in reversed(historico[-12:]):
        bicho = jogo['premios'][indice_premio]
        
        classe = ""
        letra = ""
        
        if bicho in SETORES["BAIXO (01-08)"]: 
            classe = "bola-b"; letra = "B"
        elif bicho in SETORES["MÉDIO (09-16)"]: 
            classe = "bola-m"; letra = "M"
        elif bicho in SETORES["ALTO (17-24)"]: 
            classe = "bola-a"; letra = "A"
        elif bicho == 25: 
            classe = "bola-v"; letra = "V"
            
        html += f"<div class='{classe}'>{letra}</div>"
    html += "</div>"
    return html

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
aplicar_estilo()

with st.sidebar:
    st.title("🎯 SNIPER V3")
    banca_selecionada = st.selectbox("Selecione a Banca:", list(CONFIG_BANCAS.keys()))
    st.markdown("---")
    st.info("💡 **Lógica Clássica:**\n- Baixo (01-08)\n- Médio (09-16)\n- Alto (17-24)\n- Vaca (25)")
    if st.button("🔄 Atualizar"): st.rerun()

config = CONFIG_BANCAS[banca_selecionada]
st.header(f"🔭 Análise Clássica (1º ao 5º) - {config['display_name']}")

with st.spinner("Carregando base de dados..."):
    historico = carregar_dados_top5(config['nome_aba'])

if len(historico) > 0:
    ult = historico[-1]
    st.caption(f"📅 Base de Dados: {len(historico)} sorteios. | Último: {ult['data']} às {ult['horario']}")
    
    # --- 1. RADAR DE DISPAROS (TOPO) ---
    st.subheader("🚨 Radar de Disparos")
    
    alertas_encontrados = 0
    nomes_posicoes = ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]
    
    # Grid de Alertas
    col_alerts = st.container()
    
    for idx_pos, nome_pos in enumerate(nomes_posicoes):
        df = calcular_stress_tabela(historico, idx_pos)
        
        for index, row in df.iterrows():
            atraso = row['ATRASO']
            recorde = row['REC. ATRASO']
            setor = row['SETOR']
            
            # Lógica de Alerta (Margem de 1 ou estourado)
            # Para a Vaca (25), como demora muito, exigimos recorde > 15 para alertar
            min_rec = 15 if "VACA" in setor else 5
            
            if (recorde - atraso) <= 1 and recorde >= min_rec:
                alertas_encontrados += 1
                
                classe = "box-alerta" if atraso >= recorde else "box-aviso"
                msg_extra = "**ESTOURADO!**" if atraso >= recorde else "Zona de Tiro"
                
                with col_alerts:
                    st.markdown(f"""
                    <div class="{classe}">
                        <b>{nome_pos} | {setor}</b><br>
                        Atraso: {atraso} (Recorde: {recorde}) - {msg_extra}
                    </div>
                    """, unsafe_allow_html=True)
    
    if alertas_encontrados == 0:
        st.success("✅ Mercado Estável. Nenhuma oportunidade crítica encontrada.")
    
    st.markdown("---")

    # --- 2. ABAS DETALHADAS ---
    abas = st.tabs(nomes_posicoes)
    
    for idx_aba, aba in enumerate(abas):
        with aba:
            st.markdown(f"### 📊 Raio-X: {nomes_posicoes[idx_aba]}")
            
            # VISUAL RECENTE (BOLINHAS)
            st.markdown("**Visual Recente (⬅️ Mais Novo):**")
            st.markdown(gerar_bolinhas_recentes(historico, idx_aba), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # TABELA DE STRESS
            st.markdown("**📉 Tabela de Stress (Atraso vs Recorde):**")
            df_stats = calcular_stress_tabela(historico, idx_aba)
            st.table(df_stats)
            
            # Explicação da Vaca
            if "VACA (25)" in df_stats['SETOR'].values:
                row_vaca = df_stats[df_stats['SETOR'] == "VACA (25)"].iloc[0]
                if row_vaca['ATRASO'] > 20:
                    st.info(f"ℹ️ **Nota sobre a Vaca:** Ela está com atraso de {row_vaca['ATRASO']}. Lembre-se que ela sai menos vezes estatisticamente (1 chance em 25). Só jogue se estiver próxima do recorde histórico ({row_vaca['REC. ATRASO']}).")

else:
    st.warning("⚠️ Base de dados vazia. Use o Robô Extrator primeiro.")
