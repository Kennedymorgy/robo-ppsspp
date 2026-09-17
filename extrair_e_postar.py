import sys
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
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
    id_jogo = re.sub(r'(\.html|\.iso|\.cso|\.zip|\.7z|-psp-ptbr|-ppsspp|-psp)$', '', id_jogo, flags=re.IGNORECASE)
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
    return m.group(1).upper() if m else "600 MB"

def identificar_idioma_preciso(soup, texto_completo):
    # Procura na área principal de texto do artigo
    artigo = soup.find('article') or soup.find('div', class_=re.compile(r'content|post|entry', re.I))
    texto_alvo = artigo.get_text() if artigo else texto_completo
    texto_lower = texto_alvo.lower()

    if any(k in texto_lower for k in ["pt-br", "ptbr", "português", "portugues", "traduzido pt"]):
        return "Português (PT-BR)"
    elif any(k in texto_lower for k in ["espanhol", "spanish", "castellano"]):
        return "Espanhol"
    elif any(k in texto_lower for k in ["inglês", "ingles", "english"]):
        return "Inglês"
    
    return "Português (PT-BR)"

def extrair_link_download_profundo(soup, html, url_alvo):
    # 1. Busca por servidores diretos conhecidos
    padroes_diretos = [
        r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz|modsfire\.com|sharemods\.com|send\.cm|zippyshare\.com)[^"\']+)["\']',
        r'href=["\'](https?://[^"\']+\.(?:iso|cso|zip|7z|rar))["\']'
    ]
    for p in padroes_diretos:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return m.group(1)

    # 2. Busca analítica por tags <a> com botões de download
    for a in soup.find_all('a', href=True):
        href = a['href']
        texto_btn = a.get_text().lower()
        if any(k in texto_btn for k in ['baixar', 'download', 'servidor', 'link']) and not href.startswith('#'):
            if href.startswith('http'):
                return href

    return url_alvo

def extrair_screenshots_limpas(soup, url_capa):
    # Procura imagens contidas estritamente no corpo do artigo
    artigo = soup.find('article') or soup.find('div', class_=re.compile(r'content|post|entry', re.I))
    if not artigo:
        return []

    imgs_artigo = artigo.find_all('img')
    prints_validas = []

    for img in imgs_artigo:
        src = img.get('src') or img.get('data-src')
        if not src or not src.startswith('http'):
            continue

        # Evita a capa, ícones, avatares e imagens de posts relacionados/rodapé
        src_lower = src.lower()
        if src == url_capa or any(k in src_lower for k in ['logo', 'icon', 'banner', 'avatar', 'button', 'sidebar', 'related']):
            continue
        
        prints_validas.append(src)
        if len(prints_validas) == 3:
            break

    return prints_validas

def extrair_dados_completos(html, url_alvo):
    soup = BeautifulSoup(html, 'html.parser')
    id_jogo = extrair_id_jogo(url_alvo)
    
    # Nome Limpo para BlackPostName
    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = soup.find('title')
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PTBR|PT-BR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', m_titulo.string).strip()

    idioma = identificar_idioma_preciso(soup, html)
    tag_ptbr = " PT-BR" if "Português" in idioma else ""
    titulo_seo = f"{nome_limpo} ISO PPSSPP Download{tag_ptbr} Android / PC"

    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)

    # Capa
    primeira_img = soup.find('img')
    capa = primeira_img.get('src') if primeira_img and primeira_img.get('src') else "https://k-404ppsspp.blogspot.com/favicon.ico"

    # Screenshots filtradas
    prints = extrair_screenshots_limpas(soup, capa)

    # Link do Botão
    link_direto = extrair_link_download_profundo(soup, html, url_alvo)

    return {
        "id": id_jogo,
        "nome_limpo": nome_limpo,
        "titulo_seo": titulo_seo,
        "capa": capa,
        "prints": prints,
        "formato": formato,
        "tamanho": tamanho,
        "idioma": idioma,
        "link_direto": link_direto,
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
        "link_direto": dados["link_direto"],
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

    link_redirecionado = f"{URL_WORKER}?id={dados['id']}"

    # MONTAGEM FORMATADA COM QUEBRAS DE LINHA EXPLICITAS PARA O TEMA DO BLOGGER
    corpo_linhas = [
        '<!-- FOTO DE CAPA -->',
        '<div class="post-cover" style="text-align: center; margin-bottom: 20px;">',
        f'    <img src="{dados["capa"]}" alt="{dados["nome_limpo"]}" />',
        '</div>',
        '',
        f'BlackPostName={dados["nome_limpo"]}',
        '<!--more-->',
        '<!-- VARIÁVEIS DE INFORMAÇÃO -->',
        'InfoPlataforma=PPSSPP (Android / PC)',
        f'InfoIdioma={dados["idioma"]}',
        f'InfoTamanho={dados["tamanho"]}',
        f'InfoFormato={dados["formato"]}',
        'InfoMod=SaveData 100%',
        '',
        '<!-- DESCRIÇÃO INICIAL -->',
        f'<p>Baixe agora <b>{dados["nome_limpo"]}</b> para o emulador PPSSPP no Android e PC. Jogo completo em formato {dados["formato"]} ({dados["tamanho"]}) em {dados["idioma"]} com ótimos gráficos e 100% jogável!</p>',
        ''
    ]

    # Insere screenshots apenas se existirem fotos reais do post
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
        f'    <a href="{link_redirecionado}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-green">',
        f'        🚀 BAIXAR JOGO {dados["formato"]} ({dados["tamanho"]})',
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
        f'        <li>Baixe o jogo em formato <strong>{dados["formato"]}</strong> no botão acima.</li>',
        '        <li>Instale o emulador <strong>PPSSPP Gold</strong> no seu celular Android ou PC.</li>',
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
