import sys
import os
import re
import json
import requests
from playwright.sync_api import sync_playwright

try:
    from google.oauth2 import service_account
    import google.auth.transport.requests
except ImportError:
    service_account = None

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

# VÁRIÁVEIS DE AMBIENTE DOS SECRETS DO GITHUB
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GREEN_API_INSTANCE = os.environ.get("GREEN_API_INSTANCE")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GREEN_API_GROUP_ID = os.environ.get("GREEN_API_GROUP_ID")

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

# SUAS CONFIGURAÇÕES
URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"
PAGINA_INICIAL_BLOG = "https://k-404modapk.blogspot.com/"
FOTO_OFICIAL_SITE = "https://k-404modapk.blogspot.com/favicon.ico"

# LISTA EXPANDIDA DE DOMÍNIOS DE ALOJAMENTO E ENCURTADORES DE JOGOS/ISOS/APKS
DOMINIOS_ALOJAMENTO = [
    "modsfire.com", "sharemods.com", "mediafire.com", "mega.nz", "mega.io",
    "drive.google.com", "uploadfiles.eu", "1fichier.com", "modyolo", "modplays",
    "dl.modplays.com", "terabox", "1024tera", "freeterabox", "sfile.mobi", 
    "apkpure.com", "dropapk", "file-upload", "uploadhaven", "zippyshare",
    "modshost", "sub2unlock", "sub4unlock", "boost.ink", "linkvertise",
    "ouo.io", "ouo.press", "tinylink", "krakenfiles.com", "pixeldrain.com",
    "gofile.io", "workupload.com", "katfile.com", "nitroflare.com", "rapidgator.net"
]

DOMINIOS_IGNORAR = [
    "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com",
    "youtu.be", "telegram.me", "t.me", "whatsapp.com", "pinterest.com",
    "blogger.com", "blogspot.com", "google.com/search", "schema.org",
    "w3.org", "github.com"
]

EXTENSOES_JOGO = [".apk", ".iso", ".cso", ".zip", ".rar", ".7z", ".xapk", ".apks"]

def notificar_google_indexing_api(url_para_indexar):
    """Envia solicitação para a Google Indexing API."""
    if not GOOGLE_CREDENTIALS_JSON or not service_account:
        return

    url_limpa = url_para_indexar.split('?')[0]
    try:
        info = json.loads(GOOGLE_CREDENTIALS_JSON)
        scopes = ["https://www.googleapis.com/auth/indexing"]
        credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        req = google.auth.transport.requests.Request()
        credentials.refresh(req)

        endpoint = "https://indexing.googleapis.com/v1/urlNotifications:publish"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {credentials.token}"
        }
        payload = {"url": url_limpa, "type": "URL_UPDATED"}
        res = requests.post(endpoint, headers=headers, json=payload)
        if res.status_code == 200:
            print(f"🚀 Google Indexing API: Indexação solicitada para -> {url_limpa}")
    except Exception as e:
        print(f"❌ Erro na Google Indexing API: {e}")

