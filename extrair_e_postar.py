import sys
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# CONFIGURAÇÕES DE RECURSOS
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
CLOUDFLARE_WORKER_URL = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

def extrair_id_jogo(url_origem):
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file', 'playstation-portable-rom'] and not p.isdigit()]
    id_jogo = partes[-1] if partes else "jogo"
    id_jogo = re.sub(r'(\.html|\.iso|\.cso|\.zip|\.7z|-psp-ptbr|-ppsspp|-psp|-ps2-ptbr|-ps2)$', '', id_jogo, flags=re.IGNORECASE)
    return re.sub(r'[^a-zA-Z0-9_-]', '', id_jogo).lower()

def identificar_formato(texto):
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

# -----------------------------------------------------------------------------
# EXTRAÇÃO DE LINK REAL DEDICADA (ROMSGAMES.NET VIA REQUISIÇÃO DIRETA)
# -----------------------------------------------------------------------------

def extrair_romsgames_direto(url_alvo):
    print(f"🚀 [ROMSGAMES] Extraindo arquivo direto via HTTP para: {url_alvo}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Referer": url_alvo
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        # 1. Acessa a página principal
        r1 = session.get(url_alvo, timeout=20)
        soup = BeautifulSoup(r1.text, 'html.parser')

        # 2. Localiza o formulário ou botão de download "Save Game"
        # Romsgames usa formulário POST ou link direto para /download/
        download_url = None
        
        # Tenta achar link de download direto na estrutura HTML
        for a in soup.find_all('a', href=True):
            if '/download/' in a['href'] or 'download' in a.get('class', []):
                download_url = a['href']
                if not download_url.startswith('http'):
                    download_url = f"https://www.romsgames.net{download_url}"
                break

        # Se não achou link relativo, verifica formulário
        if not download_url:
            form = soup.find('form', action=re.compile(r'/download/'))
            if form:
                action = form['action']
                download_url = action if action.startswith('http') else f"https://www.romsgames.net{action}"

        if download_url:
            print(f"⏳ Acessando página do gerador de download: {download_url}")
            time.sleep(5) # Aguarda tempo do servidor liberar o token
            
            r2 = session.get(download_url, timeout=20)
            soup2 = BeautifulSoup(r2.text, 'html.parser')

            # Busca links com extensões reais de arquivo (.zip, .iso, .7z, .rar)
            for a in soup2.find_all('a', href=True):
                href = a['href']
                if re.search(r'\.(zip|iso|7z|rar|cso|chd)(\?.*)?$', href, re.IGNORECASE):
                    print(f"🎯 LINK REAL DO ARQUIVO ENCONTRADO: {href}")
                    return href, r1.text

                # Se for link CDN hospedado internamente
                if 'files' in href or 'cdn' in href or 'media' in href:
                    if not any(x in href for x in ['.png', '.jpg', '.css', '.js']):
                        return href, r1.text

    except Exception as e:
        print(f"⚠️ Erro ao extrair Romsgames via HTTP: {e}")

    return None, ""

# -----------------------------------------------------------------------------
# EXTRAÇÃO FALLBACK COM PLAYWRIGHT (OUTROS SITES)
# -----------------------------------------------------------------------------

def navegar_e_extrair_com_playwright(url_alvo):
    links_encontrados = []
    html_content = ""

    with sync_playwright() as p:
        dispositivo = p.devices['Pixel 5']
        dispositivo['user_agent'] = "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**dispositivo)
        page = context.new_page()

        try:
            print(f"🌐 Acessando via Playwright: {url_alvo}")
            # domcontentloaded evita o erro de Timeout por propaganda infinita
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            html_content = page.content()
            hrefs = page.eval_on_selector_all('a[href]', 'elements => elements.map(e => e.href)')

            for h in hrefs:
                if re.search(r'\.(iso|cso|zip|7z|rar|chd)(\?.*)?$', h, re.IGNORECASE):
                    if h not in links_encontrados:
                        links_encontrados.append(h)

        except Exception as e:
            print(f"⚠️ Erro no Playwright: {e}")
        finally:
            browser.close()

    return html_content, links_encontrados

def obter_dados_atuais_firebase(id_jogo):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"
    try:
        res = requests.get(endpoint, timeout=10)
        if res.status_code == 200 and res.json() is not None:
            return res.json()
    except Exception as e:
        print(f"⚠️ Erro ao consultar Firebase: {e}")
    return None

def salvar_ou_atualizar_firebase(id_jogo, nome_jogo, formato, url_alvo, link_jogo, link_savedata="", link_texturas=""):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"

    dados_existentes = obter_dados_atuais_firebase(id_jogo)

    novos_dados = {
        "url_original": url_alvo,
        "link_direto": link_jogo,
        "link_savedata": link_savedata,
        "link_texturas": link_texturas,
        "nome": nome_jogo,
        "tipo": f"PPSSPP {formato}"
    }

    if dados_existentes:
        mudou = (
            dados_existentes.get("link_direto") != link_jogo or
            dados_existentes.get("link_savedata") != link_savedata or
            dados_existentes.get("link_texturas") != link_texturas
        )

        if not mudou:
            print(f"⚡ [SEM ALTERAÇÕES] Os links do jogo '{id_jogo}' estão 100% atualizados no Firebase.")
            return

        print(f"🔄 [LINK ATUALIZADO DETECTADO] Atualizando links do jogo '{id_jogo}' no Firebase...")

    try:
        res = requests.patch(endpoint, json=novos_dados, timeout=10)
        if res.status_code == 200:
            print(f"✅ Firebase sincronizado com sucesso para: {id_jogo}")
        else:
            print(f"❌ Erro ao salvar no Firebase. Status: {res.status_code}")
    except Exception as e:
        print(f"❌ Erro de requisição no Firebase: {e}")

def processar_url(url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    link_real = None
    html = ""

    # TRATAMENTO DEDICADO PARA ROMSGAMES.NET
    if "romsgames.net" in url_alvo:
        link_real, html = extrair_romsgames_direto(url_alvo)

    # SE NÃO ACHOU OU FOR OUTRO SITE, USA PLAYWRIGHT COM MODO RÁPIDO (domcontentloaded)
    if not link_real:
        html, links_capturados = navegar_e_extrair_com_playwright(url_alvo)
        if links_capturados:
            link_real = links_capturados[0]

    # SE AINDA NÃO ACHOU, APLICA FALLBACK PARA A PRÓPRIA URL
    if not link_real:
        print("⚠️ Não foi possível capturar o arquivo final automaticamente. Salvando URL de origem.")
        link_real = url_alvo

    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|CHD|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    formato = identificar_formato(html + " " + link_real)

    salvar_ou_atualizar_firebase(
        id_jogo=id_jogo,
        nome_jogo=nome_limpo,
        formato=formato,
        url_alvo=url_alvo,
        link_jogo=link_real
    )

    # IMPRESSÃO DA SAÍDA
    print("\n" + "="*60)
    print("🔥 LINK PARA COLOCAR NO SEU BLOGGER (COPIE ABAIXO):")
    print(f"{CLOUDFLARE_WORKER_URL}/?id={id_jogo}")
    print("="*60)
    print("📦 LINK REAL DO ARQUIVO (.ZIP / .ISO) SALVO NO FIREBASE:")
    print(f"🔗 {link_real}")
    print("="*60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                for linha in f:
                    url = linha.strip()
                    if url and not url.startswith("#"):
                        processar_url(url)
