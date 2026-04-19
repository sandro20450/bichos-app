import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import math
from datetime import date, timedelta

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="Pentágono - Tático", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    div[data-testid="metric-container"] { background-color: #2b2b2b; border-left: 5px solid #4CAF50; padding: 15px; border-radius: 5px; }
    .btn-extrator > button { background-color: #008CBA !important; color: white !important; }
    div[data-baseweb="input"] { background-color: #2b2b2b !important; color: white !important;}
    
    .alerta-sniper {
        background-color: #2b0000;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        color: #ff4b4b;
        font-size: 1.3em;
        border: 2px solid #ff4b4b;
        box-shadow: 0px 0px 20px rgba(255, 75, 75, 0.4);
        margin-top: 20px;
    }
    .alerta-calmo {
        background-color: #002b0c;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        color: #4CAF50;
        border: 1px solid #4CAF50;
        margin-top: 20px;
    }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Táticas")
st.markdown("### Estratégia: Cerco de Repetição (125 Duques)")

# MAPEAMENTO TÁTICO DE HORÁRIOS
HORARIOS_FIXOS = ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"]

# =============================================================================
# --- 2. O MOTOR EXTRATOR CIBERNÉTICO ---
# =============================================================================
def extrair_resultados_web(data_alvo):
    data_formatada = data_alvo.strftime("%Y-%m-%d")
    url = f"https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-{data_formatada}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        if resposta.status_code != 200:
            return None, f"O radar foi bloqueado ou a data não existe (Erro {resposta.status_code})."

        soup = BeautifulSoup(resposta.text, 'html.parser')
        tabelas = soup.find_all('table')
        dados_temporarios = []
        
        for tabela in tabelas:
            linhas = tabela.find_all('tr')
            grupos_extraidos = []
            
            for linha in linhas:
                colunas = linha.find_all(['td', 'th'])
                textos = [c.get_text(strip=True) for c in colunas]
                if not textos: continue
                
                primeira_col = textos[0].lower()
                if any(x in primeira_col for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    grupo = ""
                    for txt in textos[1:]:
                        nums = ''.join(filter(str.isdigit, txt))
                        if 0 < len(nums) <= 2:
                            grupo = nums.zfill(2)
                            break
                    if not grupo:
                        for txt in textos[1:]:
                            nums = ''.join(filter(str.isdigit, txt))
                            if len(nums) >= 3: 
                                dezena = int(nums[-2:])
                                grupo_calc = 25 if dezena == 0 else math.ceil(dezena / 4)
                                grupo = str(grupo_calc).zfill(2)
                                break
                    if grupo: grupos_extraidos.append(grupo)
            
            if len(grupos_extraidos) >= 5:
                dados_temporarios.append(grupos_extraidos)
                
        novos_dados = {"Sorteio": [], "1º Prêmio": [], "2º Prêmio": [], "3º Prêmio": [], "4º Prêmio": [], "5º Prêmio": [], "Status": []}
        
        for i in range(10):
            hora_fixa = HORARIOS_FIXOS[i]
            nome_sorteio = f"{hora_fixa} ({data_alvo.strftime('%d/%m')})"
            novos_dados["Sorteio"].append(nome_sorteio)
            
            if i < len(dados_temporarios):
                grupos = dados_temporarios[i]
                novos_dados["1º Prêmio"].append(grupos[0])
                novos_dados["2º Prêmio"].append(grupos[1])
                novos_dados["3º Prêmio"].append(grupos[2])
                novos_dados["4º Prêmio"].append(grupos[3])
                novos_dados["5º Prêmio"].append(grupos[4])
                novos_dados["Status"].append("⏳")
            else:
                for col in ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio", "Status"]:
                    novos_dados[col].append("⏳" if col == "Status" else "")
                
        if len(dados_temporarios) > 0:
            return pd.DataFrame(novos_dados), "Sucesso"
        else:
            return None, f"Sem dados para o dia {data_alvo.strftime('%d/%m/%Y')}."
            
    except Exception as e:
        return None, f"Falha crítica nos motores de busca: {e}"

# =============================================================================
# --- 3. INICIALIZAÇÃO DAS TABELAS NO COFRE ---
# =============================================================================
def criar_df_vazio(horarios, data_str):
    return pd.DataFrame({
        "Sorteio": [f"{h} ({data_str})" for h in horarios],
        "1º Prêmio": [""] * len(horarios), "2º Prêmio": [""] * len(horarios),
        "3º Prêmio": [""] * len(horarios), "4º Prêmio": [""] * len(horarios),
        "5º Prêmio": [""] * len(horarios), "Status": ["⏳"] * len(horarios)
    })

if 'df_anterior' not in st.session_state:
    st.session_state.df_anterior = criar_df_vazio(HORARIOS_FIXOS[-5:], (date.today() - timedelta(days=2)).strftime('%d/%m'))

if 'df_atual' not in st.session_state:
    st.session_state.df_atual = criar_df_vazio(HORARIOS_FIXOS, (date.today() - timedelta(days=1)).strftime('%d/%m'))


# =============================================================================
# --- 4. INTERFACE: PAINEL SUPERIOR (DIA ANTERIOR) ---
# =============================================================================
st.markdown("### ⏪ 1. O Elo de Ligação (Fechamento de Ontem)")
c_ant1, c_ant2, c_ant3 = st.columns([1, 1, 2])
with c_ant1:
    data_anterior = st.date_input("Data do Dia Anterior:", value=date.today() - timedelta(days=2), key="data_ant")
with c_ant2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Fechamento Anterior", use_container_width=True):
        with st.spinner("Puxando o histórico de ontem..."):
            df_novo, msg = extrair_resultados_web(data_anterior)
            if df_novo is not None:
                # O PULO DO GATO: Corta apenas as últimas 5 linhas (da 19:20 às 23:20)
                st.session_state.df_anterior = df_novo.tail(5).reset_index(drop=True)
                st.rerun()
            else:
                st.error(f"⚠️ {msg}")
with c_ant3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.8em;'>Puxa apenas os últimos 5 sorteios para sabermos como a banca fechou o dia. O resultado das 23:20 alimentará o cálculo das 11:20 de hoje.</span>", unsafe_allow_html=True)

df_ant_editado = st.data_editor(st.session_state.df_anterior, use_container_width=True, hide_index=True, column_config={"Status": st.column_config.TextColumn("Resultado", disabled=True)})
st.session_state.df_anterior = df_ant_editado

st.markdown("<hr>", unsafe_allow_html=True)

# =============================================================================
# --- 5. INTERFACE: PAINEL INFERIOR (DIA ATUAL) ---
# =============================================================================
st.markdown("### 🎯 2. Painel de Operação (Dia de Hoje)")
c_atu1, c_atu2, c_atu3 = st.columns([1, 1, 2])
with c_atu1:
    data_atual = st.date_input("Data do Dia Principal:", value=date.today() - timedelta(days=1), key="data_atu")
with c_atu2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='btn-extrator'>", unsafe_allow_html=True)
    if st.button("📡 Puxar Dia Principal", use_container_width=True):
        with st.spinner("Puxando extrações completas..."):
            df_novo, msg = extrair_resultados_web(data_atual)
            if df_novo is not None:
                st.session_state.df_atual = df_novo
                st.rerun()
            else:
                st.error(f"⚠️ {msg}")
    st.markdown("</div>", unsafe_allow_html=True)
with c_atu3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.8em;'>Tabela principal com 10 extrações e controle de Sniper.</span>", unsafe_allow_html=True)

# =============================================================================
# --- 6. MOTOR LÓGICO DE FUSÃO E BACKTEST ---
# =============================================================================
df_ant = st.session_state.df_anterior.copy()
df_atu = st.session_state.df_atual.copy()

derrotas_consecutivas = 0

# AVALIA A TABELA SUPERIOR (Para acumular as derrotas antes de o dia começar)
if len(df_ant) > 0:
    df_ant.at[0, "Status"] = "---" # A primeira visível do dia anterior não avaliamos
    for i in range(1, len(df_ant)):
        l_ant = df_ant.iloc[i-1]
        l_atu = df_ant.iloc[i]
        
        if not l_ant["1º Prêmio"] or not l_atu["1º Prêmio"]:
            df_ant.at[i, "Status"] = "⏳"
            continue
            
        g_base = [str(l_ant[f"{p}º Prêmio"]).strip().zfill(2) for p in range(1, 6)]
        a_1, a_2 = str(l_atu["1º Prêmio"]).strip().zfill(2), str(l_atu["2º Prêmio"]).strip().zfill(2)
        
        if a_1 in g_base or a_2 in g_base:
            df_ant.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0
        else:
            df_ant.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1

# AVALIA A TABELA INFERIOR (O Dia Principal - Interligado!)
vitorias_dia = 0
derrotas_dia = 0

for i in range(len(df_atu)):
    # A MÁGICA DA CONEXÃO: Se for a linha 0 (11:20), a linha anterior é a última das 23:20 da tabela de cima!
    if i == 0:
        linha_anterior = df_ant.iloc[-1]
    else:
        linha_anterior = df_atu.iloc[i-1]
        
    linha_atual = df_atu.iloc[i]
    
    if not linha_anterior["1º Prêmio"] or not linha_atual["1º Prêmio"]:
        df_atu.at[i, "Status"] = "⏳"
        continue
        
    try:
        grupos_base = [str(linha_anterior[f"{p}º Prêmio"]).strip().zfill(2) for p in range(1, 6)]
        alvo_1, alvo_2 = str(linha_atual["1º Prêmio"]).strip().zfill(2), str(linha_atual["2º Prêmio"]).strip().zfill(2)
        
        if alvo_1 in grupos_base or alvo_2 in grupos_base:
            df_atu.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0 
            vitorias_dia += 1
        else:
            df_atu.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1 
            derrotas_dia += 1
    except:
        df_atu.at[i, "Status"] = "⏳"

# Exibe a tabela inferior
df_atu_editado = st.data_editor(df_atu, use_container_width=True, hide_index=True, column_config={"Status": st.column_config.TextColumn("Resultado", disabled=True)})
st.session_state.df_atual = df_atu_editado

# Atualiza os displays para refletir a matemática da fusão
st.session_state.df_anterior = df_ant

# =============================================================================
# --- 7. O GATILHO DE OPORTUNIDADE (SNIPER) ---
# =============================================================================
if derrotas_consecutivas >= 4:
    st.markdown(f"""
    <div class="alerta-sniper">
        <b>🚨 ALERTA DE OPORTUNIDADE TÁTICA 🚨</b><br>
        O radar detectou <b>{derrotas_consecutivas} derrotas consecutivas</b> acumuladas na passagem dos sorteios!<br>
        A janela estatística de acerto está aberta. Prepare-se para atacar no próximo horário!
    </div>
    """, unsafe_allow_html=True)
elif derrotas_consecutivas > 0:
    st.markdown(f"""
    <div class="alerta-calmo" style="color: #ffb74d; border-color: #ffb74d;">
        <b>Aviso de Monitoramento:</b> A acumular {derrotas_consecutivas} derrota(s) seguida(s). Aguardando a quebra do padrão...
    </div>
    """, unsafe_allow_html=True)
else:
    # Checa se há vitórias recentes
    if vitorias_dia > 0 or (len(df_ant) > 0 and df_ant.iloc[-1]["Status"] == "🟢 Vitória"):
        st.markdown("""
        <div class="alerta-calmo">
            <b>Status Verde:</b> Tabela estabilizada após Vitória. Mantenha as armas em repouso até nova janela de oportunidade.
        </div>
        """, unsafe_allow_html=True)