def enviar_notificacao_telegram(nome_jogo, versao_jogo, id_jogo):
    """Envia notificação formatada para o Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    mensagem = (
        f"🔥 <b>JOGO ATUALIZADO!</b>\n\n"
        f"🎮 <b>Jogo:</b> {nome_jogo}\n"
        f"📦 <b>Versão:</b> {versao_jogo}\n"
        f"🔗 <b>Página:</b> <a href='{PAGINA_INICIAL_BLOG}'>Baixar no Blog</a>\n\n"
        f"⚡ <i>Link direto verificado e atualizado com sucesso!</i>"
    )

    url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": FOTO_OFICIAL_SITE,
        "caption": mensagem,
        "parse_mode": "HTML"
    }

    try:
        res = requests.post(url_api, json=payload)
        if res.status_code != 200:
            url_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url_msg, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"})
        print(f"📢 Telegram notificado: {nome_jogo}")
    except Exception as e:
        print(f"❌ Erro no Telegram: {e}")

def enviar_notificacao_whatsapp(nome_jogo, versao_jogo, id_jogo):
    """Envia notificação para o grupo do WhatsApp via GREEN-API."""
    if not GREEN_API_INSTANCE or not GREEN_API_TOKEN or not GREEN_API_GROUP_ID:
        return

    chat_id = GREEN_API_GROUP_ID.strip()
    if not chat_id.endswith("@g.us") and not chat_id.endswith("@c.us"):
        chat_id = f"{chat_id}@g.us"

    mensagem = (
        f"🔥 *JOGO ATUALIZADO!*\n\n"
        f"🎮 *Jogo:* {nome_jogo}\n"
        f"📦 *Versão:* {versao_jogo}\n"
        f"🔗 *Página:* {PAGINA_INICIAL_BLOG}\n\n"
        f"⚡ _Link direto verificado e atualizado no servidor!_"
    )

    url_file = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendFileByUrl/{GREEN_API_TOKEN}"
    payload_file = {
        "chatId": chat_id,
        "urlFile": FOTO_OFICIAL_SITE,
        "fileName": "icon.ico",
        "caption": mensagem
    }

    try:
        res = requests.post(url_file, json=payload_file)
        if res.status_code != 200:
            url_msg = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendMessage/{GREEN_API_TOKEN}"
            requests.post(url_msg, json={"chatId": chat_id, "message": mensagem})
        print(f"🟢 WhatsApp notificado: {nome_jogo}")
    except Exception as e:
        print(f"❌ Erro no WhatsApp: {e}")

def buscar_dados_atuais_firebase(id_jogo):
    firebase_base_url = "https://meublog-apks-default-rtdb.firebaseio.com"
    try:
        res = requests.get(f"{firebase_base_url}/links/{id_jogo}.json")
        if res.status_code == 200 and res.text != 'null':
            return res.json()
    except Exception as e:
        print(f"Erro ao consultar Firebase: {e}")
    return {}

def extrair_id_jogo(url_origem):
    """Extrai um ID limpo e seguro a partir de qualquer URL de jogo."""
    url_limpa = url_origem.split('?')[0].rstrip('/')
    slug = url_limpa.split('/')[-1] if '/' in url_limpa else url_limpa
    
    for ext in ['.html', '.htm', '.php', '.apk']:
        if slug.endswith(ext):
            slug = slug[:-len(ext)]
            
    slug = re.sub(r'[^a-zA-Z0-9\-_]', '', slug)
    return slug if slug else "jogo-game"

def limpar_nome_jogo(titulo_bruto, id_slug):
    """Transforma o título da página num nome limpo do jogo."""
    if not titulo_bruto or len(titulo_bruto.strip()) < 3:
        return id_slug.replace('-', ' ').replace('_', ' ').title()

    t = re.sub(r'(?i)\s*(?:-|–|\|)\s*(?:MovGameZone|ModYolo|ModPlays|ApkPure|Blogger|BlogSpot).*$', '', titulo_bruto)
    t = re.sub(r'(?i)\s*(?:&|with)\s*PPSSPP\s*Settings.*$', '', t)
    t = re.sub(r'(?i)\s*(?:for\s*Android|PPSSPP\s*CSO|PPSSPP\s*ISO|Free\s*Download).*$', '', t)
    t = re.sub(r'(?i)\b(?:MOD|APK|ISO|CSO|ZIP|RAR)\b', '', t)
    t = re.sub(r'\s+', ' ', t).strip()

    if len(t) > 2 and not t.lower().startswith("http"):
        return t
    return id_slug.replace('-', ' ').replace('_', ' ').title()

def extrair_versao(texto_ou_url):
    if not texto_ou_url:
        return "v1.0.0"
    match = re.search(r'\b[vV]?(\d+\.\d+(?:\.\d+)*)\b', texto_ou_url)
    if match:
        ver = match.group(1)
        if not ver.startswith("202"):  # Ignora anos como 2020, 2024
            return f"v{ver}"
    return "v1.0.0"

def e_link_valido_de_download(url, url_origem=""):
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()

    if url_lower.startswith("blob:") or url_lower.startswith("javascript:") or "play.google.com" in url_lower:
        return False

    if any(dom in url_lower for dom in DOMINIOS_IGNORAR):
        return False

    if any(dom in url_lower for dom in DOMINIOS_ALOJAMENTO):
        return True

    if any(ext in url_lower for ext in EXTENSOES_JOGO):
        return True

    if url_origem:
        domain_origem = url_origem.split('/')[2] if '/' in url_origem else ""
        if domain_origem and domain_origem not in url_lower:
            if any(kw in url_lower for kw in ["download", "file", "get", "cso", "iso", "zip", "mod"]):
                return True

    return False

def salvar_no_firebase_se_novo(url_origem, link_novo, dados_jogo):
    id_jogo = extrair_id_jogo(url_origem)
    nome_jogo = dados_jogo.get("nome", id_jogo.replace('-', ' ').title())
    versao_jogo = dados_jogo.get("versao", "v1.0.0")
    foto_url = FOTO_OFICIAL_SITE

    dados_atuais = buscar_dados_atuais_firebase(id_jogo)
    link_atual = dados_atuais.get("link_direto") if isinstance(dados_atuais, dict) else None
    versao_atual = dados_atuais.get("versao") if isinstance(dados_atuais, dict) else None

    if link_atual == link_novo and versao_atual == versao_jogo:
        print(f"⏩ O jogo '{id_jogo}' já está atualizado no Firebase com o link: {link_novo}")
        return id_jogo

    print(f"🔄 Salvando/Atualizando no Firebase para '{id_jogo}'...")
    firebase_base_url = "https://meublog-apks-default-rtdb.firebaseio.com"
    payload = {
        "url_original": url_origem,
        "link_direto": link_novo,
        "nome": nome_jogo,
        "versao": versao_jogo,
        "foto": foto_url
    }

    try:
        res1 = requests.patch(f"{firebase_base_url}/links/{id_jogo}.json", json=payload)
        requests.patch(f"{firebase_base_url}/jogos/{id_jogo}.json", json=payload)
        if res1.status_code == 200:
            print(f"✅ Firebase atualizado para: {id_jogo} ({versao_jogo})")
            enviar_notificacao_telegram(nome_jogo, versao_jogo, id_jogo)
            enviar_notificacao_whatsapp(nome_jogo, versao_jogo, id_jogo)
            notificar_google_indexing_api(PAGINA_INICIAL_BLOG)
    except Exception as e:
        print(f"❌ Erro ao salvar no Firebase: {e}")

    return id_jogo

def extrair_link_direto(url_alvo):
    print(f"Iniciando extração para: {url_alvo}")
    id_slug = extrair_id_jogo(url_alvo)

    dados_jogo = {
        "nome": id_slug.replace('-', ' ').title(),
        "versao": "v1.0.0",
        "foto": FOTO_OFICIAL_SITE
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--window-size=412,915']
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            accept_downloads=True
        )

        page = context.new_page()
        if stealth_sync:
            stealth_sync(page)

        link_final = None

        def interceptar_requisicao(request):
            nonlocal link_final
            url = request.url
            if e_link_valido_de_download(url, url_alvo) and not link_final:
                print(f"🎯 Link detectado na rede: {url}")
                link_final = url

        page.on("request", interceptar_requisicao)

        def em_nova_pagina(nova_aba):
            nonlocal link_final
            try:
                nova_aba.wait_for_timeout(2000)
                url_popup = nova_aba.url
                if e_link_valido_de_download(url_popup, url_alvo) and not link_final:
                    print(f"🎯 Link detectado em popup: {url_popup}")
                    link_final = url_popup
            except:
                pass

        context.on("page", em_nova_pagina)

        try:
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)

            # EXTRAÇÃO DE NOME E VERSÃO DA PÁGINA
            full_title = page.title() or ""
            dados_jogo["nome"] = limpar_nome_jogo(full_title, id_slug)
            dados_jogo["versao"] = extrair_versao(full_title)

            # --- NÍVEL 1: VARREDURA DIRETA DOS LINKS <a> NO DOM ---
            links_dom = page.eval_on_selector_all("a[href]", """
                elements => elements.map(e => ({
                    href: e.href,
                    text: (e.innerText || '').trim()
                }))
            """)

            # Primeiro procura links que NÃO sejam SaveData
            for item in links_dom:
                href = item["href"]
                texto = item["text"].upper()
                if e_link_valido_de_download(href, url_alvo) and "SAVEDATA" not in texto and "SAVE DATA" not in texto:
                    print(f"🎯 Link principal de jogo encontrado no DOM: {href}")
                    link_final = href
                    break

            # Se não achou link sem SaveData, pega qualquer link válido no DOM
            if not link_final:
                for item in links_dom:
                    href = item["href"]
                    if e_link_valido_de_download(href, url_alvo):
                        print(f"🎯 Link encontrado no DOM: {href}")
                        link_final = href
                        break

            # --- NÍVEL 2: CLICAR NOS BOTÕES SE AINDA NÃO ENCONTROU ---
            if not link_final:
                print("Procurando e clicando em botões de download na página...")
                botoes = page.locator("a, button").all()
                for b in botoes:
                    try:
                        texto = (b.inner_text() or "").strip().lower()
                        href = b.get_attribute("href") or ""

                        if e_link_valido_de_download(href, url_alvo):
                            link_final = href
                            break

                        if any(kw in texto for kw in ["download", "modsfire", "m0dsfire", "sharemods", "iso", "cso", "zip", "rar"]):
                            print(f"👆 Clicando no botão: '{texto}' -> {href}")
                            b.click(force=True, timeout=3000)
                            page.wait_for_timeout(3000)
                            if link_final:
                                break
                    except:
                        continue

            # Se achou versão melhor no link final
            if link_final:
                ver_link = extrair_versao(link_final)
                if ver_link != "v1.0.0":
                    dados_jogo["versao"] = ver_link

            print(f"🎯 Metadados Extraídos -> Jogo: '{dados_jogo['nome']}' | Versão: '{dados_jogo['versao']}'")

        except Exception as e:
            print(f"⚠️ Erro durante a navegação: {e}")

        browser.close()
        return link_final, dados_jogo

def salvar_url_na_lista(url):
    arquivo = "jogos.txt"
    urls_existentes = set()
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            urls_existentes = set(line.strip() for line in f if line.strip())

    if url not in urls_existentes:
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")

def processar_jogo(url_alvo):
    print(f"\n==================================================")
    link, dados_jogo = extrair_link_direto(url_alvo)
    if link:
        id_jogo = salvar_no_firebase_se_novo(url_alvo, link, dados_jogo)
        salvar_url_na_lista(url_alvo)
        link_protegido = f"{URL_WORKER}?id={id_jogo}"
        print(f"LINK_ENCONTRADO:{link_protegido}")
    else:
        print(f"❌ Nenhum link direto encontrado para: {url_alvo}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_jogo(sys.argv[1])
    else:
        arquivo_jogos = "jogos.txt"
        if os.path.exists(arquivo_jogos):
            with open(arquivo_jogos, "r", encoding="utf-8") as f:
                lista_urls = [linha.strip() for linha in f if linha.strip()]
            for url in lista_urls:
                processar_jogo(url)
        else:
            print("⚠️ Nenhuma URL informada nem ficheiro 'jogos.txt' encontrado.")
