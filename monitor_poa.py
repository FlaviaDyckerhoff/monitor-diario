import os
import re
import json
import requests
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]

URL_DIARIO = "https://poa.sp.gov.br/diario-oficial/"
STATE_FILE = "state_poa.json"
DEFAULT_ULTIMA_EDICAO = 1022

HEADERS_SITE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

def ler_estado():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        import base64
        data = resp.json()
        conteudo = base64.b64decode(data["content"]).decode("utf-8")
        estado = json.loads(conteudo)
        print(f"Estado lido: ultima edicao = {estado['ultima_edicao']}")
        return estado["ultima_edicao"], data["sha"]
    else:
        print(f"Arquivo de estado nao encontrado, usando padrao: {DEFAULT_ULTIMA_EDICAO}")
        return DEFAULT_ULTIMA_EDICAO, None

def salvar_estado(ultima_edicao, sha):
    import base64
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    conteudo = json.dumps({"ultima_edicao": ultima_edicao})
    encoded = base64.b64encode(conteudo.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Atualiza estado Poa: edicao {ultima_edicao}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"Estado salvo: ultima edicao = {ultima_edicao}")
    else:
        print(f"Erro ao salvar estado: {resp.status_code} - {resp.text}")

def buscar_edicoes_novas(ultima_edicao):
    resp = requests.get(URL_DIARIO, headers=HEADERS_SITE, timeout=20)
    resp.raise_for_status()
    texto = resp.text
    print(f"Pagina carregada: {len(texto)} caracteres")

    padrao = re.compile(r'href="(https://poa\.sp\.gov\.br/wp-content/uploads/\d+/\d+/edicao-(\d+)-[^"]+\.pdf)"')
    novas = []
    vistos = set()

    for match in padrao.finditer(texto):
        url_pdf = match.group(1)
        numero  = int(match.group(2))
        if numero > ultima_edicao and numero not in vistos:
            vistos.add(numero)
            novas.append({"numero": numero, "link": url_pdf})
            print(f"Edicao nova: {numero}")

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

    ultima_edicao, sha = ler_estado()

    try:
        novas = buscar_edicoes_novas(ultima_edicao)
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
        return

    if not novas:
        print("Nenhuma edicao nova encontrada.")
        return

    print(f"{len(novas)} edicao(oes) nova(s) encontrada(s).")

    maior_edicao = ultima_edicao
    for edicao in novas:
        msg = (
            f"Nova edicao - Diario Oficial de Poa\n"
            f"Edicao n {edicao['numero']}\n"
            f"{edicao['link']}"
        )
        enviar_whatsapp(msg)
        if edicao["numero"] > maior_edicao:
            maior_edicao = edicao["numero"]

    salvar_estado(maior_edicao, sha)

if __name__ == "__main__":
    main()
