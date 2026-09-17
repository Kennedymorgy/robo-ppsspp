import sys
import os
import re
import requests

# CONFIGURAÇÃO DO SEU BANCO E BLOG PPSSPP
FIREBASE_BASE_URL = "https://meublog-apks-default-rtdb.firebaseio.com"
BLOG_PPSSPP_URL = "https://k-404ppsspp.blogspot.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}

def extrair_id_jogo(url_origem):
    """Gera o ID do jogo limpo a partir da URL."""
    url_limpa = url_origem.split(']')[0].rstrip('/')
    partes = [p for p in url_limpa.split('/') if p and p not in ['download', 'file'] and not p.isdigit()]
    id_jogo = partes[-1] if partes else "jogo"
    id_jogo = id_jogo.replace('.html', '').replace('.iso', '').replace('-psp-ptbr', '').replace('-ppsspp', '')
    return id_jogo

def buscar_link_isoptbr(html):
    """Procura links diretos/servidores no ISOPTBR."""
    padrao = r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz)[^"\']+)["\']'
    match = re.search(padrao, html, re.IGNORECASE)
    return match.group(1) if match else None

def buscar_link_movgamezone(html):
    """Procura links de download no Movgamezone (Modsfire, Sharemods, Mediafire, etc)."""
    padrao = r'href=["\'](https?://(?:www\.)?(?:modsfire\.com|sharemods\.com|mediafire\.com|drive\.google\.com)[^"\']+)["\']'
    match = re.search(padrao, html, re.IGNORECASE)
    return match.group(1) if match else None

def buscar_link_romsfun(url):
    """Pega os links do Romsfun requisitando a página de download."""
    try:
        if "/download/" not in url:
            url_dl = url.rstrip('/') + "/download"
        else:
            url_dl = url

        res = requests.get(url_dl, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            padrao = r'href=["\'](https?://[^"\']+\.(?:iso|cso|7z|zip)[^"\']*)["\']'
            match = re.search(padrao, res.text, re.IGNORECASE)
            if match:
                return match.group(1)
            
            padrao_alt = r'href=["\'](https?://(?:dl|files|cdn)\.[^"\']+)["\']'
            match_alt = re.search(padrao_alt, res.text, re.IGNORECASE)
            if match_alt:
                return match_alt.group(1)
    except Exception as e:
        print(f"❌ Erro Romsfun: {e}")
    return None

def extrair_titulo_jogo(html, id_fallback):
    """Extrai o título limpo da página."""
    match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if match:
        titulo = match.group(1)
        titulo_limpo = re.sub(r'(?i)\s*(?:ISO|PSP|PTBR|PPSSPP|Download|ROM|Gamer|Gratis|-|–|\|).*$', '', titulo).strip()
        if titulo_limpo and len(titulo_limpo) > 2:
            return titulo_limpo
    return id_fallback.replace('-', ' ').title()

def salvar_no_firebase_ppsspp(url_origem, link_direto, nome_jogo):
    """Salva diretamente no banco Firebase no nó /ppsspp/."""
    id_jogo = extrair_id_jogo(url_origem)
    
    payload = {
        "url_original": url_origem,
        "link_direto": link_direto,
        "nome": nome_jogo,
        "tipo": "PPSSPP ISO",
        "blog": BLOG_PPSSPP_URL
    }

    try:
        endpoint = f"{FIREBASE_BASE_URL}/ppsspp/{id_jogo}.json"
        res = requests.patch(endpoint, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ SALVO NO FIREBASE (/ppsspp/{id_jogo}):")
            print(f"   └─ Jogo: {nome_jogo}")
            print(f"   └─ Link: {link_direto}")
            return id_jogo
        else:
            print(f"❌ Erro ao salvar no Firebase: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Falha de conexão com Firebase: {e}")
    return None

def processar_url_ppsspp(url_alvo):
    print(f"\n==================================================")
    print(f"🔍 Processando URL PPSSPP: {url_alvo}")
    
    id_fallback = extrair_id_jogo(url_alvo)
    link_direto = None
    nome_jogo = id_fallback.replace('-', ' ').title()

    try:
        res = requests.get(url_alvo, headers=HEADERS, timeout=15)
        html = res.text
        nome_jogo = extrair_titulo_jogo(html, id_fallback)

        if "isoptbr.com" in url_alvo:
            link_direto = buscar_link_isoptbr(html)
        elif "movgamezone.com" in url_alvo:
            link_direto = buscar_link_movgamezone(html)
        elif "romsfun.com" in url_alvo:
            link_direto = buscar_link_romsfun(url_alvo)
        else:
            # Fallback genérico para links Mediafire/Drive/Mega
            match = re.search(r'href=["\'](https?://(?:www\.)?(?:mediafire\.com|drive\.google\.com|mega\.nz)[^"\']+)["\']', html, re.IGNORECASE)
            if match:
                link_direto = match.group(1)

    except Exception as e:
        print(f"❌ Erro ao acessar a URL: {e}")

    if link_direto:
        salvar_no_firebase_ppsspp(url_alvo, link_direto, nome_jogo)
        salvar_url_na_lista(url_alvo)
    else:
        print(f"⚠️ Não foi possível encontrar link direto para: {url_alvo}")

def salvar_url_na_lista(url):
    arquivo = "jogos.txt"
    urls_existentes = set()
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            urls_existentes = set(line.strip() for line in f if line.strip())

    if url not in urls_existentes:
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
        print(f"📝 URL salva em {arquivo} para próximos ciclos.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        processar_url_ppsspp(sys.argv[1])
    else:
        arquivo_jogos = "jogos.txt"
        if os.path.exists(arquivo_jogos):
            with open(arquivo_jogos, "r", encoding="utf-8") as f:
                lista_urls = [linha.strip() for linha in f if linha.strip()]
            
            print(f"🤖 Rodando ciclo PPSSPP solo. {len(lista_urls)} jogo(s) na lista...")
            for url in lista_urls:
                processar_url_ppsspp(url)
        else:
            print("⚠️ Crie o arquivo 'jogos.txt' com os links de jogos de PPSSPP.")
