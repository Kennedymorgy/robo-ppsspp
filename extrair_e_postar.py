import sys
import os
import re
import time
import random
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# CONFIGURAÇÕES DO BLOG E FIREBASE
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

# CONFIGURAÇÕES DE E-MAIL (Secrets do GitHub)
GMAIL_USER = os.environ.get("GMAIL_USER")        
GMAIL_PASS = os.environ.get("GMAIL_PASS")        
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")  

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/121.0.0.0 Safari/537.36"
]

def obter_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

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
    m = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', texto, re.IGNORECASE)
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
# RASPAGEM DE LINKS AVANÇADA (JOGO + SAVE DATA + TEXTURAS)
# -----------------------------------------------------------------------------

def extrair_links_completos(html, url_alvo):
    links_resultado = {
        "jogo": "",
        "savedata": "",
        "texturas": ""
    }

    # Busca todas as tags de link com atributos
    tags_a = re.findall(r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)

    for href, texto in tags_a:
        texto_limpo = re.sub(r'<[^>]+>', '', texto).lower()
        href_lower = href.lower()
        
        # Ignora redes sociais, navegação e anúncios conhecidos
        if any(domain in href_lower for domain in ['facebook.com', 'twitter.com', 'instagram.com', 'whatsapp.com', 'telegram.me', 'monetag', 'doubleclick']):
            continue

        # Detecta SaveData
        if any(k in texto_limpo or k in href_lower for k in ['save', 'savedata', 'data 100%']):
            if not links_resultado["savedata"]:
                links_resultado["savedata"] = href
                continue

        # Detecta Texturas
        if any(k in texto_limpo or k in href_lower for k in ['texture', 'textura', 'texturas']):
            if not links_resultado["texturas"]:
                links_resultado["texturas"] = href
                continue

        # Detecta Link do Jogo Principal (Servidores de Download e Extensões)
        if any(k in href_lower for k in ['mediafire.com', 'mega.nz', 'drive.google.com', 'modsfire.com', 'sharemods.com', 'send.cm', 'fastdrive', 'upload']):
            if not links_resultado["jogo"]:
                links_resultado["jogo"] = href

        elif re.search(r'\.(iso|cso|zip|7z|rar)$', href_lower):
            if not links_resultado["jogo"]:
                links_resultado["jogo"] = href

    # Fallback: Se não achou link direto de servidor, pega o link do botão de download da página
    if not links_resultado["jogo"]:
        for href, texto in tags_a:
            texto_limpo = re.sub(r'<[^>]+>', '', texto).lower()
            if any(k in texto_limpo for k in ['download', 'baixar', 'servidor', 'opção', 'link']):
                if not any(domain in href for domain in ['facebook.com', 'twitter.com', 'instagram.com', 'whatsapp.com', 'telegram.me']):
                    links_resultado["jogo"] = href
                    break

    # Se ainda assim não achar nada, usa a própria URL alvo como segurança
    if not links_resultado["jogo"]:
        links_resultado["jogo"] = url_alvo

    return links_resultado

def extrair_screenshots_limpas(html, url_capa):
    todas_imgs = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    prints_validas = []

    for img in todas_imgs:
        img_lower = img.lower()
        if img == url_capa or any(k in img_lower for k in ['logo', 'icon', 'banner', 'avatar', 'button', 'sidebar', 'related', 'favicon', 'widgets', 'ads']):
            continue
        
        if img not in prints_validas:
            prints_validas.append(img)
        
        if len(prints_validas) == 3:
            break

    return prints_validas

