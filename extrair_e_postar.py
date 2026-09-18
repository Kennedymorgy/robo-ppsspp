import sys
import os
import re
import time
import requests
from playwright.sync_api import sync_playwright

FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
CLOUDFLARE_WORKER_URL = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

def extrair_id_jogo(url_origem):
    """Gera o ID único limpo para a chave no Firebase."""
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file', 'playstation-portable-rom'] and not p.isdigit()]
    id_jogo = partes[-1] if partes else "jogo"
    id_jogo = re.sub(r'(\.html|\.iso|\.cso|\.zip|\.7z|-psp-ptbr|-ppsspp|-psp|-ps2-ptbr|-ps2)$', '', id_jogo, flags=re.IGNORECASE)
    return re.sub(r'[^a-zA-Z0-9_-]', '', id_jogo).lower()

def extrair_nome_limpo(page, id_jogo):
    """Garante que o campo 'nome' seja o título do jogo e nunca uma URL."""
    titulo_raw = page.title() or ""
    
    # Limpa sufixos comuns de blogs e sites de roms
    nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|7Z|RAR|CHD|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|–|-|\|).*$', '', titulo_raw).strip()
    
    # Se falhar ou vier como URL, gera um nome formatado a partir do ID
    if not nome_limpo or nome_limpo.startswith("http://") or nome_limpo.startswith("https://") or len(nome_limpo) < 3:
        nome_limpo = id_jogo.replace('-', ' ').title()
        
    return nome_limpo

def identificar_formato(texto):
    """Mapeia a extensão do jogo."""
    texto_upper = texto.upper()
    if "CSO" in texto_upper:
        return "CSO"
    elif "ZIP" in texto_upper:
        return "ZIP"
    elif "7Z" in texto_upper or "RAR" in texto_upper:
        return "7Z / RAR"
    elif "CHD" in texto_upper:
        return "CHD"
    return "ISO"

def extrair_romsgames(page, url_alvo):
    """Tratamento exclusivo para Romsgames.net."""
    print(f"🎯 [ROMSGAMES] Processando: {url_alvo}")
    link_capturado = []

    def escutar_requisicao(req):
        url = req.url
        if re.search(r'\.(iso|cso|zip|7z|rar)(\?.*)?$', url, re.IGNORECASE) or "get-rom" in url:
            if url not in link_capturado:
                link_capturado.append(url)

    page.on("request", escutar_requisicao)
    page.goto(url_alvo, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(3000)

    for b in page.locator("a, button").all():
        try:
            txt = (b.inner_text() or "").lower()
            href = b.get_attribute("href") or ""
            if "save game" in txt or "download" in txt or "/download/" in href:
                b.click(force=True)
                print("⏳ Botão acionado. Aguardando gerador...")
                break
        except:
            continue

    page.wait_for_timeout(9000)

    if not link_capturado:
        hrefs = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
        for h in hrefs:
            if re.search(r'\.(iso|cso|zip|7z|rar)(\?.*)?$', h, re.IGNORECASE) or "get-rom" in h:
                link_capturado.append(h)
                break

    return link_capturado[0] if link_capturado else url_alvo

def extrair_links_com_contexto(page):
    """Extrai ISO, Savedata e Texturas filtrando por texto e servidores comuns."""
    dados = {
        "link_direto": "",
        "link_savedata": "",
        "link_texturas": ""
    }

    dominios_validos = [
        "mediafire.com", "mega.nz", "drive.google.com", "archive.org", 
        "workupload.com", "terabox.com", "gofile.io", "modsfire.com", 
        "encurtanet.com", "uploadhaven.com"
    ]

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

        # Ignora redes sociais e links de navegação interna
        if any(ignorar in href for ignorar in ["facebook.com", "twitter.com", "instagram.com", "whatsapp.com", "telegram.org", "blogspot.com", "/category/"]):
            continue

        # Savedata
        if "savedata" in contexto or "save data" in contexto or "save-data" in contexto:
            if not dados["link_savedata"]:
                dados["link_savedata"] = href

        # Texturas
        elif "textura" in contexto or "texture" in contexto:
            if not dados["link_texturas"]:
                dados["link_texturas"] = href

        # Jogo Principal (ISO / CSO / Servidor de Arquivo)
        else:
            is_arquivo = re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', href, re.IGNORECASE)
            is_servidor = any(dom in href for dom in dominios_validos)

            if (is_arquivo or is_servidor) and not dados["link_direto"]:
                dados["link_direto"] = href

    return dados

def processar_pagina(url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    link_direto = ""
    link_savedata = ""
    link_texturas = ""
    html_content = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
        page = context.new_page()

        try:
            print(f"\n🌐 Processando URL: {url_alvo}")

            if "romsgames.net" in url_alvo:
                link_direto = extrair_romsgames(page, url_alvo)
                html_content = page.content()
                nome_jogo = extrair_nome_limpo(page, id_jogo)
            else:
                page.goto(url_alvo, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(3000)
                html_content = page.content()
                
                nome_jogo = extrair_nome_limpo(page, id_jogo)
                links = extrair_links_com_contexto(page)
                
                link_direto = links["link_direto"]
                link_savedata = links["link_savedata"]
                link_texturas = links["link_texturas"]

        except Exception as e:
            print(f"⚠️ Erro ao navegar com Playwright: {e}")
            nome_jogo = id_jogo.replace('-', ' ').title()
        finally:
            browser.close()

    if not link_direto:
        link_direto = url_alvo

    formato = identificar_formato(html_content + " " + link_direto)

    salvar_no_firebase(
        id_jogo=id_jogo,
        nome_jogo=nome_jogo,
        formato=formato,
        url_alvo=url_alvo,
        link_direto=link_direto,
        link_savedata=link_savedata,
        link_texturas=link_texturas
    )

def salvar_no_firebase(id_jogo, nome_jogo, formato, url_alvo, link_direto, link_savedata, link_texturas):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"

    payload = {
        "url_original": url_alvo,
        "link_direto": link_direto,
        "link_savedata": link_savedata,
        "link_texturas": link_texturas,
        "nome": nome_jogo,
        "tipo": f"PPSSPP {formato}"
    }

    try:
        res = requests.patch(endpoint, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ SALVO NO FIREBASE: /ppsspp/{id_jogo}")
            print("="*60)
            print(f"🎮 Nome: {nome_jogo}")
            print(f"🔗 Link Cloudflare para o Blogger: {CLOUDFLARE_WORKER_URL}/?id={id_jogo}")
            print(f"📦 ISO/Jogo: {link_direto}")
            if link_savedata: print(f"💾 Savedata: {link_savedata}")
            if link_texturas: print(f"🎨 Texturas: {link_texturas}")
            print("="*60 + "\n")
        else:
            print(f"❌ Erro ao salvar no Firebase. Status: {res.status_code}")
    except Exception as e:
        print(f"❌ Falha de conexão com Firebase: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_pagina(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                urls = [linha.strip() for linha in f if linha.strip() and not linha.startswith("#")]
            
            print(f"🤖 Rodando extração automática para {len(urls)} jogo(s)...")
            for url in urls:
                processar_pagina(url)
        else:
            print("⚠️ Crie o arquivo 'jogos.txt' contendo as URLs dos jogos.")
