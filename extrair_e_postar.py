import sys
import os
import re
import time
import random
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# CONFIGURAÇÕES DO BLOG E FIREBASE
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

# CONFIGURAÇÕES DE E-MAIL (Secrets do GitHub)
GMAIL_USER = os.environ.get("GMAIL_USER")        
GMAIL_PASS = os.environ.get("GMAIL_PASS")        
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")  

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
    return "ISO"

def identificar_tamanho(texto):
    # Captura variações de GB, MB, KB (maiúsculas e minúsculas)
    m = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB|KB))', texto, re.IGNORECASE)
    return m.group(1).upper() if m else "1.1 GB"

def identificar_idioma_preciso(html_completo, url_alvo):
    if "isoptbr.com" in url_alvo:
        return "Português (PT-BR)"
    
    texto_lower = html_completo.lower()
    if any(k in texto_lower for k in ["pt-br", "ptbr", "português", "portugues", "dublado pt"]):
        return "Português (PT-BR)"
    elif any(k in texto_lower for k in ["espanhol", "spanish", "castellano"]):
        return "Espanhol / Inglês"
    elif any(k in texto_lower for k in ["inglês", "english", "usa"]):
        return "Inglês"
    
    return "Espanhol / Inglês"

# -----------------------------------------------------------------------------
# NAVEGADOR SIMULADO (ANDROID 13) COM PLAYWRIGHT
# -----------------------------------------------------------------------------

def navegar_e_extrair_com_playwright(url_alvo):
    links_encontrados = []
    html_content = ""
    
    with sync_playwright() as p:
        dispositivo_pixel = p.devices['Pixel 5']
        # CORREÇÃO: Sobrescreve o user_agent no dicionário do dispositivo para não dar erro de duplicidade
        dispositivo_pixel['user_agent'] = "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**dispositivo_pixel)
        page = context.new_page()

        def monitorar_requisicoes(request):
            url = request.url
            if any(k in url.lower() for k in ['mediafire.com', 'mega.nz', 'drive.google.com', 'modsfire.com', 'sharemods.com', 'send.cm', 'fastdrive']) or re.search(r'\.(iso|cso|zip|7z|rar)$', url, re.IGNORECASE):
                if url not in links_encontrados:
                    links_encontrados.append(url)

        page.on("request", monitorar_requisicoes)

        try:
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            seletor_botoes = 'a:has-text("Download"), a:has-text("Baixar"), button:has-text("Download"), button:has-text("Baixar"), .btn-download, #download-btn'
            botoes = page.query_selector_all(seletor_botoes)
            
            for btn in botoes[:3]:
                try:
                    btn.click(timeout=3000)
                    time.sleep(2)
                except Exception:
                    pass

            html_content = page.content()

            hrefs = page.eval_on_selector_all('a[href]', 'elements => elements.map(e => e.href)')
            for h in hrefs:
                if any(k in h.lower() for k in ['mediafire.com', 'mega.nz', 'drive.google.com', 'modsfire.com', 'sharemods.com', 'send.cm', 'fastdrive']) or re.search(r'\.(iso|cso|zip|7z|rar)$', h, re.IGNORECASE):
                    if h not in links_encontrados:
                        links_encontrados.append(h)

        except Exception as e:
            print(f"⚠️ Erro ao carregar página via Playwright: {e}")
        finally:
            browser.close()

    return html_content, links_encontrados

def extrair_screenshots_limpas(html, url_capa):
    todas_imgs = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    prints_validas = []

    # Palavras-chave de imagens a ignorar (banners, logos, ícones e widgets)
    palavras_ignorar = ['logo', 'icon', 'banner', 'avatar', 'button', 'sidebar', 'related', 'favicon', 'widgets', 'ads', 'ad-', 'header', 'footer']

    for img in todas_imgs:
        img_lower = img.lower()
        if img == url_capa or any(k in img_lower for k in palavras_ignorar):
            continue
        
        if img not in prints_validas:
            prints_validas.append(img)
        
        if len(prints_validas) == 3:
            break

    return prints_validas

