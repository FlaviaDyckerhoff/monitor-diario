import os
import re
import feedparser
import requests
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]

RSS_URL                 = "https://imprensaoficial.jundiai.sp.gov.br/feed/"
ULTIMA_EDICAO_CONHECIDA = 5789

TERMOS_BUSCA = [
    "15.016/2025",
    "15016/2025",
    "instalacoes de gas",
    "condominios edilícios",
    "manutencao preventiva",
]

def extrair_numero_edicao(titulo):
    match = re.search(r"(\d{4,5})", titulo)
    return int(match.group(1)) if match else None

def checar_conteudo(url_edicao):
    try:
        resp = requests.get(url_edicao, timeout=15)
        texto = resp.text.lower()
        for termo in TERMOS_BUSCA:
            if termo.lower() in texto:
                return True, termo
    except Exception as e:
        print(f"Erro ao acessar {url_edicao}: {e}")
    return False, ""

def enviar_whatsapp(mensagem):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    payload = {"From": TWILIO_FROM, "To": TWILIO_TO, "Body": mensagem}
    resp = requests.post(url, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if resp.status_code == 201:
        print("WhatsApp enviado com sucesso.")
    else:
        print(f"Erro: {resp.status_code} - {resp.text}")

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando RSS...")

    feed = feedparser.parse(RSS_URL)
    novas_edicoes = []

    for entry in feed.entries:
        numero = extrair_numero_edicao(entry.title)
        if numero and numero > ULTIMA_EDICAO_CONHECIDA:
            novas_edicoes.append({
                "numero": numero,
                "titulo": entry.title,
                "link": entry.link,
            })

    if not novas_edicoes:
        print("Nenhuma edicao nova encontrada.")
        return

    print(f"{len(novas_edicoes)} edicao(oes) nova(s) encontrada(s).")

    for edicao in novas_edicoes:
        encontrado, termo = checar_conteudo(edicao["link"])
        if encontrado:
            msg = (
                f"Alerta - Diario Oficial de Jundiai\n"
                f"Edicao: {edicao['titulo']}\n"
                f"PL 15.016/2025 ENCONTRADO (termo: {termo})\n"
                f"{edicao['link']}"
            )
        else:
            msg = (
                f"Nova edicao - Diario Oficial de Jundiai\n"
                f"Edicao: {edicao['titulo']}\n"
                f"{edicao['link']}"
            )
        enviar_whatsapp(msg)

if __name__ == "__main__":
    main()
