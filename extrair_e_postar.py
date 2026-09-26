import sys
import os
import re
import json
import base64
import urllib.parse
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

# CHAVES E CONFIGURAÇÕES DOS SECRETS
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GREEN_API_INSTANCE = os.environ.get("GREEN_API_INSTANCE")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GREEN_API_GROUP_ID = os.environ.get("GREEN_API_GROUP_ID")

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"
PAGINA_INICIAL_BLOG = "https://k-404modapk.blogspot.com/"
FOTO_OFICIAL_SITE = "https://k-404modapk.blogspot.com/favicon.ico"

# SERVIDORES E EXTENSÕES VÁLIDAS DE JOGOS
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
    "blogger.com", "blogspot.com", "google.com", "schema.org", "w3.org", "github.com"
]

EXTENSOES_JOGO = [".apk", ".iso", ".cso", ".zip", ".rar", ".7z", ".xapk", ".apks"]

def notificar_google_indexing_api(url_para_indexar):
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
    url_limpa = url_origem.split('?')[0].rstrip('/')
    slug = url_limpa.split('/')[-1] if '/' in url_limpa else url_limpa
    
    for ext in ['.html', '.htm', '.php', '.apk']:
        if slug.endswith(ext):
            slug = slug[:-len(ext)]
            
    slug = re.sub(r'[^a-zA-Z0-9\-_]', '', slug)
    return slug if slug else "jogo-game"

def limpar_nome_jogo(titulo_bruto, id_slug):
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
        if not ver.startswith("202"):
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

    return False

def tentar_decodificar_url_parametro(url_candidate):
    """Extrai URLs reais escondidas dentro de parâmetros como ?url=... ou ?link=..."""
    try:
        parsed = urllib.parse.urlparse(url_candidate)
        query = urllib.parse.parse_qs(parsed.query)
        for key in ['url', 'link', 'target', 'file', 'dest', 'u']:
            if key in query:
                val = query[key][0]
                if val.startswith("http"):
                    return val
                try:
                    decoded = base64.b64decode(val).decode('utf-8')
                    if decoded.startswith("http"):
                        return decoded
                except:
                    pass
    except:
        pass
    return url_candidate

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
            url_dec = tentar_decodificar_url_parametro(url)
            if e_link_valido_de_download(url_dec, url_alvo) and not link_final:
                print(f"🎯 Link detectado na rede: {url_dec}")
                link_final = url_dec

        page.on("request", interceptar_requisicao)

        def em_nova_pagina(nova_aba):
            nonlocal link_final
            try:
                nova_aba.wait_for_timeout(2000)
                url_popup = tentar_decodificar_url_parametro(nova_aba.url)
                if e_link_valido_de_download(url_popup, url_alvo) and not link_final:
                    print(f"🎯 Link detectado em popup: {url_popup}")
                    link_final = url_popup
            except:
                pass

        context.on("page", em_nova_pagina)

        try:
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            full_title = page.title() or ""
            dados_jogo["nome"] = limpar_nome_jogo(full_title, id_slug)
            dados_jogo["versao"] = extrair_versao(full_title)

            # --- NÍVEL 1: REGEX EM TODO O HTML BRUTO (INCLUINDO IFRAMES) ---
            conteudos_html = [page.content()]
            for frame in page.frames:
                try:
                    conteudos_html.append(frame.content())
                except:
                    pass

            regex_dominios = r'https?://[^\s"\'<>]+(?:' + '|'.join([re.escape(d) for d in DOMINIOS_ALOJAMENTO]) + r')[^\s"\'<>]*'
            regex_extensoes = r'https?://[^\s"\'<>]+\.(?:' + '|'.join([e.lstrip('.') for e in EXTENSOES_JOGO]) + r')[^\s"\'<>]*'

            for html_str in conteudos_html:
                matches = re.findall(regex_dominios, html_str, re.IGNORECASE) + re.findall(regex_extensoes, html_str, re.IGNORECASE)
                for m in matches:
                    m_dec = tentar_decodificar_url_parametro(m)
                    if e_link_valido_de_download(m_dec, url_alvo):
                        print(f"🎯 Link direto encontrado no HTML bruto: {m_dec}")
                        link_final = m_dec
                        break
                if link_final:
                    break

            # --- NÍVEL 2: VARREDURA EM TODOS OS QUADROS DA PÁGINA (IFRAMES) ---
            if not link_final:
                for frame in page.frames:
                    try:
                        links_frame = frame.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                        for href in links_frame:
                            href_dec = tentar_decodificar_url_parametro(href)
                            if e_link_valido_de_download(href_dec, url_alvo):
                                print(f"🎯 Link encontrado dentro de iframe: {href_dec}")
                                link_final = href_dec
                                break
                    except:
                        continue
                    if link_final:
                        break

            # --- NÍVEL 3: CLIQUE AUTOMÁTICO EM BOTÕES DE DOWNLOAD ---
            if not link_final:
                print("Procurando e clicando em botões de download...")
                for frame in page.frames:
                    try:
                        botoes = frame.locator("a, button, div[role='button']").all()
                        for b in botoes:
                            try:
                                texto = (b.inner_text() or "").strip().lower()
                                href = b.get_attribute("href") or ""
                                href_dec = tentar_decodificar_url_parametro(href)

                                if e_link_valido_de_download(href_dec, url_alvo):
                                    link_final = href_dec
                                    break

                                if any(kw in texto for kw in ["download", "modsfire", "sharemods", "iso", "cso", "zip", "rar", "server"]):
                                    print(f"👆 Clicando no botão do elemento: '{texto}'")
                                    b.click(force=True, timeout=3000)
                                    page.wait_for_timeout(3000)
                                    if link_final:
                                        break
                            except:
                                continue
                    except:
                        continue
                    if link_final:
                        break

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
