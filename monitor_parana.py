import os
import re
import json
import base64
import smtplib
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BRASILIA = ZoneInfo("America/Sao_Paulo")

GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
EMAIL_TO          = os.environ["EMAIL_TO"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPO"]

# diarioCodigo=3 → Diário Oficial Executivo do Paraná
URL_CONSULTA = (
    "https://www.documentos.dioe.pr.gov.br/dioe/consultaPublicaPDF.do"
    "?action=pgLocalizar&enviado=true"
    "&dataInicialEntrada={data}&dataFinalEntrada={data}"
    "&numero=&search=&diarioCodigo=3"
)
STATE_FILE            = "state_parana.json"
DEFAULT_ULTIMA_EDICAO = 12114  # edição de 26/03/2026 (ponto de partida)

HEADERS_SITE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def ler_estado():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
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
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    conteudo = json.dumps({"ultima_edicao": ultima_edicao})
    encoded = base64.b64encode(conteudo.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Atualiza estado Parana: edicao {ultima_edicao}",
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
    """
    Consulta a página do DIOE do Paraná para a data de hoje.
    Extrai número de edição e data de publicação via regex no HTML retornado.
    Retorna lista de edições com numero > ultima_edicao.
    """
    hoje = datetime.now().strftime("%d/%m/%Y")
    url = URL_CONSULTA.format(data=hoje)
    print(f"Consultando: {url}")

    resp = requests.get(url, headers=HEADERS_SITE, timeout=20)
    resp.raise_for_status()
    texto = resp.text
    print(f"Pagina carregada: {len(texto)} caracteres")

    # Extrai linhas do tipo: | 19,26 MB | 26/03/2026 | 12114 | Diário Oficial Executivo |
    # O HTML tem padrão: data no formato DD/MM/AAAA seguida do número da edição
    padrao = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s*\|\s*(\d{4,6})\s*\|\s*Di[aá]rio Oficial Executivo"
    )
    novas = []
    vistos = set()

    for match in padrao.finditer(texto):
        data_pub = match.group(1)
        numero   = int(match.group(2))
        if numero > ultima_edicao and numero not in vistos:
            vistos.add(numero)
            link_consulta = (
                "https://www.documentos.dioe.pr.gov.br/dioe/consultaPublicaPDF.do"
                f"?action=pgLocalizar&enviado=true"
                f"&dataInicialEntrada={data_pub}&dataFinalEntrada={data_pub}"
                f"&numero={numero}&search=&diarioCodigo=3"
            )
            novas.append({
                "numero": numero,
                "data": data_pub,
                "link": link_consulta,
            })
            print(f"Edicao nova encontrada: {numero} ({data_pub})")

    return sorted(novas, key=lambda x: x["numero"])


def enviar_email(edicao):
    assunto = f"Nova edicao - Diario Oficial Executivo do Parana - Edicao {edicao['numero']}"
    corpo = (
        f"Nova edicao do Diario Oficial Executivo do Parana publicada.\n\n"
        f"Edicao: {edicao['numero']}\n"
        f"Data de publicacao: {edicao['data']}\n\n"
        f"Acesse a edicao:\n{edicao['link']}\n\n"
        f"---\n"
        f"Monitor automatico - GitHub Actions"
    )

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            servidor.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())
        print(f"E-mail enviado com sucesso para {EMAIL_TO}.")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        raise


def main():
    agora = datetime.now(BRASILIA)
    print(f"[{agora.strftime('%Y-%m-%d %H:%M')} BRT] Verificando Diario Oficial Executivo do Parana...")

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
        enviar_email(edicao)
        if edicao["numero"] > maior_edicao:
            maior_edicao = edicao["numero"]

    salvar_estado(maior_edicao, sha)


if __name__ == "__main__":
    main()