def extrair_dados_completos(html, url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    
    # Nome Limpo
    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PS2|PTBR|PT-BR|PPSSPP|Download|ROM|ROMs|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    idioma = identificar_idioma_preciso(html, url_alvo)
    tag_ptbr = " PT-BR" if "Português" in idioma else ""
    titulo_seo = f"{nome_limpo} ISO PPSSPP Download{tag_ptbr} Android / PC"

    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)

    # Capa
    todas_imgs = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    capa = todas_imgs[0] if todas_imgs else "https://k-404ppsspp.blogspot.com/favicon.ico"

    prints = extrair_screenshots_limpas(html, capa)
    links = extrair_links_completos(html, url_alvo)

    has_savedata = bool(links["savedata"])
    mod_status = "SaveData 100%" if has_savedata else "Nenhum"

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
        "link_jogo": links["jogo"],
        "link_savedata": links["savedata"],
        "link_texturas": links["texturas"],
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

    # ESTRUTURA HTML COM CARDS SEPARADOS PARA NÃO EMBALANÇAR/MISTURAR DADOS
    corpo_linhas = [
        '<!-- FOTO DE CAPA -->',
        '<div class="post-cover" style="text-align: center; margin-bottom: 20px;">',
        f'    <img src="{dados["capa"]}" alt="{dados["nome_limpo"]}" />',
        '</div>',
        '',
        f'BlackPostName={dados["nome_limpo"]}',
        '<!--more-->',
        '',
        '<!-- GRID DE INFORMAÇÕES DO JOGO (CADA ITEM EM SEU CARD) -->',
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

    corpo_linhas.extend([
        '<!-- ÁREA DE DOWNLOADS -->',
        '<div class="post-dl-box">',
        '    <div class="post-dl-title">📥 Links para Download Direto</div>',
        '',
        f'    <a href="{link_redirecionado_jogo}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-green">',
        f'        🚀 BAIXAR JOGO {dados["formato"]} ({dados["tamanho"]})',
        '    </a>'
    ])

    if dados['link_savedata']:
        corpo_linhas.extend([
            '',
            f'    <a href="{link_redirecionado_save}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-orange">',
            '        💾 BAIXAR SAVE DATA 100% (ZIP)',
            '    </a>'
        ])

    corpo_linhas.extend([
        '',
        '    <a href="https://k-404ppsspp.blogspot.com/p/emulador-ppsspp.html" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-purple">',
        '        📲 BAIXAR EMULADOR PPSSPP GOLD',
        '    </a>',
        '',
        '    <!-- AVISO CHAMATIVO E DESTACADO -->',
        '    <div class="dl-notice">',
        '        ⚠️ Se abrir algum anúncio ao clicar, basta fechar a guia e clicar novamente no botão!',
        '    </div>',
        '</div>',
        '',
        '<!-- COMO INSTALAR -->',
        '<div class="tutorial-box">',
        '    <div class="tutorial-title">📌 Como Instalar e Jogar:</div>',
        '    <ol class="tutorial-list">',
        f'        <li>Baixe o jogo em formato <strong>{dados["formato"]}</strong>' + (' e o arquivo do <strong>SaveData</strong> nos botões acima.' if dados['link_savedata'] else ' no botão acima.') + '</li>',
        '        <li>Instale o emulador <strong>PPSSPP Gold</strong> no seu celular Android ou PC.</li>'
    ])

    if dados['link_savedata']:
        corpo_linhas.append('        <li>Extraia o SaveData usando o aplicativo <strong>ZArchiver</strong> e mova a pasta extraída para a pasta <code>PSP/SAVEDATA</code> do seu dispositivo.</li>')

    corpo_linhas.extend([
        '        <li>Abra o emulador PPSSPP, navegue até a pasta onde salvou o jogo (geralmente em "Downloads") e clique para jogar!</li>',
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
        res = requests.get(url_alvo, headers=obter_headers(), timeout=15)
        if res.status_code == 200:
            dados = extrair_dados_completos(res.text, url_alvo)
            ja_cadastrado = jogo_ja_existe_no_firebase(dados['id'])
            
            salvar_no_firebase(dados)
            
            if not ja_cadastrado:
                enviar_post_para_blogger(dados)
            else:
                print(f"ℹ️ Jogo '{dados['nome_limpo']}' já cadastrado. Banco sincronizado sem post duplicado.")
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