def extrair_dados_completos(url_alvo):
    html, links_capturados = navegar_e_extrair_com_playwright(url_alvo)
    
    id_jogo = extrair_id_jogo(url_alvo)
    
    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    idioma = identificar_idioma_preciso(html, url_alvo)
    tag_ptbr = " PT-BR" if "Português" in idioma else ""
    titulo_seo = f"{nome_limpo} ISO PPSSPP Download{tag_ptbr} Android / PC"

    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)

    todas_imgs = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    capa = todas_imgs[0] if todas_imgs else "https://k-404ppsspp.blogspot.com/favicon.ico"

    prints = extrair_screenshots_limpas(html, capa)

    link_jogo = links_capturados[0] if links_capturados else url_alvo
    link_savedata = ""
    link_texturas = ""

    for l in links_capturados:
        l_lower = l.lower()
        if any(k in l_lower for k in ['save', 'savedata', 'data']):
            link_savedata = l
        elif any(k in l_lower for k in ['texture', 'textura']):
            link_texturas = l

    mod_status = "SaveData 100%" if link_savedata else "Nenhum"

    return {
        "id": id_jogo,
        "nome_limpo": nome_limpo,
        "titulo_seo": titulo_seo,
        "capa": capa,
        "prints": prints,
        "formato": formato,
        "tamanho": tamanho,
        "idioma": idioma,
        "mod": mod_status,
        "link_jogo": link_jogo,
        "link_savedata": link_savedata,
        "link_texturas": link_texturas,
        "url_original": url_alvo
    }

def jogo_ja_existe_no_firebase(id_jogo):
    try:
        endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"
        res = requests.get(endpoint, timeout=10)
        return res.status_code == 200 and res.json() is not None
    except Exception:
        return False

def salvar_no_firebase(dados):
    endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{dados['id']}.json"
    payload = {
        "url_original": dados["url_original"],
        "link_direto": dados["link_jogo"],
        "link_savedata": dados["link_savedata"],
        "link_texturas": dados["link_texturas"],
        "nome": dados["nome_limpo"],
        "tipo": f"PPSSPP {dados['formato']}"
    }
    try:
        requests.patch(endpoint, json=payload, timeout=10)
        print(f"✅ Firebase Atualizado: {dados['id']}")
    except Exception as e:
        print(f"❌ Erro Firebase: {e}")

