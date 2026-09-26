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

# Pega as chaves salvas nos Secrets do GitHub
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GREEN_API_INSTANCE = os.environ.get("GREEN_API_INSTANCE")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GREEN_API_GROUP_ID = os.environ.get("GREEN_API_GROUP_ID")

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

# URL DA SUA CLOUDFLARE WORKER
URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

# SEU BLOG OFICIAL
PAGINA_INICIAL_BLOG = "https://k-404modapk.blogspot.com/"
FOTO_OFICIAL_SITE = "https://k-404modapk.blogspot.com/favicon.ico"

# LISTA DE DOMÍNIOS DE ALOJAMENTO E EXTENSÕES VÁLIDAS DE JOGOS/ISOS/APKS
DOMINIOS_ALOJAMENTO = [
    "modsfire.com", "sharemods.com", "mediafire.com", "mega.nz", "mega.io",
    "drive.google.com", "uploadfiles.eu", "1fichier.com", "modyolo", "modplays",
    "dl.modplays.com", "terabox", "sfile.mobi", "apkpure.com", "dropapk"
]

EXTENSOES_JOGO = [".apk", ".iso", ".cso", ".zip", ".rar", ".7z"]

def notificar_google_indexing_api(url_para_indexar):
    """Envia solicitação para a Google Indexing API para indexar/atualizar a URL no Google Search."""
    if not GOOGLE_CREDENTIALS_JSON:
        print("⚠️ GOOGLE_CREDENTIALS_JSON não configurado nos Secrets. Pulando Google Indexing.")
        return

    if not service_account:
        print("⚠️ Módulo 'google-auth' não encontrado. Certifique-se de adicioná-lo no requirements.txt.")
        return

    url_limpa = url_para_indexar.split('?')[0]

    try:
        info = json.loads(GOOGLE_CREDENTIALS_JSON)
        scopes = ["https://www.googleapis.com/auth/indexing"]
        credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        
        req = google.auth.transport.requests.Request()
        credentials.refresh(req)
        token = credentials.token

        endpoint = "https://indexing.googleapis.com/v1/urlNotifications:publish"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "url": url_limpa,
            "type": "URL_UPDATED"
        }

        res = requests.post(endpoint, headers=headers, json=payload)
        if res.status_code == 200:
            print(f"🚀 Google Indexing API: Solicitada indexação com sucesso para -> {url_limpa}")
        else:
            print(f"❌ Erro na Google Indexing API ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Erro ao enviar para Google Indexing API: {e}")

