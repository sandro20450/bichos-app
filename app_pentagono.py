import streamlit as st
import pandas as pd

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="Pentágono - Backtest", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; }
    div[data-testid="metric-container"] { background-color: #2b2b2b; border-left: 5px solid #4CAF50; padding: 15px; border-radius: 5px; }
    .vitoria { color: #4CAF50; font-weight: bold; }
    .derrota { color: #FF5252; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Táticas")
st.markdown("### Estratégia: Cerco de Repetição (125 Duques)")
st.write("Insira os grupos sorteados (de 01 a 25) nas últimas extrações para testar a sua teoria.")

# =============================================================================
# --- 2. DADOS INICIAIS DA TABELA ---
# =============================================================================
# Criando uma tabela vazia com 11 linhas para simular 10 transições
if 'df_backtest' not in st.session_state:
    dados_iniciais = {
        "Sorteio": [f"Extração {i}" for i in range(1, 12)],
        "1º Prêmio": ["02"] + [""] * 10,
        "2º Prêmio": ["15"] + [""] * 10,
        "3º Prêmio": ["17"] + [""] * 10,
        "4º Prêmio": ["22"] + [""] * 10,
        "5º Prêmio": ["01"] + [""] * 10
    }
    st.session_state.df_backtest = pd.DataFrame(dados_iniciais)

st.markdown("#### 📝 Preencha os Resultados Oficiais:")
df_editado = st.data_editor(st.session_state.df_backtest, use_container_width=True, hide_index=True)

# =============================================================================
# --- 3. MOTOR DE BACKTEST (LÓGICA) ---
# =============================================================================
if st.button("🚀 Executar Backtest Completo", use_container_width=True):
    vitorias = 0
    derrotas = 0
    custo_por_rodada = 125.00
    premio_por_vitoria = 255.00
    
    st.markdown("---")
    st.markdown("### 📊 Relatório de Transições")
    
    # Varrendo as 10 transições (da linha 0 até a linha 9)
    for i in range(10):
        linha_atual = df_editado.iloc[i]
        linha_futura = df_editado.iloc[i+1]
        
        # Verifica se as linhas estão preenchidas
        if linha_atual["1º Prêmio"] == "" or linha_futura["1º Prêmio"] == "":
            continue # Pula se o usuário não preencheu ainda
            
        try:
            # Pega os 5 grupos do sorteio atual
            grupos_base = [
                str(linha_atual["1º Prêmio"]).strip().zfill(2),
                str(linha_atual["2º Prêmio"]).strip().zfill(2),
                str(linha_atual["3º Prêmio"]).strip().zfill(2),
                str(linha_atual["4º Prêmio"]).strip().zfill(2),
                str(linha_atual["5º Prêmio"]).strip().zfill(2)
            ]
            
            # Pega os 2 primeiros prêmios do sorteio seguinte
            alvo_1 = str(linha_futura["1º Prêmio"]).strip().zfill(2)
            alvo_2 = str(linha_futura["2º Prêmio"]).strip().zfill(2)
            
            # REGRA DE VITÓRIA: Se o alvo 1 OU o alvo 2 estiverem dentro dos grupos base
            if alvo_1 in grupos_base or alvo_2 in grupos_base:
                status = "VITÓRIA"
                vitorias += 1
                cor = "#4CAF50"
            else:
                status = "DERROTA"
                derrotas += 1
                cor = "#FF5252"
                
            st.markdown(f"<div style='background-color: #2b2b2b; padding: 10px; margin-bottom: 5px; border-radius: 5px;'>"
                        f"Analisando <b style='color:#aaa;'>{linha_atual['Sorteio']}</b> ➔ <b style='color:#aaa;'>{linha_futura['Sorteio']}</b> <br>"
                        f"Buscando repetição de: {grupos_base} <br>"
                        f"Resultado do novo sorteio (1º e 2º): ['{alvo_1}', '{alvo_2}'] <br>"
                        f"Status: <b style='color: {cor};'>{status}</b></div>", 
                        unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Erro ao processar a linha {i+1}. Verifique se digitou apenas números.")

    # =============================================================================
    # --- 4. RESULTADO FINANCEIRO ---
    # =============================================================================
    total_jogos = vitorias + derrotas
    
    if total_jogos > 0:
        custo_total = total_jogos * custo_por_rodada
        retorno_total = vitorias * premio_por_vitoria
        lucro_liquido = retorno_total - custo_total
        assertividade = (vitorias / total_jogos) * 100
        
        st.markdown("---")
        st.markdown("### 💰 Balanço Geral do Dia")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Análises", f"{total_jogos}")
        col2.metric("Assertividade", f"{assertividade:.1f}%")
        col3.metric("Investimento Total", f"R$ {custo_total:.2f}")
        
        if lucro_liquido > 0:
            col4.metric("Lucro Líquido", f"R$ {lucro_liquido:.2f}")
        else:
            col4.metric("Prejuízo", f"R$ {lucro_liquido:.2f}")
