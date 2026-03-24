import os
import re
import feedparser
import requests
from datetime import datetime

# ── Configurações ──────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]          # seu número com DDI

RSS_URL            = "https://imprensaoficial.jundiai.sp.gov.br/feed/"
ULTIMA_EDICAO_CONHECIDA = 5789                        # Edição Extra de 24/03/2026

# Termos que indicam que a lei foi publicada (busca case-insensitive)
TERMOS_BUSCA = [
    "15.016/2025",
    "15016/2025",
    "instalações de gás",
    "instalacoes de gas",
    "condomínios edilícios",
    "manutenção preventiva",
]
# ───────────────────────────────────────────────────────────────


def extrair_numero_edicao(titulo: str) -> int | None:
    """Extrai o número da edição do título do post RSS."""
    match = re.search(r"(\d{4,5})", titulo)
    return int(match.group(1)) if match else None


def checar_conteudo(url_edicao: str) -> tuple[bool, str]:
    """
    Acessa a página da edição e verifica se algum termo de busca aparece.
    Retorna (encontrado, trecho_relevante).
    """
    try:
        resp = requests.get(url_edicao, timeout=15)
        texto = resp.text.lower()
        for termo in TERMOS_BUSCA:
            if termo.lower() in texto:
                return True, termo
    except Exception as e:
        print(f"Erro ao acessar {url_edicao}: {e}")
    return False, ""


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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando RSS...")

    feed = feedparser.parse(RSS_URL)
    novas_edicoes = []

    for entry in feed.entries:
        numero = extrair_numero_edicao(entry.title)
        if numero and numero > ULTIMA_EDICAO_CONHECIDA:
            novas_edicoes.append({
                "numero": numero,
                "titulo": entry.title,
                "link":   entry.link,
            })

    if not novas_edicoes:
        print("Nenhuma edição nova encontrada.")
        return

    print(f"{len(novas_edicoes)} edição(ões) nova(s) encontrada(s).")

    for edicao in novas_edicoes:
        print(f"  → Verificando edição {edicao['numero']}: {edicao['link']}")
        encontrado, termo = checar_conteudo(edicao["link"])

        if encontrado:
            msg = (
                f"🚨 *Lei publicada no Diário Oficial de Jundiaí!*\n\n"
                f"📋 Edição: {edicao['titulo']}\n"
                f"🔍 Termo encontrado: \"{termo}\"\n"
                f"🔗 Link: {edicao['link']}\n\n"
                f"Verifique a publicação do PL 15.016/2025 "
                f"(instalações de gás em condomínios)."
            )
            enviar_whatsapp(msg)
        else:
            print(f"     Termos do PL 15.016/2025 não encontrados nesta edição.")

    # Informa que houve edições novas mas sem o PL (para não ficar no escuro)
    edicoes_sem_pl = [e for e in novas_edicoes if not checar_conteudo(e["link"])[0]]
    if edicoes_sem_pl and len(edicoes_sem_pl) == len(novas_edicoes):
        nomes = ", ".join(e["titulo"] for e in edicoes_sem_pl)
        msg = (
            f"📰 *Nova(s) edição(ões) no Diário Oficial de Jundiaí*\n\n"
            f"{nomes}\n\n"
            f"PL 15.016/2025 *não* encontrado nesta(s) edição(ões)."
        )
        enviar_whatsapp(msg)


if __name__ == "__main__":
    main()