def enviar_post_para_blogger(dados):
    if not GMAIL_USER or not GMAIL_PASS or not BLOGGER_EMAIL:
        print("⚠️ Credenciais de e-mail não configuradas no GitHub Secrets.")
        return

    link_redirecionado_jogo = f"{URL_WORKER}?id={dados['id']}"
    link_redirecionado_save = f"{URL_WORKER}?id={dados['id']}&type=save" if dados['link_savedata'] else ""
    link_redirecionado_tex = f"{URL_WORKER}?id={dados['id']}&type=texture" if dados['link_texturas'] else ""

    corpo_linhas = [
        '<!-- FOTO DE CAPA -->',
        '<div class="post-cover" style="text-align: center; margin-bottom: 20px;">',
        f'    <img src="{dados["capa"]}" alt="{dados["nome_limpo"]}" />',
        '</div>',
        '',
        f'BlackPostName={dados["nome_limpo"]}',
        '<!--more-->',
        '',
        '<!-- GRID DE INFORMAÇÕES DO JOGO -->',
        '<div class="info-grid">',
        '    <div class="info-card">',
        '        <span class="info-label">📱 NOME</span>',
        f'        <span class="info-value">{dados["nome_limpo"]}</span>',
        '    </div>',
        '    <div class="info-card">',
        '        <span class="info-label">🔧 PLATAFORMA</span>',
        '        <span class="info-value">PPSSPP (Android / PC)</span>',
        '    </div>',
        '    <div class="info-card">',
        '        <span class="info-label">🌐 IDIOMA</span>',
        f'        <span class="info-value">{dados["idioma"]}</span>',
        '    </div>',
        '    <div class="info-card">',
        '        <span class="info-label">📦 TAMANHO</span>',
        f'        <span class="info-value">{dados["tamanho"]}</span>',
        '    </div>',
        '    <div class="info-card">',
        '        <span class="info-label">⚡ FORMATO</span>',
        f'        <span class="info-value">{dados["formato"]}</span>',
        '    </div>',
        '    <div class="info-card">',
        '        <span class="info-label">🎮 EXTRA</span>',
        f'        <span class="info-value">{dados["mod"]}</span>',
        '    </div>',
        '</div>',
        '',
        '<!-- DESCRIÇÃO INICIAL -->',
        f'<p>Baixe agora <b>{dados["nome_limpo"]}</b> para o emulador PPSSPP no Android e PC. Jogo completo em formato {dados["formato"]} ({dados["tamanho"]}) em {dados["idioma"]} com ótimos gráficos e 100% jogável!</p>',
        ''
    ]

    # GALERIA CONDICIONAL DE SCREENSHOTS (SÓ CRIA SE HOUVER IMAGENS VÁLIDAS)
    if dados['prints']:
        corpo_linhas.extend([
            '<!-- GALERIA DE SCREENSHOTS ESTILO PLAY STORE -->',
            '<div class="screenshots-wrapper">',
            '    <div class="screenshots-header-title">📸 Capturas de Tela do Jogo</div>',
            '    <div class="screenshots-box">'
        ])
        for i, img in enumerate(dados['prints'], start=1):
            corpo_linhas.append(f'        <img src="{img}" alt="{dados["nome_limpo"]} Gameplay {i}"/>')
        
        corpo_linhas.extend([
            '    </div>',
            '    <div class="scroll-indicator">👈 Deslize para o lado para ver mais fotos 📸 👉</div>',
            '</div>',
            ''
        ])

    # BOTÕES DINÂMICOS DE DOWNLOAD
    corpo_linhas.extend([
        '<!-- ÁREA DE DOWNLOADS -->',
        '<div class="post-dl-box">',
        '    <div class="post-dl-title">📥 Links para Download Direto</div>',
        ''
    ])

    if dados['link_jogo']:
        corpo_linhas.append(
            f'    <a href="{link_redirecionado_jogo}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-green">'
            f'🚀 BAIXAR JOGO {dados["formato"]} ({dados["tamanho"]})</a>'
        )

    if dados['link_savedata']:
        corpo_linhas.append(
            f'    <a href="{link_redirecionado_save}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-orange">'
            f'💾 BAIXAR SAVE DATA 100% (ZIP)</a>'
        )

    if dados['link_texturas']:
        corpo_linhas.append(
            f'    <a href="{link_redirecionado_tex}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-blue">'
            f'🎨 BAIXAR TEXTURAS HD (ZIP)</a>'
        )

    corpo_linhas.extend([
        '    <a href="https://k-404ppsspp.blogspot.com/p/emulador-ppsspp.html" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-purple">',
        '        📲 BAIXAR EMULADOR PPSSPP GOLD',
        '    </a>',
        '',
        '    <div class="dl-notice">',
        '        ⚠️ Se abrir algum anúncio ao clicar, basta fechar a guia e clicar novamente no botão!',
        '    </div>',
        '</div>',
        '',
        '<!-- COMO INSTALAR -->',
        '<div class="tutorial-box">',
        '    <div class="tutorial-title">📌 Como Instalar e Jogar:</div>',
        '    <ol class="tutorial-list">',
        f'        <li>Baixe o jogo em formato <strong>{dados["formato"]}</strong>' + (' e o arquivo de dados adicional nos botões acima.' if (dados['link_savedata'] or dados['link_texturas']) else ' no botão acima.') + '</li>',
        '        <li>Instale o emulador <strong>PPSSPP Gold</strong> no seu celular Android ou PC.</li>'
    ])

    if dados['link_savedata']:
        corpo_linhas.append('        <li>Extraia o SaveData usando o aplicativo <strong>ZArchiver</strong> e mova a pasta extraída para a pasta <code>PSP/SAVEDATA</code>.</li>')

    corpo_linhas.extend([
        '        <li>Abra o emulador PPSSPP, navegue até a pasta onde salvou o arquivo e inicie a partida!</li>',
        '    </ol>',
        '</div>'
    ])

    html_content = "\n".join(corpo_linhas)

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = BLOGGER_EMAIL
    msg['Subject'] = dados['titulo_seo']
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"🎉 POST PUBLICADO COM SUCESSO: {dados['titulo_seo']}")
    except Exception as e:
        print(f"❌ Erro ao enviar postagem: {e}")

def processar_url(url_alvo):
    time.sleep(random.uniform(2, 4))
    try:
        dados = extrair_dados_completos(url_alvo)
        ja_cadastrado = jogo_ja_existe_no_firebase(dados['id'])
        
        salvar_no_firebase(dados)
        
        if not ja_cadastrado:
            enviar_post_para_blogger(dados)
        else:
            print(f"ℹ️ Jogo '{dados['nome_limpo']}' já cadastrado. Links sincronizados no Firebase.")
    except Exception as e:
        print(f"❌ Falha ao processar a URL {url_alvo}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                for linha in f:
                    if linha.strip():
                        processar_url(linha.strip())
