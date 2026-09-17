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

# CONFIGURAÇÕES DE E-MAIL (GitHub Secrets)
GMAIL_USER = os.environ.get("GMAIL_USER")        
GMAIL_PASS = os.environ.get("GMAIL_PASS")        
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")  

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/121.0.0.0 Safari/537.36"
]

# DICIONÁRIO DE CATEGORIAS AUTOMÁTICAS
MAPA_CATEGORIAS = {
    "Luta": ["tekken", "dragon ball", "naruto", "mortal kombat", "street fighter", "bleach", "wwe", "ufc", "guilty gear", "blazblue", "injustice"],
    "Futebol": ["pes", "fifa", "e football", "winning eleven", "bomba patch"],
    "Corrida": ["need for speed", "nfs", "gran turismo", "burnout", "midnight club", "asphalt", "flatout", "ridge racer"],
    "Ação": ["god of war", "gta", "grand theft auto", "assassin", "spiderman", "batman", "metal gear", "crisis core", "dante"],
    "Aventura": ["tomb raider", "monster hunter", "lego", "prince of persia", "daxter", "jack", "kingdom hearts"],
    "Tiro": ["call of duty", "medal of honor", "siphon filter", "killzone", "socom", "star wars", "battlefield"],
    "Anime": ["naruto", "dragon ball", "bleach", "one piece", "fate", "sword art", "yu gi oh"]
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
    return "ISO"  # Padrão para PPSSPP

def identificar_tamanho(texto):
    m = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', texto, re.IGNORECASE)
    return m.group(1).upper() if m else "N/A"

def identificar_categorias(nome_jogo):
    nome_lower = nome_jogo.lower()
    categorias = ["PPSSPP", "PSP"]
    
    for cat, palavras in MAPA_CATEGORIAS.items():
        if any(p in nome_lower for p in palavras):
            categorias.append(cat)
            
    if len(categorias) == 2:  # Caso não encontre palavra específica
        categorias.append("Ação")
        
    return categorias

def extrair_dados_completos(html, url_alvo):
    id_jogo = extrair_id_jogo(url_alvo)
    
    # Extrai Título Limpo
    nome_jogo = id_jogo.replace('-', ' ').title()
    m_titulo = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m_titulo:
        nome_jogo = re.sub(r'(?i)\s*(?:ISO|CSO|ZIP|PSP|PTBR|PT-BR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', m_titulo.group(1)).strip()

    # Formato e Peso
    formato = identificar_formato(html + " " + url_alvo)
    tamanho = identificar_tamanho(html)
    categorias = identificar_categorias(nome_jogo)

    # Extrai Screenshots / Imagens
    imagens = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
    imagens_filtradas = [img for img in imagens if not any(k in img for k in ["logo", "icon", "avatar", "banner", "button"])]
    
    capa = imagens_filtradas[0] if imagens_filtradas else "https://k-404ppsspp.blogspot.com/favicon.ico"
    prints = imagens_filtradas[1:4] if len(imagens_filtradas) > 1 else []

    # Extrai Link Direto de Download
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
        print(f"✅ Firebase Atualizado: {dados['id']}")
    except Exception as e:
        print(f"❌ Erro Firebase: {e}")

def enviar_post_para_blogger(dados):
    if not GMAIL_USER or not GMAIL_PASS or not BLOGGER_EMAIL:
        print("⚠️ Credenciais de e-mail não configuradas no GitHub Secrets.")
        return

    link_redirecionado = f"{URL_WORKER}?id={dados['id']}"

    # Monta HTML Estruturado do Post com Metadados
    html_content = f"""
    <div class="post-body-container" style="text-align: center; font-family: sans-serif;">
        <!-- IMAGEM DE CAPA PRINCIPAL -->
        <div class="separator" style="clear: both; text-align: center; margin-bottom: 15px;">
            <img src="{dados['capa']}" alt="Baixar {dados['nome']} PPSSPP" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
        </div>

        <!-- TABELA DE INFORMAÇÕES DO JOGO -->
        <table style="width: 100%; margin: 15px 0; border-collapse: collapse; text-align: left; background: #f9f9f9; border-radius: 8px; padding: 10px;">
            <tr><td style="padding: 8px; font-weight: bold;">🎮 Jogo:</td><td style="padding: 8px;">{dados['nome']}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">📁 Formato:</td><td style="padding: 8px;">{dados['formato']}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">💾 Tamanho:</td><td style="padding: 8px;">{dados['tamanho']}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">📱 Plataforma:</td><td style="padding: 8px;">PPSSPP (Android / PC)</td></tr>
        </table>

        <p>Baixe agora <b>{dados['nome']}</b> no formato {dados['formato']} testado e funcionando 100% no emulador PPSSPP.</p>
    """
    
    # SCREENSHOTS DO JOGO
    if dados['prints']:
        html_content += '<h4 style="margin-top: 20px;">📸 Screenshots do Jogo:</h4><div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">'
        for img in dados['prints']:
            html_content += f'<img src="{img}" style="width: 48%; max-width: 300px; border-radius: 6px;" />'
        html_content += '</div>'

    # BOTÃO DE DOWNLOAD REDIRECIONADO
    html_content += f"""
        <br/><br/>
        <div style="margin: 25px 0;">
            <a href="{link_redirecionado}" target="_blank" style="background-color: #28a745; color: #ffffff; padding: 15px 30px; font-size: 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                🚀 DOWNLOAD {dados['formato']} PPSSPP
            </a>
        </div>
    </div>
    """

    # ADICIONA AS CATEGORIAS / MARCADORES NO FINAL DO CORPO DO E-MAIL (PADRÃO BLOGGER)
    hashtags_categorias = " ".join([f"#{cat.replace(' ', '')}" for cat in dados['categorias']])
    corpo_final = f"{html_content}\n\n<p>{hashtags_categorias}</p>"

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = BLOGGER_EMAIL
    # TÍTULO LIMPO PARA A HOME DO SEU TEMA
    msg['Subject'] = f"{dados['nome']} ISO PPSSPP"
    msg.attach(MIMEText(corpo_final, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"🎉 POST PUBLICADO NO BLOGGER: {dados['nome']} | Formato: {dados['formato']} | Categorias: {dados['categorias']}")
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
                
                salvar_no_firebase(dados)
                
                if not ja_cadastrado:
                    enviar_post_para_blogger(dados)
                else:
                    print(f"ℹ️ Jogo '{dados['nome']}' já existe. Firebase atualizado sem post duplicado.")
            else:
                print(f"⚠️ Link de download direto não encontrado na URL: {url_alvo}")
    except Exception as e:
        print(f"❌ Erro ao processar URL {url_alvo}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url(sys.argv[1])
    else:
        if os.path.exists("jogos.txt"):
            with open("jogos.txt", "r", encoding="utf-8") as f:
                for linha in f:
                    if linha.strip():
                        processar_url(linha.strip())
