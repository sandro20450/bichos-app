import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import math
import re
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
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Táticas")
st.markdown("### Estratégia: Cerco de Repetição (125 Duques)")

# =============================================================================
# --- 2. O EXTRATOR CIBERNÉTICO COM LEITOR DE HORÁRIOS ---
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
        
        novos_dados = {
            "Sorteio": [], "1º Prêmio": [], "2º Prêmio": [], 
            "3º Prêmio": [], "4º Prêmio": [], "5º Prêmio": [], "Status": []
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
                if any(x in primeira_col for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    grupo = ""
                    # Acha o grupo pelos dígitos diretos
                    for txt in textos[1:]:
                        nums = ''.join(filter(str.isdigit, txt))
                        if 0 < len(nums) <= 2:
                            grupo = nums.zfill(2)
                            break
                    # Acha o grupo por cálculo matemático (se o site esconder)
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
                # =========================================================
                # NOVO: MOTOR DE EXTRAÇÃO DE HORAS (RegEx)
                # =========================================================
                hora_str = ""
                # Procura a hora dentro da própria tabela
                match = re.search(r'\b([01]?[0-9]|2[0-3])[:hH]([0-5][0-9])\b', tabela.text)
                if match:
                    hora_str = match.group(0).replace('h', ':').replace('H', ':')
                else:
                    # Se não achar, procura no cabeçalho acima da tabela
                    header = tabela.find_previous(['h2', 'h3', 'h4', 'caption', 'th', 'div'])
                    if header:
                        match = re.search(r'\b([01]?[0-9]|2[0-3])[:hH]([0-5][0-9])\b', header.text)
                        if match:
                            hora_str = match.group(0).replace('h', ':').replace('H', ':')
                
                nome_sorteio = f"{hora_str} ({data_alvo.strftime('%d/%m')})" if hora_str else f"Ext. {count} ({data_alvo.strftime('%d/%m')})"
                
                novos_dados["Sorteio"].append(nome_sorteio)
                novos_dados["1º Prêmio"].append(grupos_extraidos[0])
                novos_dados["2º Prêmio"].append(grupos_extraidos[1])
                novos_dados["3º Prêmio"].append(grupos_extraidos[2])
                novos_dados["4º Prêmio"].append(grupos_extraidos[3])
                novos_dados["5º Prêmio"].append(grupos_extraidos[4])
                novos_dados["Status"].append("⏳")
                count += 1
                if count > 11: break
        
        if len(novos_dados["Sorteio"]) > 0:
            while len(novos_dados["Sorteio"]) < 11:
                idx = len(novos_dados["Sorteio"]) + 1
                novos_dados["Sorteio"].append(f"Extração Pendente")
                for pr in ["1º Prêmio", "2º Prêmio", "3º Prêmio", "4º Prêmio", "5º Prêmio", "Status"]:
                    novos_dados[pr].append("⏳" if pr == "Status" else "")
            return pd.DataFrame(novos_dados), "Sucesso"
        else:
            return None, f"Não há resultados registados para o dia {data_alvo.strftime('%d/%m/%Y')}."
            
    except Exception as e:
        return None, f"Falha crítica nos motores de busca: {e}"

# =============================================================================
# --- 3. DADOS INICIAIS ---
# =============================================================================
if 'df_backtest' not in st.session_state:
    dados_iniciais = {
        "Sorteio": [f"Extração {i}" for i in range(1, 12)],
        "1º Prêmio": [""] * 11, "2º Prêmio": [""] * 11,
        "3º Prêmio": [""] * 11, "4º Prêmio": [""] * 11, "5º Prêmio": [""] * 11,
        "Status": ["⏳"] * 11
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
                st.success("✅ Radar sincronizado!")
                st.rerun()
            else:
                st.error(f"⚠️ Alerta: {msg}")
    st.markdown("</div>", unsafe_allow_html=True)

with c3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.85em;'>O sistema injeta a data direto no servidor e descobre os horários de forma automática usando RegEx.</span>", unsafe_allow_html=True)

st.markdown("---")

# =============================================================================
# --- 4. MOTOR DE BACKTEST EM TEMPO REAL ---
# =============================================================================
# O sistema agora calcula tudo instantaneamente sem precisar de botão "Executar"!
df_atual = st.session_state.df_backtest.copy()
vitorias = 0
derrotas = 0

# A primeira linha não tem como ter status de aposta, pois não sabemos o resultado anterior a ela
if len(df_atual) > 0:
    df_atual.at[0, "Status"] = "---"

for i in range(1, len(df_atual)):
    linha_anterior = df_atual.iloc[i-1]
    linha_atual = df_atual.iloc[i]
    
    # Se uma das linhas estiver vazia, o status fica pendente
    if not linha_anterior["1º Prêmio"] or not linha_atual["1º Prêmio"]:
        df_atual.at[i, "Status"] = "⏳"
        continue
        
    try:
        # A regra: Os 5 grupos da Extração Anterior
        grupos_base = [
            str(linha_anterior["1º Prêmio"]).strip().zfill(2),
            str(linha_anterior["2º Prêmio"]).strip().zfill(2),
            str(linha_anterior["3º Prêmio"]).strip().zfill(2),
            str(linha_anterior["4º Prêmio"]).strip().zfill(2),
            str(linha_anterior["5º Prêmio"]).strip().zfill(2)
        ]
        
        # Contra: O 1º e 2º Prêmio da Extração Atual
        alvo_1 = str(linha_atual["1º Prêmio"]).strip().zfill(2)
        alvo_2 = str(linha_atual["2º Prêmio"]).strip().zfill(2)
        
        if alvo_1 in grupos_base or alvo_2 in grupos_base:
            df_atual.at[i, "Status"] = "🟢 Vitória"
            vitorias += 1
        else:
            df_atual.at[i, "Status"] = "❌ Derrota"
            derrotas += 1
    except:
        df_atual.at[i, "Status"] = "⏳"

# Exibe a tabela na tela (a coluna Status é bloqueada para edição manual)
st.markdown("#### 📝 Placard Tático Interativo")
df_editado = st.data_editor(
    df_atual,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Status": st.column_config.TextColumn("Resultado", disabled=True)
    }
)

# Salva as edições do utilizador (se houver) para manter o ecrã atualizado
st.session_state.df_backtest = df_editado

# =============================================================================
# --- 5. RESULTADO FINANCEIRO AUTOMÁTICO ---
# =============================================================================
total_jogos = vitorias + derrotas

if total_jogos > 0:
    custo_por_rodada = 125.00
    premio_por_vitoria = 255.00
    
    custo_total = total_jogos * custo_por_rodada
    retorno_total = vitorias * premio_por_vitoria
    lucro_liquido = retorno_total - custo_total
    assertividade = (vitorias / total_jogos) * 100
    
    st.markdown("### 💰 Balanço do Dia Selecionado")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Batalhas Travadas", f"{total_jogos}")
    col2.metric("Taxa de Sucesso", f"{assertividade:.1f}%")
    col3.metric("Investimento Total", f"R$ {custo_total:.2f}")
    
    if lucro_liquido > 0:
        col4.metric("Lucro Líquido", f"R$ {lucro_liquido:.2f}", "Lucro")
    else:
        col4.metric("Prejuízo", f"R$ {lucro_liquido:.2f}", "- Perda")