def enviar_notificacao_telegram(nome_jogo, versao_jogo, id_jogo):
    """Envia mensagem no Telegram com a foto oficial do site."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram não configurado nos Secrets. Pulando notificação.")
        return

    mensagem = (
        f"🔥 <b>JOGO ATUALIZADO!</b>\n\n"
        f"🎮 <b>Jogo:</b> {nome_jogo}\n"
        f"📦 <b>Versão:</b> {versao_jogo}\n"
        f"🔗 <b>Página:</b> <a href='{PAGINA_INICIAL_BLOG}'>Baixar no Blog</a>\n\n"
        f"⚡ <i>Nova versão disponível no servidor! Atualize os dados no Blogger se necessário.</i>"
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
            url_api_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload_msg = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": mensagem,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            res = requests.post(url_api_msg, json=payload_msg)

        if res.status_code == 200:
            print(f"📢 Notificação enviada para o Telegram: {nome_jogo} ({versao_jogo})")
        else:
            print(f"❌ Erro ao enviar Telegram: {res.text}")
    except Exception as e:
        print(f"❌ Erro na API do Telegram: {e}")

def enviar_notificacao_whatsapp(nome_jogo, versao_jogo, id_jogo):
    """Envia mensagem no WhatsApp via GREEN-API com Foto + Legenda."""
    if not GREEN_API_INSTANCE or not GREEN_API_TOKEN or not GREEN_API_GROUP_ID:
        print("⚠️ GREEN-API não configurada nos Secrets. Pulando WhatsApp.")
        return

    chat_id = GREEN_API_GROUP_ID.strip()
    if not chat_id.endswith("@g.us") and not chat_id.endswith("@c.us"):
        chat_id = f"{chat_id}@g.us"

    mensagem = (
        f"🔥 *JOGO ATUALIZADO!*\n\n"
        f"🎮 *Jogo:* {nome_jogo}\n"
        f"📦 *Versão:* {versao_jogo}\n"
        f"🔗 *Página:* {PAGINA_INICIAL_BLOG}\n\n"
        f"⚡ _Nova versão disponível no servidor! Atualize os dados no Blogger se necessário._"
    )

    url_file = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendFileByUrl/{GREEN_API_TOKEN}"
    payload_file = {
        "chatId": chat_id,
        "urlFile": FOTO_OFICIAL_SITE,
        "fileName": "icon.ico",
        "caption": mensagem
    }

    try:
        print(f"🔄 Enviando WhatsApp (Foto + Legenda) para: {chat_id}")
        res = requests.post(url_file, json=payload_file)

        if res.status_code != 200:
            print("⚠️ Falha no envio de arquivo. Tentando enviar como texto simples...")
            url_msg = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendMessage/{GREEN_API_TOKEN}"
            payload_msg = {
                "chatId": chat_id,
                "message": mensagem
            }
            res = requests.post(url_msg, json=payload_msg)

        if res.status_code == 200:
            print(f"🟢 Notificação enviada com sucesso para o WhatsApp: {nome_jogo} ({versao_jogo})")
        else:
            print(f"❌ Falha ao enviar WhatsApp. Verifique as credenciais no GitHub.")
    except Exception as e:
        print(f"❌ Erro crítico na API do WhatsApp: {e}")

def buscar_dados_atuais_firebase(id_jogo):
    """Consulta os dados atuais salvos no Firebase."""
    firebase_base_url = "https://meublog-apks-default-rtdb.firebaseio.com"
    try:
        res = requests.get(f"{firebase_base_url}/links/{id_jogo}.json")
        if res.status_code == 200 and res.text != 'null':
            return res.json()
    except Exception as e:
        print(f"Erro ao consultar Firebase: {e}")
    return {}

def extrair_id_jogo(url_origem):
    """Extrai o ID correto do jogo ignorando sufixos como /download/, /0/, /1/, .html, etc."""
    url_limpa = url_origem.split(']')[0].rstrip('/')
    partes = url_limpa.split('/')
    
    partes_filtradas = [
        p for p in partes 
        if p and p not in ['download', 'file'] and not p.isdigit()
    ]
    
    if partes_filtradas:
        id_jogo = partes_filtradas[-1]
    else:
        id_jogo = "jogo"
        
    id_jogo = id_jogo.replace('.html', '').replace('.apk', '')
    return id_jogo

def extrair_versao_do_texto_ou_link(texto_ou_url):
    """Extrai padrões numéricos de versão (ex: 3.8.0, 4.2.1, 1.23.4) de strings ou URLs de download."""
    if not texto_ou_url:
        return None
    
    match_filename = re.search(r'[vV]?(\d+[\.\-_]\d+(?:[\.\-_]\d+)+)', texto_ou_url)
    if match_filename:
        ver_str = match_filename.group(1).replace('-', '.').replace('_', '.')
        if not ver_str.startswith("202"):
            return ver_str

    match_std = re.search(r'\b(\d+\.\d+(?:\.\d+)*)\b', texto_ou_url)
    if match_std and not match_std.group(1).startswith("202"):
        return match_std.group(1)

    return None

def e_link_valido_de_download(url):
    """Verifica se a URL pertence a um servidor de alojamento ou ficheiro de jogo."""
    if not url or url.startswith("blob:") or "play.google.com" in url:
        return False
    
    url_lower = url.lower()
    if any(dom in url_lower for dom in DOMINIOS_ALOJAMENTO):
        return True
    
    if any(ext in url_lower for ext in EXTENSOES_JOGO):
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
        print(f"⏩ O jogo '{id_jogo}' continua com o mesmo link ({versao_jogo}). Nenhuma notificação enviada.")
        return id_jogo

    print(f"🔄 Nova versão/link detectado para '{id_jogo}'! Atualizando no Firebase...")
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
        res2 = requests.patch(f"{firebase_base_url}/jogos/{id_jogo}.json", json=payload)
        if res1.status_code == 200:
            print(f"✅ Link e versão atualizados no Firebase para: {id_jogo} ({versao_jogo})")
            enviar_notificacao_telegram(nome_jogo, versao_jogo, id_jogo)
            enviar_notificacao_whatsapp(nome_jogo, versao_jogo, id_jogo)
            
            # --- INDEXAÇÃO AUTOMÁTICA NO GOOGLE ---
            notificar_google_indexing_api(PAGINA_INICIAL_BLOG)
            if "blogspot.com" in url_origem or "k-404" in url_origem:
                notificar_google_indexing_api(url_origem)

    except Exception as e:
        print(f"❌ Erro ao salvar no Firebase: {e}")
    
    return id_jogo

def extrair_link_direto(url_alvo):
    print(f"Iniciando extração para: {url_alvo}")

    id_fallback = extrair_id_jogo(url_alvo).replace('-', ' ').title()

    dados_jogo = {
        "nome": id_fallback,
        "versao": "",
        "foto": FOTO_OFICIAL_SITE
    }

    with sync_playwright() as p:
        # Configuração do navegador imitando um Samsung Galaxy S23 Ultra real
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-size=412,915',
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            locale="pt-BR",
            accept_downloads=True
        )

        page = context.new_page()

        if stealth_sync:
            stealth_sync(page)
        else:
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        link_final = None

        # Intercepta pedidos e capturas de rede
        def interceptar_requisicao(request):
            nonlocal link_final
            url = request.url
            if e_link_valido_de_download(url) and not link_final:
                print(f"🎯 Link detectado na rede: {url}")
                link_final = url

        page.on("request", interceptar_requisicao)

        # Captura novas abas/popups abertas por cliques
        def em_nova_pagina(nova_aba):
            nonlocal link_final
            try:
                nova_aba.wait_for_timeout(2000)
                url_popup = nova_aba.url
                if e_link_valido_de_download(url_popup) and not link_final:
                    print(f"🎯 Link detectado em nova aba/popup: {url_popup}")
                    link_final = url_popup
            except Exception as e:
                pass

        context.on("page", em_nova_pagina)

        try:
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            if "cloudflare" in page.content().lower() or "just a moment" in page.title().lower():
                print("Detectado Cloudflare Challenge, aguardando resolução...")
                page.wait_for_timeout(8000)

            # --- EXTRAÇÃO DE NOME E VERSÃO ---
            try:
                full_title = ""
                try:
                    og_elem = page.locator('meta[property="og:title"]').first
                    if og_elem.count() > 0:
                        full_title = og_elem.get_attribute("content") or ""
                except:
                    pass

                if not full_title:
                    full_title = page.title() or ""

                # 1. TENTA VIA JS NO DOM
                num_versao = page.evaluate(r'''() => {
                    const elements = Array.from(document.querySelectorAll('tr, td, th, div, li, span, p'));
                    for (let el of elements) {
                        const txt = (el.innerText || '').trim();
                        if (/^(version|versão)$/i.test(txt) || /^version\s*:/i.test(txt) || /^versão\s*:/i.test(txt)) {
                            const parentText = el.parentElement ? el.parentElement.innerText : '';
                            const match = parentText.match(/\b(\d+\.\d+(?:\.\d+)*)\b/);
                            if (match && match[1] && !match[1].startsWith('202')) {
                                return match[1];
                            }
                        }
                    }
                    return null;
                }''')

                # 2. SE NÃO ACHOU, EXTRAI DO TÍTULO COMPLETO
                if not num_versao and full_title:
                    num_versao = extrair_versao_do_texto_ou_link(full_title)

                # 3. EXTRAÇÃO E LIMPEZA DO NOME
                if full_title and len(full_title.strip()) > 3:
                    nome_limpo = re.sub(r'(?i)\s*(?:MOD|APK|v?\d+\.\d+.*|\(.*?\)|-|–|Download).*$', '', full_title).strip()
                    nome_limpo = re.sub(r'(?i)modyolo\.com|modplays\.com|modyolo|modplays|movgamezone\.com|movgamezone', '', nome_limpo).strip()
                    if nome_limpo and len(nome_limpo) > 1 and nome_limpo.lower() != "download":
                        dados_jogo["nome"] = nome_limpo

                if num_versao:
                    dados_jogo["versao"] = f"v{num_versao.lstrip('vV')}"

            except Exception as err_meta:
                print(f"⚠️ Erro ao extrair metadados da página: {err_meta}")

            # --- PRIMEIRO PASSO: Varredura direta de links no DOM ---
            hrefs = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
            for href in hrefs:
                if e_link_valido_de_download(href):
                    print(f"🎯 Link direto de alojamento encontrado no DOM: {href}")
                    link_final = href
                    break

            # --- SEGUNDO PASSO: Clicar nos botões de download caso não tenha achado direto ---
            if not link_final:
                print("Procurando e clicando em botões de download na página...")
                botoes = page.locator("a, button").all()
                for b in botoes:
                    try:
                        texto = (b.inner_text() or "").strip()
                        href = b.get_attribute("href") or ""
                        
                        if e_link_valido_de_download(href):
                            link_final = href
                            print(f"🎯 Encontrado via atributo href do botão: {href}")
                            break

                        texto_lower = texto.lower()
                        href_lower = href.lower()

                        # Identifica botões típicos de download (Modsfire, Sharemods, Download ISO, etc.)
                        if ("download" in texto_lower or "download" in href_lower or "modsfire" in texto_lower or "sharemods" in texto_lower or "cso" in texto_lower or "iso" in texto_lower) and "play.google.com" not in href_lower:
                            print(f"👆 Clicando no botão: '{texto}' -> {href}")
                            b.click(force=True, timeout=4000)
                            page.wait_for_timeout(3000)

                            if link_final:
                                break
                    except:
                        continue

            print("Aguardando carregamento final da página/redirecionamento...")
            page.wait_for_timeout(5000)

            # --- TERCEIRO PASSO: Varredura final pós-clique ---
            if not link_final:
                hrefs_finais = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                for href in hrefs_finais:
                    if e_link_valido_de_download(href):
                        link_final = href
                        break

            # 4. EXTRAÇÃO DE SEGURANÇA PARA A VERSÃO
            if not dados_jogo["versao"] or dados_jogo["versao"] == "v1.0.0":
                ver_do_link = extrair_versao_do_texto_ou_link(link_final or "")
                if ver_do_link:
                    dados_jogo["versao"] = f"v{ver_do_link.lstrip('vV')}"
                else:
                    ver_da_url = extrair_versao_do_texto_ou_link(url_alvo)
                    if ver_da_url:
                        dados_jogo["versao"] = f"v{ver_da_url.lstrip('vV')}"
                    else:
                        dados_jogo["versao"] = "v1.0.0"

            print(f"🎯 Metadados Extraídos -> Jogo: '{dados_jogo['nome']}' | Versão: '{dados_jogo['versao']}'")

        except Exception as e:
            print(f"Erro na navegação: {e}")

        browser.close()
        return link_final, dados_jogo

def salvar_url_na_lista(url):
    """Guarda a URL no arquivo jogos.txt para o robô monitorar sozinho depois."""
    arquivo = "jogos.txt"
    urls_existentes = set()
    
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            urls_existentes = set(line.strip() for line in f if line.strip())

    if url not in urls_existentes:
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
        print(f"📝 URL salva em {arquivo} para monitoramento automático.")

def processar_jogo(url_alvo):
    """Executa a verificação e atualização de um único jogo."""
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
        url_single = sys.argv[1]
        processar_jogo(url_single)
    else:
        arquivo_jogos = "jogos.txt"
        if os.path.exists(arquivo_jogos):
            with open(arquivo_jogos, "r", encoding="utf-8") as f:
                lista_urls = [linha.strip() for linha in f if linha.strip()]
            
            print(f"🤖 Rodando em modo automático. {len(lista_urls)} jogo(s) para verificar...")
            for url in lista_urls:
                processar_jogo(url)
        else:
            print("⚠️ Nenhuma URL cadastrada no 'jogos.txt'. Adicione uma URL manualmente primeiro.")
