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

# CONFIGURAÇÕES DE E-MAIL (Buscadas das Secrets do GitHub)
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

def identificar_idiomas(texto):
    texto_lower = texto.lower()
    idiomas = []
    
    if any(k in texto_lower for k in ["ptbr", "pt-br", "português", "portugues", "dublado", "traduzido"]):
        idiomas.append("Português (PT-BR)")
    if any(k in texto_lower for k in ["espanhol", "spanish", "castellano", "esp"]):
        idiomas.append("Espanhol")
    if any(k in texto_lower for k in ["inglês", "ingles", "english", "usa", "en"]):
        idiomas.append("Inglês")
    if any(k in texto_lower for k in ["francês", "frances", "french"]):
        idiomas.append("Francês")
    if any(k in texto_lower for k in ["japonês", "japones", "japanese", "jp"]):
        idiomas.append("Japonês")

    return " / ".join(idiomas) if idiomas else "Português / Inglês"

def extrair_dados_completos(html, url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    
    # Nome Limpo do Jogo para o BlackPostName
    nome_limpo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_limpo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PTBR|PT-BR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    # Título SEO Otimizado para Buscas do Google
    idiomas_detectados = identificar_idiomas(html + " " + url_alvo)
    tag_ptbr = " PT-BR" if "Português" in idiomas_detectados else ""
    titulo_seo = f"{nome_limpo} ISO PPSSPP Download{tag_ptbr} Android / PC"

    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)

    # Captura de Imagens
    imagens = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    imagens_filtradas = [img for img in imagens if not any(k in img for k in ["logo", "icon", "avatar", "banner", "button"])]
    
    capa = imagens_filtradas[0] if imagens_filtradas else "https://k-404ppsspp.blogspot.com/favicon.ico"
    prints = imagens_filtradas[1:4] if len(imagens_filtradas) > 1 else []

    # Busca Avançada pelo Link Direto de Download
    link_direto = None
    padroes_links = [
        r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz|modsfire\.com|sharemods\.com)[^"\']+)["\']',
        r'href=["\'](https?://[^"\']+\.(?:iso|cso|zip|7z|rar))["\']'
    ]
    for p in padroes_links:
        m_link = re.search(p, html, re.IGNORECASE)
        if m_link:
            link_direto = m_link.group(1)
            break

    # Se não achar o link direto, usa a própria URL alvo para garantir que o Worker redirecione
    if not link_direto:
        link_direto = url_alvo

    return {
        "id": id_jogo,
        "nome_limpo": nome_limpo,
        "titulo_seo": titulo_seo,
        "capa": capa,
        "prints": prints,
        "formato": formato,
        "tamanho": tamanho,
        "idioma": idiomas_detectados,
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

    # MONTAGEM RIGOROSA COM QUEBRAS DE LINHA REAIS (\n) PARA O TEMA LER AS VARIÁVEIS
    html_content = (
        f'<!-- FOTO DE CAPA -->\n'
        f'<div class="post-cover" style="text-align: center; margin-bottom: 20px;">\n'
        f'    <img src="{dados["capa"]}" alt="{dados["nome_limpo"]}" />\n'
        f'</div>\n\n'
        f'BlackPostName={dados["nome_limpo"]}\n'
        f'<!--more-->\n'
        f'<!-- VARIÁVEIS DE INFORMAÇÃO -->\n'
        f'InfoPlataforma=PPSSPP (Android / PC)\n'
        f'InfoIdioma={dados["idioma"]}\n'
        f'InfoTamanho={dados["tamanho"]}\n'
        f'InfoFormato={dados["formato"]}\n'
        f'InfoMod=SaveData 100%\n\n'
        f'<!-- DESCRIÇÃO INICIAL -->\n'
        f'<p>Baixe agora <b>{dados["nome_limpo"]}</b> para o emulador PPSSPP no Android e PC. Jogo completo em formato {dados["formato"]} ({dados["tamanho"]}) em {dados["idioma"]} com ótimos gráficos e 100% jogável!</p>\n\n'
    )

    if dados['prints']:
        html_content += (
            '<!-- GALERIA DE SCREENSHOTS ESTILO PLAY STORE -->\n'
            '<div class="screenshots-wrapper">\n'
            '    <div class="screenshots-header-title">📸 Capturas de Tela do Jogo</div>\n'
            '    <div class="screenshots-box">\n'
        )
        for i, img in enumerate(dados['prints'], start=1):
            html_content += f'        <img src="{img}" alt="{dados["nome_limpo"]} Gameplay {i}"/>\n'
        
        html_content += (
            '    </div>\n'
            '    <div class="scroll-indicator">👈 Deslize para o lado para ver mais fotos 📸 👉</div>\n'
            '</div>\n\n'
        )

    html_content += (
        '<!-- ÁREA DE DOWNLOADS -->\n'
        '<div class="post-dl-box">\n'
        '    <div class="post-dl-title">📥 Links para Download Direto</div>\n\n'
        f'    <a href="{link_redirecionado}" target="_blank" rel="nofollow noopener" class="btn-dl btn-dl-green">\n'
        f'        🚀 BAIXAR JOGO {dados["formato"]} ({dados["tamanho"]})\n'
        '    </a>\n\n'
        '    <!-- AVISO CHAMATIVO E DESTACADO -->\n'
        '    <div class="dl-notice">\n'
        '        ⚠️ Se abrir algum anúncio ao clicar, basta fechar a guia e clicar novamente no botão!\n'
        '    </div>\n'
        '</div>\n\n'
        '<!-- COMO INSTALAR -->\n'
        '<div class="tutorial-box">\n'
        '    <div class="tutorial-title">📌 Como Instalar e Jogar:</div>\n'
        '    <ol class="tutorial-list">\n'
        f'        <li>Baixe o jogo em formato <strong>{dados["formato"]}</strong> no botão acima.</li>\n'
        '        <li>Instale o emulador <strong>PPSSPP Gold</strong> no seu celular Android ou PC.</li>\n'
        '        <li>Abra o emulador PPSSPP, navegue até a pasta onde salvou o jogo (geralmente em "Downloads") e clique para jogar!</li>\n'
        '    </ol>\n'
        '</div>'
    )

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
