import sys
import os
import re
import time
import random
import requests
from playwright.sync_api import sync_playwright

# CONFIGURAÇÃO DO BANCO DE DADOS
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"

def extrair_id_jogo(url_origem):
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file'] and not p.isdigit()]
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
# EXTRAÇÃO COM PLAYWRIGHT (OTIMIZADA PARA ROMSFUN E DEMAIS SITES)
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

        # Monitor de rede em tempo real
        def monitorar_requisicoes(request):
            url = request.url
            if any(k in url.lower() for k in ['mediafire.com', 'mega.nz', 'drive.google.com', 'modsfire.com', 'sharemods.com', 'send.cm', 'fastdrive', 'uploadhaven', 'pixeldrain', 'cdn']) or re.search(r'\.(iso|cso|zip|7z|rar|chd)$', url, re.IGNORECASE):
                if url not in links_encontrados and not url.endswith('.js') and not url.endswith('.css'):
                    links_encontrados.append(url)

        page.on("request", monitorar_requisicoes)

        try:
            print(f"🌐 Acessando: {url_alvo}")
            page.goto(url_alvo, wait_until="networkidle", timeout=60000)

            # LÓGICA EXCLUSIVA PARA O ROMSFUN (Evita erro de DOM e aguarda temporizador)
            if "romsfun.com" in url_alvo:
                print("⏳ Tratando Romsfun (Aguardando temporizador e gerando link)...")
                try:
                    # Espera o botão de download ficar visível
                    page.wait_for_selector('a:has-text("Download Now"), .btn-download, a:has-text("Download")', timeout=15000)
                    time.sleep(2)

                    btn_inicial = page.query_selector('a:has-text("Download Now"), .btn-download, a:has-text("Download")')
                    if btn_inicial:
                        btn_inicial.click()
                        print("⏱️ Botão acionado. Aguardando 12 segundos do temporizador...")
                        time.sleep(12)

                    # Busca o botão gerado após o temporizador
                    btn_final = page.query_selector('a[download], a.btn-download-file, a:has-text("Download Now")')
                    if btn_final:
                        href_final = btn_final.get_attribute('href')
                        if href_final and href_final not in links_encontrados:
                            links_encontrados.append(href_final)
                        btn_final.click()
                        time.sleep(3)
                except Exception as e:
                    print(f"⚠️ Aviso Romsfun: {e}")

            else:
                # Clique genérico para outros sites
                seletores = 'a:has-text("Download"), a:has-text("Baixar"), button:has-text("Download"), .btn-download, #download-btn'
                botoes = page.query_selector_all(seletores)
                for btn in botoes[:3]:
                    try:
                        btn.click(timeout=3000)
                        time.sleep(2)
                    except Exception:
                        pass

            html_content = page.content()

            # Varredura extra em todos os links da árvore HTML
            hrefs = page.eval_on_selector_all('a[href]', 'elements => elements.map(e => e.href)')
            for h in hrefs:
                if any(k in h.lower() for k in ['mediafire.com', 'mega.nz', 'drive.google.com', 'modsfire.com', 'sharemods.com', 'send.cm', 'fastdrive', 'pixeldrain']) or re.search(r'\.(iso|cso|zip|7z|rar|chd)$', h, re.IGNORECASE):
                    if h not in links_encontrados and not h.endswith('#'):
                        links_encontrados.append(h)

        except Exception as e:
            print(f"⚠️ Erro no Playwright: {e}")
        finally:
            browser.close()

    # SAÍDA EM TEXTO NO TERMINAL DO GITHUB ACTIONS PARA VISUALIZAÇÃO DIRETA
    print("\n" + "="*50)
    print("🎯 LINK(S) EXTRAÍDO(S) COM SUCESSO:")
    for l in links_encontrados:
        print(f"🔗 {l}")
    print("="*50 + "\n")

    return html_content, links_encontrados

def classificar_links(links_capturados, url_alvo):
    link_jogo = ""
    link_savedata = ""
    link_texturas = ""

    for link in links_capturados:
        l_lower = link.lower()
        if any(k in l_lower for k in ['save', 'savedata', 'data']):
            if not link_savedata:
                link_savedata = link
        elif any(k in l_lower for k in ['texture', 'textura']):
            if not link_texturas:
                link_texturas = link
        else:
            if not link_jogo:
                link_jogo = link

    if not link_jogo and links_capturados:
        link_jogo = links_capturados[0]
    elif not link_jogo:
        link_jogo = url_alvo

    return link_jogo, link_savedata, link_texturas

def obter_dados_atuais_firebase(id_jogo):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"
    try:
        res = requests.get(endpoint, timeout=10)
        if res.status_code == 200 and res.json() is not None:
            return res.json()
    except Exception as e:
        print(f"⚠️ Erro ao consultar Firebase: {e}")
    return None

def salvar_ou_atualizar_firebase(id_jogo, nome_jogo, formato, url_alvo, link_jogo, link_savedata, link_texturas):
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
    time.sleep(random.uniform(2, 3))
    
    id_jogo = extrair_id_jogo(url_alvo)
    html, links_capturados = navegar_e_extrair_com_playwright(url_alvo)

    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|CHD|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    formato = identificar_formato(html + " " + url_alvo)
    link_jogo, link_savedata, link_texturas = classificar_links(links_capturados, url_alvo)

    salvar_ou_atualizar_firebase(
        id_jogo=id_jogo,
        nome_jogo=nome_limpo,
        formato=formato,
        url_alvo=url_alvo,
        link_jogo=link_jogo,
        link_savedata=link_savedata,
        link_texturas=link_texturas
    )

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
