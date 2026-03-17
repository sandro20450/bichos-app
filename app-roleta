import streamlit as st

# 1. TÍTULO DO APLICATIVO
st.title("🎯 Roleta Tracker - 12 Segundos")

# 2. CRIANDO A "MEMÓRIA RÁPIDA"
# Se ainda não existir um histórico na memória, criamos uma lista vazia
if 'historico' not in st.session_state:
    st.session_state.historico = []

# 3. ÁREA DE ENTRADA RÁPIDA (Onde você digita)
numero_sorteado = st.number_input("Digite o número que saiu (0 a 36):", min_value=0, max_value=36, step=1)

# Botão para registrar o número
if st.button("Registrar Número"):
    st.session_state.historico.append(numero_sorteado)

st.write("---") # Linha para separar a tela

# 4. PAINEL DE ANÁLISE E INDICADORES (Componentes Nativos)
st.write("### Análise da Mesa")

# Mostra os números que você já digitou usando um painel azul (st.info)
st.info(f"Últimos números registrados: {st.session_state.historico}")

# A Lógica entra aqui: Só analisa se tivermos pelo menos 5 rodadas registradas
if len(st.session_state.historico) >= 5:
    
    # Pegamos apenas os últimos 5 números da memória
    ultimos_5 = st.session_state.historico[-5:]
    
    # Contamos quantos desses números são da 1ª Dúzia (entre 1 e 12)
    qtd_primeira_duzia = sum(1 for num in ultimos_5 if 1 <= num <= 12)
    
    # Usamos st.metric para criar os Indicadores na tela
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Giros Analisados", value=len(ultimos_5))
    with col2:
        st.metric(label="Saídas da 1ª Dúzia", value=qtd_primeira_duzia)
    
    # A REGRA DE ALERTA VERDE (st.success)
    if qtd_primeira_duzia == 0:
        st.success("🚨 ALERTA DE APOSTA: A 1ª Dúzia não saiu nas últimas 5 rodadas! Considere apostar nela agora.")
    else:
        st.info("Aguardando padrão ideal... Continue registrando os números.")

else:
    # Mensagem enquanto não temos 5 números
    st.info(f"Faltam {5 - len(st.session_state.historico)} rodadas para iniciar a análise dos padrões.")
