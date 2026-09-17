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

# DICIONÁRIO DE CATEGORIAS COMPATÍVEL COM AS LABELS DO SEU TEMA
MAPA_CATEGORIAS = {
    "ptbr": ["pt-br", "ptbr", "dublado", "legendado", "portugues", "traduzido", "pt br"],
    "Mods": ["mod", "mods", "save", "textura", "camera", "cheat", "cheto"],
    "Luta": ["tekken", "dragon ball", "naruto", "mortal kombat", "street fighter", "bleach", "wwe", "ufc", "guilty gear", "blazblue", "injustice"],
    "acao": ["god of war", "gta", "grand theft auto", "assassin", "spiderman", "batman", "metal gear", "crisis core", "dante", "payback"],
    "Futebol": ["pes", "fifa", "e football", "winning eleven", "bomba patch"],
    "Corrida": ["need for speed", "nfs", "gran turismo", "burnout", "midnight club", "asphalt", "flatout", "ridge racer", "fr legends"],
    "Aventura": ["tomb raider", "monster hunter", "lego", "prince of persia", "daxter", "jack", "kingdom hearts", "subway surfers"],
    "App Emulador": ["emulador", "ppsspp", "gold", "apk"]
}

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
    elif "ZIP" in texto_upper or ".ZIP" in texto_upper:
        return "ZIP"
    elif "7Z" in texto_upper or "RAR" in texto_upper:
        return "7Z / RAR"
    return "ISO"

def identificar_tamanho(texto):
    m = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', texto, re.IGNORECASE)
    return m.group(1).upper() if m else "N/A"

def identificar_categorias(nome_jogo):
    nome_lower = nome_jogo.lower()
    categorias = ["PPSSPP"]
    
    for cat, palavras in MAPA_CATEGORIAS.items():
        if any(p in nome_lower for p in palavras):
            categorias.append(cat)
            
    if len(categorias) == 1:
        categorias.append("acao")
        
    return list(set(categorias))

def extrair_dados_completos(html, url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    
    nome_jogo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_jogo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PTBR|PT-BR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)
    categorias = identificar_categorias(nome_jogo)

    imagens = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    imagens_filtradas = [img for img in imagens if not any(k in img for k in ["logo", "icon", "avatar", "banner", "button"])]
    
    capa = imagens_filtradas[0] if imagens_filtradas else "https://k-404ppsspp.blogspot.com/favicon.ico"
    prints = imagens_filtradas[1:4] if len(imagens_filtradas) > 1 else []

    link_direto = None
    m_link = re.search(r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz|modsfire\.com|sharemods\.com)[^"\']+)["\']', html, re.IGNORECASE)
    if m_link:
        link_direto = m_link.group(1)

    return {
        "id": id_jogo,
        "nome": nome_jogo,
        "capa": capa,
        "prints": prints,
        "formato": formato,
        "tamanho": tamanho,
        "categorias": categorias,
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
        "nome": dados["nome"],
        "tipo": f"PPSSPP {dados['formato']}"
    }
    try:
        requests.patch(endpoint, json=payload, timeout=10)
        print(f"✅ Firebase Atualizado com sucesso: {dados['id']}")
    except Exception as e:
        print(f"❌ Erro ao salvar no Firebase: {e}")

def enviar_post_para_blogger(dados):
    if not GMAIL_USER or not GMAIL_PASS or not BLOGGER_EMAIL:
        print("⚠️ Credenciais de e-mail não configuradas no GitHub Secrets.")
        return

    link_redirecionado = f"{URL_WORKER}?id={dados['id']}"

    # ESTRUTURA HTML AJUSTADA PARA O JS DO SEU TEMA (.post-dl-box e .btn-dl)
    html_content = f"""
    <div style="text-align: center; font-family: sans-serif;">
        <div class="separator" style="clear: both; text-align: center; margin-bottom: 15px;">
            <img src="{dados['capa']}" alt="{dados['nome']}" style="max-width: 100%; height: auto; border-radius: 8px;" />
        </div>

        <p>Faça o download do jogo <b>{dados['nome']}</b> em formato {dados['formato']} ({dados['tamanho']}) testado e 100% funcional no emulador PPSSPP.</p>
    """
    
    if dados['prints']:
        html_content += '<div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin: 15px 0;">'
        for img in dados['prints']:
            html_content += f'<img src="{img}" style="width: 48%; max-width: 300px; border-radius: 6px;" />'
        html_content += '</div>'

    html_content += f"""
        <div class="post-dl-box" style="margin: 25px 0;">
            <a class="btn-dl" href="{link_redirecionado}" style="background-color: #28a745; color: #ffffff; padding: 15px 30px; font-size: 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                🚀 DOWNLOAD {dados['formato']}
            </a>
        </div>
    </div>
    """

    hashtags_categorias = " ".join([f"#{cat}" for cat in dados['categorias']])
    corpo_final = f"{html_content}\n\n<p>{hashtags_categorias}</p>"

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = BLOGGER_EMAIL
    msg['Subject'] = f"{dados['nome']} ISO PPSSPP"
    msg.attach(MIMEText(corpo_final, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"🎉 POST PUBLICADO COM SUCESSO: {dados['nome']} | Categorias: {dados['categorias']}")
    except Exception as e:
        print(f"❌ Erro SMTP ao enviar postagem: {e}")

def processar_url(url_alvo):
    time.sleep(random.uniform(2, 4))
    try:
        res = requests.get(url_alvo, headers=obter_headers(), timeout=15)
        if res.status_code == 200:
            dados = extrair_dados_completos(res.text, url_alvo)
            if dados['link_direto']:
                ja_cadastrado = jogo_ja_existe_no_firebase(dados['id'])
                salvar_no_firebase(dados)
                
                if not ja_cadastrado:
                    enviar_post_para_blogger(dados)
                else:
                    print(f"ℹ️ Jogo '{dados['nome']}' já cadastrado. Banco sincronizado sem post duplicado.")
            else:
                print(f"⚠️ Link direto (Mediafire/Drive/Mega/etc) não encontrado na URL: {url_alvo}")
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
