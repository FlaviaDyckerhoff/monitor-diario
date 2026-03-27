import os
import re
import requests
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]

URL_DIARIO              = "https://poa.sp.gov.br/diario-oficial/"
ULTIMA_EDICAO_CONHECIDA = 1021

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

def buscar_edicoes_novas():
    resp = requests.get(URL_DIARIO, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    texto = resp.text

    print(f"Pagina carregada: {len(texto)} caracteres")

    # Extrai numero de edicao direto da URL do PDF
    padrao = re.compile(r'href="(https://poa\.sp\.gov\.br/wp-content/uploads/\d+/\d+/edicao-(\d+)-[^"]+\.pdf)"')

    novas = []
    vistos = set()

    for match in padrao.finditer(texto):
        url_pdf = match.group(1)
        numero  = int(match.group(2))
        if numero > ULTIMA_EDICAO_CONHECIDA and numero not in vistos:
            vistos.add(numero)
            novas.append({"numero": numero, "link": url_pdf})
            print(f"Edicao nova encontrada: {numero} -> {url_pdf}")

    return sorted(novas, key=lambda x: x["numero"])

def enviar_whatsapp(mensagem):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    payload = {"From": TWILIO_FROM, "To": TWILIO_TO, "Body": mensagem}
    resp = requests.post(url, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if resp.status_code == 201:
        print("WhatsApp enviado com sucesso.")
    else:
        print(f"Erro Twilio: {resp.status_code} - {resp.text}")

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando Diario Oficial de Poa...")

    try:
        novas = buscar_edicoes_novas()
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
        return

    if not novas:
        print("Nenhuma edicao nova encontrada.")
        return

    print(f"{len(novas)} edicao(oes) nova(s) encontrada(s).")

    for edicao in novas:
        msg = (
            f"Nova edicao - Diario Oficial de Poa\n"
            f"Edicao n {edicao['numero']}\n"
            f"{edicao['link']}"
        )
        enviar_whatsapp(msg)

if __name__ == "__main__":
    main()
