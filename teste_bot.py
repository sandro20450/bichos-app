import requests

# === SUAS CREDENCIAIS SECRETAS ===
TOKEN = "8626929004:AAH0SlcDyWeV_o31QzfNqes_rN2HCnopX4I"
CHAT_ID = "5881774528"

# === A MENSAGEM TÁTICA ===
MENSAGEM = """🚨 *ALERTA PENTÁGONO* 🚨
Senhor Comandante, o teste de transmissão foi concluído com sucesso! 
O seu Soldado Fantasma está vivo e pronto para a guerra. 🫡🎯"""

def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown" # Isso permite deixar o texto em negrito
    }
    
    try:
        resposta = requests.post(url, data=payload)
        if resposta.status_code == 200:
            print("✅ MÍSSIL DISPARADO: Mensagem enviada com sucesso para o seu celular!")
        else:
            print(f"❌ FALHA NO DISPARO: Erro {resposta.status_code} - {resposta.text}")
    except Exception as e:
        print(f"❌ ERRO CRÍTICO DE CONEXÃO: {e}")

# Executando o disparo
enviar_alerta_telegram(MENSAGEM)
