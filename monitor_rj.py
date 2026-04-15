import os
import re
import json
import base64
import smtplib
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv("/opt/monitor-diario/.env")

# TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
# TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
# TWILIO_FROM        = "whatsapp:+14155238886"
# TWILIO_TO          = os.environ["TWILIO_TO"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
EMAIL_TO           = os.environ["EMAIL_TO"]

BASE_URL   = "https://www.ioerj.com.br/portal/modules/conteudoonline/do_seleciona_edicao.php"
STATE_FILE = "/opt/monitor-diario/state_rj.json"

HEADERS_SITE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://www.ioerj.com.br/portal/",
}

def data_para_base64(data_str):
    return base64.b64encode(data_str.encode("utf-8")).decode("utf-8")

def chave_caderno(nome, extra, session):
    if extra:
        return f"{nome} EXTRA ({session[-8:]})"
    return nome

def ler_estado():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            estado = json.load(f)
        print(f"Estado lido: {len(estado.get('cadernos', []))} caderno(s) para {estado.get('data', 'N/A')}")
        return estado
    print("Arquivo de estado nao encontrado, iniciando do zero.")
    return {"data": "", "cadernos": []}

def salvar_estado(estado):
    with open(STATE_FILE, "w") as f:
        json.dump(estado, f, ensure_ascii=False)
    print(f"Estado salvo: {len(estado['cadernos'])} caderno(s) para {estado['data']}")

def buscar_cadernos(data_str):
    param = data_para_base64(data_str)
    url = f"{BASE_URL}?data={param}"
    print(f"Consultando: {url}")
    resp = requests.get(url, headers=HEADERS_SITE, timeout=20)
    resp.raise_for_status()
    texto = resp.text
    print(f"Pagina carregada: {len(texto)} caracteres")
    
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
        chave   = chave_caderno(nome, extra, session)
        cadernos.append({"session": session, "nome": nome, "extra": extra, "chave": chave})
        sufixo = " [EDICAO EXTRA]" if extra else ""
        print(f"  Caderno: {nome}{sufixo} (chave: {chave})")
    return cadernos

def enviar_whatsapp(mensagem):
    print("WhatsApp DESABILITADO (limite Twilio atingido)")
    return

def enviar_email(caderno, link):
    prefixo = "Edicao EXTRA" if caderno["extra"] else "Nova edicao"
    assunto = f"{prefixo} - Diario Oficial do RJ - {caderno['nome']}"
    corpo = (
        f"{prefixo} do Diario Oficial do Rio de Janeiro publicada.\n\n"
        f"Caderno: {caderno['nome']}\n\n"
        f"Acesse:\n{link}\n\n"
        f"---\nMonitor automatico - VPS (WhatsApp temporariamente desabilitado)"
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

def processar_cadernos(cadernos, cadernos_conhecidos, data_str):
    novos = [c for c in cadernos if c["chave"] not in cadernos_conhecidos]
    if not novos:
        return []
    
    print(f"{len(novos)} caderno(s) novo(s) encontrado(s) para {data_str}.")
    
    for caderno in novos:
        link = f"https://www.ioerj.com.br/portal/modules/conteudoonline/mostra_edicao.php?session={caderno['session']}"
        prefixo = "Edicao EXTRA" if caderno["extra"] else "Nova edicao"
        
        hoje = datetime.now().strftime("%Y%m%d")
        if data_str != hoje:
            ontem_formatado = datetime.strptime(data_str, "%Y%m%d").strftime("%d/%m/%Y")
            msg = f"{prefixo} - Diario Oficial do RJ [RETROATIVO {ontem_formatado}]\nCaderno: {caderno['nome']}\n{link}"
        else:
            msg = f"{prefixo} - Diario Oficial do RJ\nCaderno: {caderno['nome']}\n{link}"
        
        enviar_whatsapp(msg)
        enviar_email(caderno, link)
    
    return novos

def main():
    hoje = datetime.now().strftime("%Y%m%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Verificando Diario Oficial do RJ...")

    estado = ler_estado()

    if estado.get("data") != hoje and estado.get("data"):
        ontem = estado.get("data")
        cadernos_conhecidos_ontem = set(estado.get("cadernos", []))
        
        print(f"Novo dia detectado ({hoje}). Verificando se perdeu algo do dia anterior ({ontem})...")
        
        try:
            cadernos_ontem = buscar_cadernos(ontem)
            if cadernos_ontem:
                novos_ontem = processar_cadernos(cadernos_ontem, cadernos_conhecidos_ontem, ontem)
                if novos_ontem:
                    print(f"ALERTA: Encontradas {len(novos_ontem)} edicao(oes) extra(s) do dia anterior!")
        except Exception as e:
            print(f"Erro ao verificar dia anterior: {e}")
        
        estado = {"data": hoje, "cadernos": []}
        print(f"Estado zerado para o novo dia ({hoje}).")
    
    cadernos_conhecidos_hoje = set(estado.get("cadernos", []))

    try:
        cadernos_hoje = buscar_cadernos(hoje)
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
        return

    if not cadernos_hoje:
        print("Nenhum caderno encontrado para hoje.")
        salvar_estado({"data": hoje, "cadernos": list(cadernos_conhecidos_hoje)})
        return

    novos_hoje = processar_cadernos(cadernos_hoje, cadernos_conhecidos_hoje, hoje)
    
    if not novos_hoje:
        print("Nenhum caderno novo para hoje.")

    todas_chaves = cadernos_conhecidos_hoje | {c["chave"] for c in novos_hoje}
    salvar_estado({"data": hoje, "cadernos": list(todas_chaves)})

if __name__ == "__main__":
    main()
