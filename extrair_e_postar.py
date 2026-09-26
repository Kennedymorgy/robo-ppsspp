import sys
import os
import re
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
CLOUDFLARE_WORKER_URL = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

DOMINIOS_SERVIDORES = [
    "mediafire.com", "mega.nz", "mega.io", "drive.google.com", "archive.org", 
    "workupload.com", "terabox.com", "terabox.app", "1024tera.com", "gofile.io", 
    "modsfire.com", "sharemods.com", "encurtanet.com", "uploadhaven.com", 
    "pixeldrain.com", "1fichier.com", "krakenfiles.com", "usersdrive.com"
]

def limpa_url(url):
    """Remove redirecionamentos do Google Captcha (?continue=) e recupera o link original."""
    if not url:
        return ""
    if "google.com/sorry" in url or "google.com/url" in url:
        try:
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            if "continue" in query and query["continue"][0].startswith("http"):
                return query["continue"][0]
            if "q" in query and query["q"][0].startswith("http"):
                return query["q"][0]
            if "url" in query and query["url"][0].startswith("http"):
                return query["url"][0]
        except:
            pass
        return ""
    return url

def extrair_id_jogo(url_origem):
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file', 'playstation-portable-rom', 'roms', 'psp'] and not p.isdigit()]
    id_jogo = partes[-1] if partes else "jogo"
    id_jogo = re.sub(r'(\.html|\.iso|\.cso|\.zip|\.7z|-psp-ptbr|-ppsspp|-psp|-ps2-ptbr|-ps2)$', '', id_jogo, flags=re.IGNORECASE)
    return re.sub(r'[^a-zA-Z0-9_-]', '', id_jogo).lower()

def extrair_nome_limpo(page, id_jogo):
    titulo_raw = page.title() or ""
    nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|7Z|RAR|CHD|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|–|-|\|).*$', '', titulo_raw).strip()
    if not nome_limpo or nome_limpo.startswith("http") or len(nome_limpo) < 3:
        nome_limpo = id_jogo.replace('-', ' ').title()
    return nome_limpo

