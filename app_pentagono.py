import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="PENTÁGONO V2 - Sniper", page_icon="🎯", layout="wide")

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

# LÓGICA DE SETORES EQUILIBRADOS (ROUND ROBIN 1-2-3)
# Garantia de que nenhum setor fique viciado em numeros altos ou baixos
SETORES = {
    "S1": [1, 4, 7, 10, 13, 16, 19, 22, 25],
    "S2": [2, 5, 8, 11, 14, 17, 20, 23],
    "S3": [3, 6, 9, 12, 15, 18, 21, 24]
}

def aplicar_estilo():
    st.markdown("""
    <style>
        .stMetric { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }
        .box-alerta { background-color: #580000; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; color: #ffcccc; }
        .box-aviso { background-color: #584e00; padding: 15px; border-radius: 8px; border-left: 5px solid #ffd700; margin-bottom: 15px; color: #fffacd; }
        h1, h2, h3 { color: #ffffff !important; }
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
            # Garante que tem data, hora e 5 premios
            if len(row) >= 7:
                try:
                    # Tenta converter as colunas 2,3,4,5,6 para int
                    premios = [int(p) for p in row[2:7] if p.isdigit()]
                    if len(premios) == 5:
                        dados_processados.append({
                            "data": row[0],
                            "horario": row[1],
                            "premios": premios # [P1, P2, P3, P4, P5]
                        })
                except: pass
        return dados_processados
    return []

# =============================================================================
# --- 3. CÁLCULO DE STRESS POR POSIÇÃO (LÓGICA SNIPER) ---
# =============================================================================
def calcular_stress_individual(historico, indice_premio):
    """
    Analisa apenas uma coluna verticalmente (ex: só o 4º prêmio de todos os dias).
    indice_premio: 0=1º, 1=2º, 2=3º, 3=4º, 4=5º
    """
    stats = {}
    
    for nome_setor, lista_bichos in SETORES.items():
        recorde_atraso = 0
        tmp_atraso = 0
        
        # 1. Calcula o Recorde Histórico (Varrendo do passado pro presente)
        for jogo in historico:
            bicho_na_posicao = jogo['premios'][indice_premio]
            
            if bicho_na_posicao in lista_bichos:
                # Setor saiu nesta posição -> Zera contagem temporária
                if tmp_atraso > recorde_atraso: recorde_atraso = tmp_atraso
                tmp_atraso = 0
            else:
                # Setor não saiu -> Aumenta contagem
                tmp_atraso += 1
        
        # Checagem final do loop
        if tmp_atraso > recorde_atraso: recorde_atraso = tmp_atraso
        
        # 2. Calcula o Atraso Atual (Varrendo do presente pro passado até achar a última saída)
        atraso_real = 0
        for jogo in reversed(historico):
            bicho_na_posicao = jogo['premios'][indice_premio]
            if bicho_na_posicao in lista_bichos:
                break # Encontrou a última vez que saiu, para de contar
            atraso_real += 1
            
        stats[nome_setor] = {
            "atraso": atraso_real,
            "recorde": recorde_atraso
        }
        
    return stats

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
aplicar_estilo()

with st.sidebar:
    st.title("🎯 SNIPER V2")
    banca_selecionada = st.selectbox("Selecione a Banca:", list(CONFIG_BANCAS.keys()))
    st.markdown("---")
    
    st.info("💡 **Dica:** Este app analisa cada prêmio individualmente. Se o radar apontar o 4º Prêmio, jogue APENAS no 4º Prêmio.")
    
    if st.button("🔄 Atualizar"): st.rerun()

config = CONFIG_BANCAS[banca_selecionada]
st.header(f"🔭 Análise Individual (1º ao 5º) - {config['display_name']}")

with st.spinner("Carregando base de dados e calculando estatísticas..."):
    historico = carregar_dados_top5(config['nome_aba'])

if len(historico) > 0:
    ult = historico[-1]
    st.caption(f"📅 Base de Dados: {len(historico)} sorteios carregados. | Último registro: {ult['data']} às {ult['horario']}")
    
    # --- 1. RADAR DE OPORTUNIDADES (TOPO) ---
    st.subheader("🚨 Radar de Disparos")
    
    alertas_encontrados = 0
    nomes_posicoes = ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]
    
    # Grid de Alertas
    for idx_pos, nome_pos in enumerate(nomes_posicoes):
        dados_pos = calcular_stress_individual(historico, idx_pos)
        
        for setor, info in dados_pos.items():
            atraso = info['atraso']
            recorde = info['recorde']
            margem = recorde - atraso
            
            # LÓGICA DE TIRO: 
            # Se o atraso estiver IGUAL ou MAIOR que o recorde, ou FALTANDO 1 para bater.
            # (Filtro: Recorde deve ser pelo menos 5 para evitar falsos positivos de início de planilha)
            if margem <= 1 and recorde >= 5:
                alertas_encontrados += 1
                
                if margem <= 0:
                    classe = "box-alerta"
                    icone = "🔥"
                    txt_extra = "**ESTOURADO!** (Bateu/Passou Recorde)"
                else:
                    classe = "box-aviso"
                    icone = "⚠️"
                    txt_extra = "Zona de Tiro (Falta 1)"
                
                st.markdown(f"""
                <div class="{classe}">
                    <h3>{icone} {nome_pos} -> {setor}</h3>
                    <p><b>Atraso Atual: {atraso}</b> | Recorde Histórico: {recorde}</p>
                    <p>{txt_extra}</p>
                </div>
                """, unsafe_allow_html=True)
    
    if alertas_encontrados == 0:
        st.success("✅ Mercado Estável: Nenhuma oportunidade crítica encontrada no momento.")
    
    st.markdown("---")

    # --- 2. ABAS DETALHADAS ---
    st.subheader("📊 Detalhes por Posição")
    abas = st.tabs(nomes_posicoes)
    
    for idx_aba, aba in enumerate(abas):
        with aba:
            st.markdown(f"#### Estatísticas do {nomes_posicoes[idx_aba]}")
            stats = calcular_stress_individual(historico, idx_aba)
            
            c1, c2, c3 = st.columns(3)
            
            def render_card(col, titulo, dados, cor):
                at = dados['atraso']
                rec = dados['recorde']
                # Evita divisão por zero
                progresso = at / rec if rec > 0 else 0
                progresso = min(1.0, progresso)
                
                with col:
                    st.markdown(f"<h4 style='color:{cor}; text-align:center;'>{titulo}</h4>", unsafe_allow_html=True)
                    st.metric("Atraso", f"{at}", delta=f"Recorde: {rec}", delta_color="off")
                    st.progress(progresso)
            
            render_card(c1, "Setor 1 (S1)", stats["S1"], "#17a2b8")
            render_card(c2, "Setor 2 (S2)", stats["S2"], "#fd7e14")
            render_card(c3, "Setor 3 (S3)", stats["S3"], "#dc3545")
            
            with st.expander("🔍 Ver Grupos deste Setor"):
                st.write("**🔵 S1:** 1, 4, 7, 10, 13, 16, 19, 22, 25")
                st.write("**🟠 S2:** 2, 5, 8, 11, 14, 17, 20, 23")
                st.write("**🔴 S3:** 3, 6, 9, 12, 15, 18, 21, 24")

else:
    st.warning("⚠️ Base de dados vazia ou incompleta. Use o 'Robô Extrator' para preencher a planilha primeiro.")
