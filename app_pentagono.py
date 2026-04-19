import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import math

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="Pentágono - Backtest Auto", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    div[data-testid="metric-container"] { background-color: #2b2b2b; border-left: 5px solid #4CAF50; padding: 15px; border-radius: 5px; }
    .btn-extrator > button { background-color: #008CBA !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Táticas")
st.markdown("### Estratégia: Cerco de Repetição (125 Duques)")

# =============================================================================
# --- 2. O EXTRATOR CIBERNÉTICO (ALVO: PLAYBICHO) ---
# =============================================================================
def extrair_resultados_web():
    # Novo alvo definido pelo Comandante
    url = "https://playbicho.com/resultado-jogo-do-bicho/tradicional-de-hoje"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        
        if resposta.status_code != 200:
            return None, f"O novo radar foi bloqueado pelo servidor (Erro {resposta.status_code})."

        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        novos_dados = {
            "Sorteio": [], "1º Prêmio": [], "2º Prêmio": [], 
            "3º Prêmio": [], "4º Prêmio": [], "5º Prêmio": []
        }
        
        tabelas = soup.find_all('table')
        count = 1
        
        for tabela in tabelas:
            linhas = tabela.find_all('tr')
            grupos_extraidos = []
            
            for linha in linhas:
                colunas = linha.find_all(['td', 'th'])
                textos = [c.get_text(strip=True) for c in colunas]
                
                if not textos: continue
                
                primeira_col = textos[0].lower()
                # Verifica se a linha pertence ao 1º ao 5º prémio
                if any(x in primeira_col for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    grupo = ""
                    
                    # TENTA TÁTICA A: Achar uma coluna que seja apenas o grupo (1 ou 2 dígitos isolados)
                    for txt in textos[1:]:
                        nums = ''.join(filter(str.isdigit, txt))
                        if 0 < len(nums) <= 2:
                            grupo = nums.zfill(2)
                            break
                            
                    # TENTA TÁTICA B (Matemática): Se o site escondeu o grupo, calcula através da Milhar
                    if not grupo:
                        for txt in textos[1:]:
                            nums = ''.join(filter(str.isdigit, txt))
                            if len(nums) >= 3: # Identificou a centena/milhar
                                dezena = int(nums[-2:]) # Pega as duas últimas casas
                                if dezena == 0:
                                    grupo_calc = 25
                                else:
                                    grupo_calc = math.ceil(dezena / 4)
                                grupo = str(grupo_calc).zfill(2)
                                break
                                
                    if grupo:
                        grupos_extraidos.append(grupo)
            
            # Se capturou os 5 prémios desta extração, guarda os dados
            if len(grupos_extraidos) >= 5:
                novos_dados["Sorteio"].append(f"Extração {count} (PlayBicho)")
                novos_dados["1º Prêmio"].append(grupos_extraidos[0])
                novos_dados["2º Prêmio"].append(grupos_extraidos[1])
                novos_dados["3º Prêmio"].append(grupos_extraidos[2])
                novos_dados["4º Prêmio"].append(grupos_extraidos[3])
                novos_dados["5º Prêmio"].append(grupos_extraidos[4])
                count += 1
                if count > 11: break # Precisamos apenas de 11 extrações para 10 testes
        
        if len(novos_dados["Sorteio"]) > 0:
            # Preenche o resto com linhas vazias caso o dia ainda esteja a começar e não haja 11 sorteios
            while len(novos_dados["Sorteio"]) < 11:
                idx = len(novos_dados["Sorteio"]) + 1
                novos_dados["Sorteio"].append(f"Extração {idx} (Pendente)")
                for pr in ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio"]:
                    novos_dados[pr].append("")
                    
            return pd.DataFrame(novos_dados), "Sucesso"
        else:
            return None, "As tabelas do PlayBicho foram encontradas, mas os números estão ilegíveis para o radar."
            
    except Exception as e:
        return None, f"Falha crítica nos motores de busca: {e}"

# =============================================================================
# --- 3. DADOS INICIAIS E INTERFACE ---
# =============================================================================
if 'df_backtest' not in st.session_state:
    dados_iniciais = {
        "Sorteio": [f"Extração {i}" for i in range(1, 12)],
        "1º Prêmio": [""] * 11, "2º Prêmio": [""] * 11,
        "3º Prêmio": [""] * 11, "4º Prêmio": [""] * 11, "5º Prêmio": [""] * 11
    }
    st.session_state.df_backtest = pd.DataFrame(dados_iniciais)

c1, c2 = st.columns([1, 3])
with c1:
    st.markdown("<div class='btn-extrator'>", unsafe_allow_html=True)
    if st.button("📡 Puxar Resultados (Auto)"):
        with st.spinner("A invadir os servidores do PlayBicho..."):
            df_novo, msg = extrair_resultados_web()
            time.sleep(1) # Efeito de processamento tático
            if df_novo is not None:
                st.session_state.df_backtest = df_novo
                st.success("✅ Radar sincronizado! Tabela actualizada.")
                st.rerun()
            else:
                st.error(f"⚠️ Alerta: {msg}")
                st.info("Pode preencher a tabela manualmente enquanto os engenheiros ajustam a frequência do radar.")
    st.markdown("</div>", unsafe_allow_html=True)
with c2:
    st.markdown("<span style='color:#aaa; font-size: 0.9em;'>*O Extrator varre as últimas 11 extrações no site PlayBicho. Você também pode digitar/editar na tabela abaixo à vontade.*</span>", unsafe_allow_html=True)

st.markdown("#### 📝 Base de Dados (Editável):")
df_editado = st.data_editor(st.session_state.df_backtest, use_container_width=True, hide_index=True)

# =============================================================================
# --- 4. MOTOR DE BACKTEST (LÓGICA) ---
# =============================================================================
if st.button("🚀 Executar Backtest", use_container_width=True):
    vitorias = 0
    derrotas = 0
    custo_por_rodada = 125.00
    premio_por_vitoria = 255.00
    
    st.markdown("---")
    st.markdown("### 📊 Relatório de Transições")
    
    # Processa as transições. O site mais recente fica no topo da tabela (linha 0).
    # Vamos inverter a tabela para ler cronologicamente (do mais antigo para o mais recente)
    df_cronologico = df_editado.iloc[::-1].reset_index(drop=True)
    
    for i in range(len(df_cronologico)-1):
        linha_atual = df_cronologico.iloc[i]
        linha_futura = df_cronologico.iloc[i+1]
        
        # Ignora se não houver dados (ex: sorteios que ainda não aconteceram hoje)
        if linha_atual["1º Prêmio"] == "" or linha_futura["1º Prêmio"] == "":
            continue 
            
        try:
            grupos_base = [
                str(linha_atual["1º Prêmio"]).strip().zfill(2),
                str(linha_atual["2º Prêmio"]).strip().zfill(2),
                str(linha_atual["3º Prêmio"]).strip().zfill(2),
                str(linha_atual["4º Prêmio"]).strip().zfill(2),
                str(linha_atual["5º Prêmio"]).strip().zfill(2)
            ]
            
            alvo_1 = str(linha_futura["1º Prêmio"]).strip().zfill(2)
            alvo_2 = str(linha_futura["2º Prêmio"]).strip().zfill(2)
            
            if alvo_1 in grupos_base or alvo_2 in grupos_base:
                status = "VITÓRIA"
                vitorias += 1
                cor = "#4CAF50"
            else:
                status = "DERROTA"
                derrotas += 1
                cor = "#FF5252"
                
            st.markdown(f"<div style='background-color: #2b2b2b; padding: 10px; margin-bottom: 5px; border-radius: 5px; border-left: 4px solid {cor};'>"
                        f"Base <b style='color:#aaa;'>{linha_atual['Sorteio']}</b> ➔ Sorteio <b style='color:#aaa;'>{linha_futura['Sorteio']}</b> <br>"
                        f"Os 5 grupos base: {grupos_base} <br>"
                        f"Veio no novo 1º ou 2º: ['{alvo_1}', '{alvo_2}'] <br>"
                        f"Resultado: <b style='color: {cor};'>{status}</b></div>", 
                        unsafe_allow_html=True)
                        
        except Exception as e:
            pass

    # =============================================================================
    # --- 5. RESULTADO FINANCEIRO ---
    # =============================================================================
    total_jogos = vitorias + derrotas
    
    if total_jogos > 0:
        custo_total = total_jogos * custo_por_rodada
        retorno_total = vitorias * premio_por_vitoria
        lucro_liquido = retorno_total - custo_total
        assertividade = (vitorias / total_jogos) * 100
        
        st.markdown("---")
        st.markdown("### 💰 Balanço Geral Simulado")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Batalhas Travadas", f"{total_jogos}")
        col2.metric("Taxa de Sucesso", f"{assertividade:.1f}%")
        col3.metric("Investimento Total", f"R$ {custo_total:.2f}")
        
        if lucro_liquido > 0:
            col4.metric("Lucro Líquido", f"R$ {lucro_liquido:.2f}", "Positivo")
        else:
            col4.metric("Prejuízo", f"R$ {lucro_liquido:.2f}", "Negativo")
    else:
        st.info("Aguardando dados suficientes para gerar o balanço financeiro.")
