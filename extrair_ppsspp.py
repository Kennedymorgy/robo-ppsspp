import sys
import os
import re
import time
import random
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# CONFIGURAÇÕES SEU BLOG E FIREBASE
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
URL_WORKER = "https://orange-star-d066.claudiokennedymorgy.workers.dev"

# CONFIGURAÇÕES DE E-MAIL (Usadas nas Secrets do GitHub)
GMAIL_USER = os.environ.get("GMAIL_USER")        # Seu email do gmail que vai enviar
GMAIL_PASS = os.environ.get("GMAIL_PASS")        # Senha de app do Gmail
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")  # O e-mail secreto do seu Blogger

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
    id_jogo = re.sub(r'(\.html|\.iso|-psp-ptbr|-ppsspp|-psp)$', '', id_jogo, flags=re.IGNORECASE)
    return re.sub(r'[^a-zA-Z0-9_-]', '', id_jogo)

def extrair_dados_completos(html, url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    nome_jogo = id_jogo.replace('-', ' ').title()
    
    # Extrai Título
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_jogo = re.sub(r'(?i)\s*(?:ISO|PSP|PTBR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    # Extrai Screenshots / Imagens
    imagens = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    imagens_filtradas = [img for img in imagens if not any(k in img for k in ["logo", "icon", "avatar", "banner"])]
    
    capa = imagens_filtradas[0] if imagens_filtradas else "https://k-404ppsspp.blogspot.com/favicon.ico"
    prints = imagens_filtradas[1:4] if len(imagens_filtradas) > 1 else []

    # Extrai Link
    link_direto = None
    m_link = re.search(r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz|modsfire\.com|sharemods\.com)[^"\']+)["\']', html, re.IGNORECASE)
    if m_link:
        link_direto = m_link.group(1)

    return {
        "id": id_jogo,
        "nome": nome_jogo,
        "capa": capa,
        "prints": prints,
        "link_direto": link_direto,
        "url_original": url_alvo
    }

def jogo_ja_existe_no_firebase(id_jogo):
    """Verifica se o jogo já foi salvo no Firebase anteriormente."""
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
        "tipo": "PPSSPP ISO"
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

    # Monta HTML bonito do Post
    html_content = f"""
    <div style="text-align: center;">
        <img src="{dados['capa']}" style="max-width: 100%; height: auto; border-radius: 8px;" /><br/><br/>
        <h3>Baixar {dados['nome']} ISO PPSSPP</h3>
        <p>Faça o download do jogo {dados['nome']} em alta qualidade para o seu emulador PPSSPP Android e PC.</p>
    """
    
    if dados['prints']:
        html_content += "<h4>Screenshots do Jogo:</h4>"
        for img in dados['prints']:
            html_content += f'<img src="{img}" style="max-width: 48%; margin: 1%; border-radius: 5px;" />'

    html_content += f"""
        <br/><br/>
        <a href="{link_redirecionado}" target="_blank" style="background-color: #28a745; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
            🚀 DOWNLOAD ISO PPSSPP
        </a>
    </div>
    """

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = BLOGGER_EMAIL
    msg['Subject'] = f"{dados['nome']} ISO PPSSPP"
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"🎉 POST PUBLICADO NO BLOGGER: {dados['nome']}")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail para Blogger: {e}")

def processar_url(url_alvo):
    time.sleep(random.uniform(2, 4))
    try:
        res = requests.get(url_alvo, headers=obter_headers(), timeout=15)
        if res.status_code == 200:
            dados = extrair_dados_completos(res.text, url_alvo)
            if dados['link_direto']:
                ja_cadastrado = jogo_ja_existe_no_firebase(dados['id'])
                
                # Atualiza sempre o link direto no Firebase
                salvar_no_firebase(dados)
                
                # Só envia o e-mail para criar o POST se for um jogo NOVO
                if not ja_cadastrado:
                    enviar_post_para_blogger(dados)
                else:
                    print(f"ℹ️ Jogo '{dados['nome']}' já existe no blog. Link atualizado no Firebase sem duplicar post.")
            else:
                print("⚠️ Link de download não encontrado.")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                for linha in f:
                    if linha.strip():
                        processar_url(linha.strip())