def extrair_link_externo_de_pagina_interna(page, url_interna):
    url_interna = limpa_url(url_interna)
    if not url_interna or "google.com/sorry" in url_interna:
        return ""

    try:
        print(f"🔄 Entrando em página secundária: {url_interna}")
        page.goto(url_interna, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        
        hrefs = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
        for h in hrefs:
            h_limpo = limpa_url(h)
            if not h_limpo or "google.com/sorry" in h_limpo:
                continue
            if any(dom in h_limpo for dom in DOMINIOS_SERVIDORES) or re.search(r'\.(zip|7z|rar|iso|cso)(\?.*)?$', h_limpo, re.IGNORECASE):
                return h_limpo
    except Exception as e:
        print(f"⚠️ Erro na página secundária: {e}")
    return url_interna

def extrair_romspedia_com_click(page, url_alvo):
    link_capturado = []

    def escutar_requisicoes(request):
        url = request.url
        if re.search(r'\.(zip|7z|rar|iso|cso)(\?.*)?$', url, re.IGNORECASE) or "/files/" in url:
            if not any(ext in url for ext in [".png", ".jpg", ".css", ".js", "google"]):
                link_capturado.append(url)

    page.on("request", escutar_requisicoes)

    try:
        print(f"\n🌐 [ROMSPEDIA] Acessando: {url_alvo}")
        page.goto(url_alvo, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(2000)

        botao_download = page.query_selector("a:has-text('fast'), a:has-text('slow'), a[href*='/download']")
        if botao_download:
            href_download = botao_download.get_attribute("href")
            if href_download:
                if not href_download.startswith("http"):
                    href_download = "https://www.romspedia.com" + href_download
                print(f"⏳ Indo para a página de contagem regressiva: {href_download}")
                page.goto(href_download, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(7000)

        if link_capturado:
            print(f"🎯 Link direto extraído com sucesso: {link_capturado[0]}")
            return link_capturado[0]

        link_click_here = page.query_selector("a:has-text('click here')")
        if link_click_here:
            href_manual = link_click_here.get_attribute("href")
            if href_manual:
                print(f"🎯 Link do 'click here' extraído: {href_manual}")
                return href_manual

    except Exception as e:
        print(f"⚠️ Erro ao processar RomsPedia: {e}")

    return url_alvo

def extrair_links_com_contexto(page, url_alvo):
    dados = {"link_direto": "", "link_savedata": ""}
    
    elementos = page.eval_on_selector_all("a[href]", """
        elements => elements.map(e => ({
            href: e.href,
            text: (e.innerText || '').toLowerCase(),
            parentText: (e.parentElement ? e.parentElement.innerText : '').toLowerCase()
        }))
    """)

    parsed_alvo = urllib.parse.urlparse(url_alvo)
    dominio_atual = parsed_alvo.netloc.replace("www.", "")

    candidatos_direto = []
    candidatos_savedata = []

    for item in elementos:
        href = limpa_url(item["href"])
        if not href or "google.com/sorry" in href:
            continue

        parsed_href = urllib.parse.urlparse(href)
        dominio_href = parsed_href.netloc.replace("www.", "")

        # Ignora links que pertencem ao próprio blog (evita puxar a URL da postagem)
        if dominio_atual and dominio_atual in dominio_href:
            continue

        if any(ignorar in href for ignorar in ["facebook.com", "twitter.com", "instagram.com", "whatsapp.com", "telegram.org", "/category/", "zarchiver"]):
            continue

        texto = item["text"]
        contexto = f"{texto} {item['parentText']}"

        is_savedata = any(k in contexto for k in ["savedata", "save data", "save-data", "unlock character", "personagens"])
        is_servidor = any(dom in href for dom in DOMINIOS_SERVIDORES)
        is_arquivo = re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', href, re.IGNORECASE)
        is_botao = any(k in contexto for k in ["download", "modsfire", "sharemods", "mediafire", "mega", "alternativelink", "cso", "iso", "zip"])

        if is_savedata:
            if is_servidor or is_arquivo or is_botao:
                if href not in candidatos_savedata:
                    candidatos_savedata.append(href)
        else:
            if is_servidor or is_arquivo or is_botao:
                if href not in candidatos_direto:
                    candidatos_direto.append(href)
            elif not candidatos_direto:
                candidatos_direto.append(href)

    if candidatos_direto:
        dados["link_direto"] = candidatos_direto[0]
    if candidatos_savedata:
        dados["link_savedata"] = candidatos_savedata[0]

    return dados

def processar_pagina(url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    link_direto, link_savedata = "", ""
    nome_jogo = id_jogo.replace('-', ' ').title()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
        page = context.new_page()

        try:
            if "romspedia.com" in url_alvo:
                link_direto = extrair_romspedia_com_click(page, url_alvo)
                nome_jogo = extrair_nome_limpo(page, id_jogo)
            else:
                print(f"\n🌐 Processando URL: {url_alvo}")
                page.goto(url_alvo, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(3000)

                nome_jogo = extrair_nome_limpo(page, id_jogo)
                links = extrair_links_com_contexto(page, url_alvo)

                link_direto = links["link_direto"]
                link_savedata = links["link_savedata"]

                if link_direto and not any(dom in link_direto for dom in DOMINIOS_SERVIDORES) and not re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', link_direto, re.IGNORECASE):
                    link_direto = extrair_link_externo_de_pagina_interna(page, link_direto)

                if link_savedata and not any(dom in link_savedata for dom in DOMINIOS_SERVIDORES) and not re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', link_savedata, re.IGNORECASE):
                    link_savedata = extrair_link_externo_de_pagina_interna(page, link_savedata)

        except Exception as e:
            print(f"⚠️ Erro ao navegar: {e}")
        finally:
            browser.close()

    link_direto = limpa_url(link_direto)
    link_savedata = limpa_url(link_savedata)

    # Se por acaso não achar nada válido, deixa vazio em vez de salvar a URL do blog
    if not link_direto or "google.com/sorry" in link_direto or url_alvo in link_direto:
        link_direto = ""

    if "google.com/sorry" in link_savedata or url_alvo in link_savedata:
        link_savedata = ""

    if link_direto:
        salvar_no_firebase(id_jogo, nome_jogo, url_alvo, link_direto, link_savedata)
    else:
        print(f"❌ Não foi possível extrair o link real para: {url_alvo}")

def salvar_no_firebase(id_jogo, nome_jogo, url_alvo, link_direto, link_savedata):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"
    
    dados_atuais = {}
    try:
        res_get = requests.get(endpoint, timeout=10)
        if res_get.status_code == 200 and res_get.json():
            dados_atuais = res_get.json()
    except:
        pass

    payload = {
        "url_original": url_alvo,
        "link_direto": link_direto,
        "link_savedata": link_savedata,
        "nome": nome_jogo,
        "tipo": "PPSSPP ISO"
    }

    se_mudou = (
        dados_atuais.get("link_direto") != link_direto or
        dados_atuais.get("link_savedata") != link_savedata
    )

    try:
        res = requests.patch(endpoint, json=payload, timeout=10)
        if res.status_code == 200:
            status_txt = "🔄 LINK ATUALIZADO NO FIREBASE!" if se_mudou else "⚡ LINKS VERIFICADOS (SEM ALTERAÇÕES)"
            print(f"✅ {status_txt} -> /ppsspp/{id_jogo}")
            print("="*60)
            print(f"🎮 Jogo: {nome_jogo}")
            print(f"🔗 Cloudflare ISO: {CLOUDFLARE_WORKER_URL}/?id={id_jogo}")
            if link_savedata:
                print(f"💾 Cloudflare Savedata: {CLOUDFLARE_WORKER_URL}/?id={id_jogo}&type=savedata")
            print(f"📦 ISO Real: {link_direto}")
            if link_savedata: print(f"💾 Savedata Real: {link_savedata}")
            print("="*60 + "\n")
    except Exception as e:
        print(f"❌ Erro ao salvar no Firebase: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_pagina(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                urls = [linha.strip() for linha in f if linha.strip() and not linha.startswith("#")]
            print(f"🤖 Monitorando e atualizando {len(urls)} jogo(s)...")
            for url in urls:
                processar_pagina(url)
