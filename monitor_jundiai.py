import os
import re
import json
import base64
import feedparser
import requests
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]

RSS_URL    = "https://imprensaoficial.jundiai.sp.gov.br/feed/"
STATE_FILE = "state_jundiai.json"
DEFAULT_ULTIMA_EDICAO = 5790

TERMOS_BUSCA = [
    "15.016/2025",
    "15016/2025",
    "instalacoes de gas",
    "condominios edilícios",
    "manutencao preventiva",
]

def ler_estado():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        conteudo = base64.b64decode(data["content"]).decode("utf-8")
        estado = json.loads(conteudo)
        print(f"Estado lido: ultima edicao = {estado['ultima_edicao']}")
        return estado["ultima_edicao"], data["sha"]
    else:
        print(f"Arquivo de estado nao encontrado, usando padrao: {DEFAULT_ULTIMA_EDICAO}")
        return DEFAULT_ULTIMA_EDICAO, None

def salvar_estado(ultima_edicao, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    conteudo = json.dumps({"ultima_edicao": ultima_edicao})
    encoded = base64.b64encode(conteudo.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Atualiza estado Jundiai: edicao {ultima_edicao}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"Estado salvo: ultima edicao = {ultima_edicao}")
    else:
        print(f"Erro ao salvar estado: {resp.status_code} - {resp.text}")

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
        print(f"Erro Twilio: {resp.status_code} - {resp.text}")

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando RSS Jundiai...")

    ultima_edicao, sha = ler_estado()

    feed = feedparser.parse(RSS_URL)
    novas_edicoes = []

    for entry in feed.entries:
        numero = extrair_numero_edicao(entry.title)
        if numero and numero > ultima_edicao:
            novas_edicoes.append({"numero": numero, "titulo": entry.title, "link": entry.link})

    if not novas_edicoes:
        print("Nenhuma edicao nova encontrada.")
        return

    print(f"{len(novas_edicoes)} edicao(oes) nova(s) encontrada(s).")

    maior_edicao = ultima_edicao
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
        if edicao["numero"] > maior_edicao:
            maior_edicao = edicao["numero"]

    salvar_estado(maior_edicao, sha)

if __name__ == "__main__":
    main()
