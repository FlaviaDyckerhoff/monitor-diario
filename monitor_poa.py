import os
import re
import requests
from datetime import datetime

# ── Configurações ──────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]

URL_DIARIO         = "https://poa.sp.gov.br/diario-oficial/"
ULTIMA_EDICAO_CONHECIDA = 1021   # Edição de 25/03/2026
# ───────────────────────────────────────────────────────────────


def buscar_edicoes_novas() -> list[dict]:
    """Acessa a página do diário e retorna edições com número > última conhecida."""
    resp = requests.get(URL_DIARIO, timeout=15)
    resp.raise_for_status()

    # Padrão: Edição n° 1022- 26/03/2026 com link para PDF
    padrao = re.compile(
        r'href="([^"]+\.pdf)"[^>]*>.*?Edição\s+n[°º]?\s*(\d+)',
        re.IGNORECASE | re.DOTALL
    )
    # Padrão alternativo (número antes do link)
    padrao_alt = re.compile(
        r'Edição\s+n[°º]?\s*(\d+)[^<]*<[^>]+href="([^"]+\.pdf)"',
        re.IGNORECASE | re.DOTALL
    )

    texto = resp.text
    novas = []
    vistos = set()

    for match in re.finditer(
        r'Edição\s+n[°º]?\s*(\d+).*?href="([^"]+\.pdf)"',
        texto, re.IGNORECASE | re.DOTALL
    ):
        numero = int(match.group(1))
        link   = match.group(2)
        if numero > ULTIMA_EDICAO_CONHECIDA and numero not in vistos:
            vistos.add(numero)
            novas.append({"numero": numero, "link": link})

    # Busca alternativa caso o href venha antes do número
    for match in re.finditer(
        r'href="([^"]+\.pdf)"[^>]*>\s*.*?Edição\s+n[°º]?\s*(\d+)',
        texto, re.IGNORECASE | re.DOTALL
    ):
        numero = int(match.group(2))
        link   = match.group(1)
        if numero > ULTIMA_EDICAO_CONHECIDA and numero not in vistos:
            vistos.add(numero)
            novas.append({"numero": numero, "link": link})

    return sorted(novas, key=lambda x: x["numero"])


def enviar_whatsapp(mensagem: str):
    """Envia mensagem via Twilio WhatsApp."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    payload = {
        "From": TWILIO_FROM,
        "To":   TWILIO_TO,
        "Body": mensagem,
    }
    resp = requests.post(url, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if resp.status_code == 201:
        print("✅ WhatsApp enviado com sucesso.")
    else:
        print(f"❌ Erro ao enviar WhatsApp: {resp.status_code} — {resp.text}")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando Diário Oficial de Poá...")

    try:
        novas = buscar_edicoes_novas()
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
        return

    if not novas:
        print("Nenhuma edição nova encontrada.")
        return

    print(f"{len(novas)} edição(ões) nova(s) encontrada(s).")

    for edicao in novas:
        msg = (
            f"🗞 Nova edição — Diário Oficial de Poá\n"
            f"Edição nº {edicao['numero']}\n"
            f"{edicao['link']}"
        )
        enviar_whatsapp(msg)


if __name__ == "__main__":
    main()
