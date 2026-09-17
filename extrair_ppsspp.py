import sys
import os
import re
import time
import random
import requests

FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
BLOG_PPSSPP_URL = "https://k-404ppsspp.blogspot.com"

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, Gecko) Version/17.2 Safari/605.1.15"
]

def obter_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

def extrair_id_jogo(url_origem):
    url_limpa = url_origem.split('?')[0].split('#')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file'] and not p.isdigit()]
    id_jogo = partes[-1] if partes else "jogo"
    id_jogo = re.sub(r'(\.html|\.iso|-psp-ptbr|-ppsspp|-psp)$', '', id_jogo, flags=re.IGNORECASE)
    id_jogo = re.sub(r'[^a-zA-Z0-9_-]', '', id_jogo)
    return id_jogo if id_jogo else "jogo_ppsspp"

def buscar_link_download(html, url_alvo):
    if "isoptbr.com" in url_alvo:
        match = re.search(r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz)[^"\']+)["\']', html, re.IGNORECASE)
        return match.group(1) if match else None
        
    elif "movgamezone.com" in url_alvo:
        match = re.search(r'href=["\'](https?://(?:www\.)?(?:modsfire\.com|sharemods\.com|mediafire\.com|drive\.google\.com)[^"\']+)["\']', html, re.IGNORECASE)
        return match.group(1) if match else None

    # Captura genérica para Mediafire/Drive/Mega
    match = re.search(r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz)[^"\']+)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None

def salvar_no_firebase_ppsspp(url_origem, link_direto, nome_jogo):
    id_jogo = extrair_id_jogo(url_origem)
    
    payload = {
        "url_original": url_origem,
        "link_direto": link_direto,
        "nome": nome_jogo,
        "tipo": "PPSSPP ISO",
        "blog": BLOG_PPSSPP_URL
    }

    try:
        endpoint = f"{FIREBASE_BASE_URL.rstrip('/')}/ppsspp/{id_jogo}.json"
        res = requests.patch(endpoint, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ SALVO NO FIREBASE (/ppsspp/{id_jogo}):")
            print(f"   └─ Link Direto: {link_direto}")
            return id_jogo
        else:
            print(f"❌ Erro Firebase ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Erro Conexão Firebase: {e}")
    return None

def processar_url_ppsspp(url_alvo):
    print(f"\n🔍 Processando: {url_alvo}")
    id_jogo = extrair_id_jogo(url_alvo)
    nome_jogo = id_jogo.replace('-', ' ').replace('_', ' ').title()

    # Pausa de 3 a 6 segundos para evitar o erro HTTP 429 (bloqueio por requisicoes frequentes)
    time.sleep(random.uniform(3, 6))

    try:
        res = requests.get(url_alvo, headers=obter_headers(), timeout=15)
        if res.status_code == 200:
            link_direto = buscar_link_download(res.text, url_alvo)
            if link_direto:
                salvar_no_firebase_ppsspp(url_alvo, link_direto, nome_jogo)
            else:
                print(f"⚠️ Link de download não localizado na página.")
        elif res.status_code == 429:
            print("⚠️ Acesso limitado temporariamente pelo site de origem (Erro 429). Aguarde o próximo ciclo.")
        else:
            print(f"⚠️ Falha de acesso HTTP: {res.status_code}")
    except Exception as e:
        print(f"❌ Erro durante a requisição: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url_ppsspp(sys.argv[1])
    else:
        arquivo_jogos = "jogos.txt"
        if os.path.exists(arquivo_jogos):
            with open(arquivo_jogos, "r", encoding="utf-8") as f:
                lista_urls = [linha.strip() for linha in f if linha.strip()]
            
            for url in lista_urls:
                processar_url_ppsspp(url)
