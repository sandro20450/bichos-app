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
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Táticas")
st.markdown("### Estratégia: Cerco de Repetição (125 Duques)")

# MAPEAMENTO TÁTICO DE HORÁRIOS DEFINIDO PELO COMANDANTE (Exatamente 10 sorteios)
HORARIOS_FIXOS = ["11:20", "12:20", "13:20", "14:20", "18:20", "19:20", "20:20", "21:20", "22:20", "23:20"]

# =============================================================================
# --- 2. O EXTRATOR CIBERNÉTICO (INVERTIDO E CORRIGIDO) ---
# =============================================================================
def extrair_resultados_web(data_alvo):
    data_formatada = data_alvo.strftime("%Y-%m-%d")
    url = f"https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-{data_formatada}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        if resposta.status_code != 200:
            return None, f"O radar foi bloqueado ou a data não existe (Erro {resposta.status_code})."

        soup = BeautifulSoup(resposta.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        # Primeiro, extraímos todos os grupos válidos encontrados no site para uma lista temporária
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
                
        # O PULO DO GATO: O site mostra o mais recente primeiro. Nós precisamos inverter
        # para que o sorteio mais antigo do dia (11:20) seja o primeiro da lista.
        dados_temporarios.reverse()
        
        # Agora montamos a estrutura final com exatamente 10 linhas
        novos_dados = {
            "Sorteio": [], "1º Prêmio": [], "2º Prêmio": [], 
            "3º Prêmio": [], "4º Prêmio": [], "5º Prêmio": [], "Status": []
        }
        
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
                novos_dados["1º Prêmio"].append("")
                novos_dados["2º Prêmio"].append("")
                novos_dados["3º Prêmio"].append("")
                novos_dados["4º Prêmio"].append("")
                novos_dados["5º Prêmio"].append("")
                novos_dados["Status"].append("⏳")
                
        # Se achou pelo menos 1 tabela, retorna sucesso
        if len(dados_temporarios) > 0:
            return pd.DataFrame(novos_dados), "Sucesso"
        else:
            return None, f"Não há resultados registados para o dia {data_alvo.strftime('%d/%m/%Y')}."
            
    except Exception as e:
        return None, f"Falha crítica nos motores de busca: {e}"

# =============================================================================
# --- 3. DADOS INICIAIS E INTERFACE ---
# =============================================================================
if 'df_backtest' not in st.session_state:
    data_hoje = date.today().strftime('%d/%m')
    dados_iniciais = {
        "Sorteio": [f"{h} ({data_hoje})" for h in HORARIOS_FIXOS],
        "1º Prêmio": [""] * 10, "2º Prêmio": [""] * 10,
        "3º Prêmio": [""] * 10, "4º Prêmio": [""] * 10, "5º Prêmio": [""] * 10,
        "Status": ["⏳"] * 10
    }
    st.session_state.df_backtest = pd.DataFrame(dados_iniciais)

st.markdown("### 📅 Painel de Extração")
c1, c2, c3 = st.columns([1, 1, 2])

with c1:
    data_selecionada = st.date_input("Data do Sorteio:", value=date.today() - timedelta(days=1))

with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='btn-extrator'>", unsafe_allow_html=True)
    if st.button("📡 Puxar Resultados", use_container_width=True):
        with st.spinner(f"A varrer dados do dia {data_selecionada.strftime('%d/%m')}..."):
            df_novo, msg = extrair_resultados_web(data_selecionada)
            time.sleep(1) 
            if df_novo is not None:
                st.session_state.df_backtest = df_novo
                st.success("✅ Radar sincronizado perfeitamente!")
                st.rerun()
            else:
                st.error(f"⚠️ Alerta: {msg}")
    st.markdown("</div>", unsafe_allow_html=True)

with c3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.85em;'>O Extrator fixa as 10 extrações diárias e procura ativamente a Janela de Oportunidade.</span>", unsafe_allow_html=True)

st.markdown("---")

# =============================================================================
# --- 4. MOTOR DE BACKTEST (COM CONTADOR DE DERROTAS) ---
# =============================================================================
df_atual = st.session_state.df_backtest.copy()

if len(df_atual) > 0:
    df_atual.at[0, "Status"] = "---"

# Variável estratégica para contar as derrotas seguidas
derrotas_consecutivas = 0

for i in range(1, len(df_atual)):
    linha_anterior = df_atual.iloc[i-1]
    linha_atual = df_atual.iloc[i]
    
    if not linha_anterior["1º Prêmio"] or not linha_atual["1º Prêmio"]:
        df_atual.at[i, "Status"] = "⏳"
        continue
        
    try:
        grupos_base = [
            str(linha_anterior["1º Prêmio"]).strip().zfill(2),
            str(linha_anterior["2º Prêmio"]).strip().zfill(2),
            str(linha_anterior["3º Prêmio"]).strip().zfill(2),
            str(linha_anterior["4º Prêmio"]).strip().zfill(2),
            str(linha_anterior["5º Prêmio"]).strip().zfill(2)
        ]
        
        alvo_1 = str(linha_atual["1º Prêmio"]).strip().zfill(2)
        alvo_2 = str(linha_atual["2º Prêmio"]).strip().zfill(2)
        
        if alvo_1 in grupos_base or alvo_2 in grupos_base:
            df_atual.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0 # O ciclo zerou!
        else:
            df_atual.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1 # Conta mais uma derrota seguida
    except:
        df_atual.at[i, "Status"] = "⏳"

# Exibe a tabela na tela
st.markdown("#### 📝 Placard Tático Interativo")
df_editado = st.data_editor(
    df_atual,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Status": st.column_config.TextColumn("Resultado", disabled=True)
    }
)

st.session_state.df_backtest = df_editado

# =============================================================================
# --- 5. O GATILHO DE OPORTUNIDADE (SNIPER) ---
# =============================================================================
# Removemos o painel financeiro e colocamos o Alerta Tático
if derrotas_consecutivas >= 4:
    st.markdown(f"""
    <div class="alerta-sniper">
        <b>🚨 ALERTA DE OPORTUNIDADE TÁTICA 🚨</b><br>
        O radar detectou <b>{derrotas_consecutivas} derrotas consecutivas</b> no histórico recente!<br>
        A janela estatística de acerto está aberta. Prepare-se para atacar no próximo sorteio!
    </div>
    """, unsafe_allow_html=True)
elif derrotas_consecutivas > 0:
    st.markdown(f"""
    <div class="alerta-calmo" style="color: #ffb74d; border-color: #ffb74d;">
        <b>Aviso de Monitoramento:</b> A acumular {derrotas_consecutivas} derrota(s) seguida(s). Aguardando a quebra do padrão...
    </div>
    """, unsafe_allow_html=True)
else:
    # Se a última foi Vitória ou se ainda não tem dados
    tem_dados = False
    for s in df_atual["Status"]:
        if s == "🟢 Vitória" or s == "❌ Derrota":
            tem_dados = True
            break
            
    if tem_dados:
        st.markdown("""
        <div class="alerta-calmo">
            <b>Status Verde:</b> Tabela estabilizada após Vitória. Mantenha as armas em repouso até nova janela de oportunidade.
        </div>
        """, unsafe_allow_html=True)
