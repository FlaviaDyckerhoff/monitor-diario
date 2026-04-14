import os
import re
import json
import base64
import requests
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = os.environ["TWILIO_TO"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]

BASE_URL   = "https://www.ioerj.com.br/portal/modules/conteudoonline/do_seleciona_edicao.php"
STATE_FILE = "state_rj.json"

HEADERS_SITE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def data_para_base64(data_str):
    """Converte 'YYYYMMDD' para base64, como o site espera."""
    return base64.b64encode(data_str.encode("utf-8")).decode("utf-8")


def ler_estado():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        conteudo = base64.b64decode(data["content"]).decode("utf-8")
        estado = json.loads(conteudo)
        print(f"Estado lido: {len(estado.get('sessions', []))} caderno(s) conhecidos para {estado.get('data', 'N/A')}")
        return estado, data["sha"]
    else:
        print("Arquivo de estado nao encontrado, iniciando do zero.")
        return {"data": "", "sessions": []}, None


def salvar_estado(estado, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    conteudo = json.dumps(estado)
    encoded = base64.b64encode(conteudo.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Atualiza estado RJ: {estado['data']} - {len(estado['sessions'])} caderno(s)",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"Estado salvo: {len(estado['sessions'])} caderno(s) para {estado['data']}")
    else:
        print(f"Erro ao salvar estado: {resp.status_code} - {resp.text}")


def buscar_cadernos(data_str):
    """
    Acessa a pagina do DO RJ para a data informada (formato YYYYMMDD)
    e retorna lista de dicts com: nome, session, extra (bool).
    """
    param = data_para_base64(data_str)
    url = f"{BASE_URL}?data={param}"
    print(f"Consultando: {url}")

    resp = requests.get(url, headers=HEADERS_SITE, timeout=20)
    resp.raise_for_status()
    texto = resp.text
    print(f"Pagina carregada: {len(texto)} caracteres")

    # Extrai blocos <li> com link de edicao
    # Cada <li> pode ter um <span ID="EdicaoExtraDO"> indicando edicao extra
    padrao_li = re.compile(
        r'<li>\s*<a href="mostra_edicao\.php\?session=([^"]+)"[^>]*>([^<]+)</a>\s*'
        r'(?:<span[^>]*>([^<]*)</span>)?',
        re.IGNORECASE
    )

    cadernos = []
    for match in padrao_li.finditer(texto):
        session = match.group(1).strip()
        nome    = match.group(2).strip()
        extra   = bool(match.group(3) and "EXTRA" in match.group(3).upper())
        cadernos.append({"session": session, "nome": nome, "extra": extra})
        sufixo = " [EDICAO EXTRA]" if extra else ""
        print(f"  Caderno encontrado: {nome}{sufixo}")

    return cadernos


def enviar_whatsapp(mensagem):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    payload = {"From": TWILIO_FROM, "To": TWILIO_TO, "Body": mensagem}
    resp = requests.post(url, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if resp.status_code == 201:
        print("WhatsApp enviado com sucesso.")
    else:
        print(f"Erro Twilio: {resp.status_code} - {resp.text}")


def main():
    hoje = datetime.now().strftime("%Y%m%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando Diario Oficial do RJ...")

    estado, sha = ler_estado()

    # Se mudou o dia, zera o estado (nova edicao do dia comeca do zero)
    if estado.get("data") != hoje:
        print(f"Novo dia detectado ({hoje}). Zerando estado.")
        estado = {"data": hoje, "sessions": []}
        sha = None  # forca criacao se nao existia ainda

    sessions_conhecidas = set(estado.get("sessions", []))

    try:
        cadernos = buscar_cadernos(hoje)
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
        return

    if not cadernos:
        print("Nenhum caderno encontrado na pagina (possivel dia sem publicacao ou site fora).")
        return

    novos = [c for c in cadernos if c["session"] not in sessions_conhecidas]

    if not novos:
        print("Nenhum caderno novo encontrado.")
        return

    print(f"{len(novos)} caderno(s) novo(s) encontrado(s).")

    for caderno in novos:
        link = f"https://www.ioerj.com.br/portal/modules/conteudoonline/mostra_edicao.php?session={caderno['session']}"
        if caderno["extra"]:
            msg = (
                f"Edicao EXTRA - Diario Oficial do RJ\n"
                f"Caderno: {caderno['nome']}\n"
                f"{link}"
            )
        else:
            msg = (
                f"Nova edicao - Diario Oficial do RJ\n"
                f"Caderno: {caderno['nome']}\n"
                f"{link}"
            )
        enviar_whatsapp(msg)

    # Atualiza estado com todos os sessions conhecidos agora
    todas_sessions = list(sessions_conhecidas | {c["session"] for c in novos})
    estado = {"data": hoje, "sessions": todas_sessions}
    salvar_estado(estado, sha)


if __name__ == "__main__":
    main()
