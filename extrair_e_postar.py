import sys
import os
import re
import requests
from playwright.sync_api import sync_playwright

FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
CLOUDFLARE_WORKER_URL = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

DOMINIOS_SERVIDORES = [
    "mediafire.com", "mega.nz", "drive.google.com", "archive.org", 
    "workupload.com", "terabox.com", "gofile.io", "modsfire.com", 
    "encurtanet.com", "uploadhaven.com", "pixeldrain.com", "1fichier.com"
]

def extrair_id_jogo(url_origem):
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file', 'playstation-portable-rom'] and not p.isdigit()]
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
    """Navega na página secundária para buscar o servidor real (Modsfire, Mediafire, Mega, etc)."""
    try:
        print(f"🔄 Entrando em página secundária: {url_interna}")
        page.goto(url_interna, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        
        hrefs = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
        for h in hrefs:
            if any(dom in h for dom in DOMINIOS_SERVIDORES) or re.search(r'\.(zip|7z|rar|iso|cso)(\?.*)?$', h, re.IGNORECASE):
                return h
    except Exception as e:
        print(f"⚠️ Erro na página secundária: {e}")
    return url_interna

def extrair_links_com_contexto(page):
    dados = {"link_direto": "", "link_savedata": ""}
    
    elementos = page.eval_on_selector_all("a[href]", """
        elements => elements.map(e => ({
            href: e.href,
            text: (e.innerText || '').toLowerCase(),
            parentText: (e.parentElement ? e.parentElement.innerText : '').toLowerCase()
        }))
    """)

    for item in elementos:
        href = item["href"]
        contexto = f"{item['text']} {item['parentText']}"

        if any(ignorar in href for ignorar in ["facebook.com", "twitter.com", "instagram.com", "whatsapp.com", "telegram.org", "/category/"]):
            continue

        if ("savedata" in contexto or "save data" in contexto or "save-data" in contexto) and not dados["link_savedata"]:
            dados["link_savedata"] = href

        elif not dados["link_direto"]:
            is_arquivo = re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', href, re.IGNORECASE)
            is_servidor = any(dom in href for dom in DOMINIOS_SERVIDORES)
            if is_arquivo or is_servidor:
                dados["link_direto"] = href

    return dados

def processar_pagina(url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    link_direto, link_savedata = "", ""
    nome_jogo = id_jogo.replace('-', ' ').title()

    if "romsgames.net" in url_alvo:
        link_direto = url_alvo.rstrip('/') + '/'
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
            page = context.new_page()

            try:
                print(f"\n🌐 Processando URL: {url_alvo}")
                page.goto(url_alvo, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(3000)

                nome_jogo = extrair_nome_limpo(page, id_jogo)
                links = extrair_links_com_contexto(page)

                link_direto = links["link_direto"]
                link_savedata = links["link_savedata"]

                if link_savedata and ("movgamezone.com" in link_savedata or "isoptbr.com" in link_savedata):
                    link_savedata = extrair_link_externo_de_pagina_interna(page, link_savedata)

            except Exception as e:
                print(f"⚠️ Erro ao navegar: {e}")
            finally:
                browser.close()

    if not link_direto:
        link_direto = url_alvo

    salvar_no_firebase(id_jogo, nome_jogo, url_alvo, link_direto, link_savedata)

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
