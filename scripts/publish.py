#!/usr/bin/env python3
"""
Publica no Instagram os posts agendados na pasta posts/.

Cada post é uma pasta com um post.json:
{
  "quando": "2026-11-20T18:00",          # horário local (fuso em TZ, padrão America/Sao_Paulo)
  "tipo": "reel" | "imagem" | "carrossel" | "story",
  "midia": ["video.mp4"],                 # arquivos dentro da pasta do post (carrossel: 2 a 10)
  "legenda": "texto do post #hashtag",    # ou "legenda_arquivo": "legenda.txt"
  "capa": "capa.jpg",                     # opcional, só reel
  "no_feed": true                         # opcional, só reel (padrão true)
}

Só usa a biblioteca padrão do Python. Variáveis de ambiente:
  IG_USER_ID, IG_ACCESS_TOKEN  (obrigatórias)
  MEDIA_BASE_URL  URL pública onde a pasta posts/ fica acessível
                  (padrão: raw.githubusercontent.com do próprio repositório)
  TZ_POSTS        fuso dos horários (padrão America/Sao_Paulo)
  GRAPH_VERSION   versão da API (padrão v25.0)
  DRY_RUN=1       só mostra o que faria, sem chamar a API
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
STATE_FILE = ROOT / "state" / "published.json"

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v25.0")
# O host certo depende do tipo de token; detectamos sozinhos no início.
HOSTS = ["graph.instagram.com", "graph.facebook.com"]
API = f"https://{HOSTS[0]}/{GRAPH_VERSION}"
TZ = ZoneInfo(os.environ.get("TZ_POSTS", "America/Sao_Paulo"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MAX_TENTATIVAS = 3


def log(msg):
    print(msg, flush=True)


def media_base_url():
    base = os.environ.get("MEDIA_BASE_URL")
    if base:
        return base.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        sys.exit("Defina MEDIA_BASE_URL (ou rode dentro do GitHub Actions).")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/posts"


def api(method, path, params=None):
    token = os.environ["IG_ACCESS_TOKEN"]
    params = dict(params or {})
    url = f"{API}/{path}"
    if method == "GET":
        params["access_token"] = token
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
    else:
        body = urllib.parse.urlencode({**params, "access_token": token}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode(errors='replace')}")


def esperar_container(cid, limite_s=900):
    """Vídeo precisa ser processado pela Meta antes de publicar."""
    inicio = time.time()
    while True:
        st = api("GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {cid} falhou: {st}")
        if time.time() - inicio > limite_s:
            raise RuntimeError(f"Container {cid} demorou demais: {st}")
        time.sleep(15)


def criar_container(ig, params):
    if DRY_RUN:
        log(f"   [dry-run] POST {ig}/media {params}")
        return "DRY"
    return api("POST", f"{ig}/media", params)["id"]


def eh_video(nome):
    return nome.lower().endswith((".mp4", ".mov"))


def publicar(post, pasta, base):
    ig = os.environ["IG_USER_ID"]
    url = lambda f: f"{base}/{urllib.parse.quote(pasta.name)}/{urllib.parse.quote(f)}"
    tipo = post["tipo"]
    midia = post["midia"]
    legenda = post.get("legenda", "")
    if post.get("legenda_arquivo"):
        legenda = (pasta / post["legenda_arquivo"]).read_text(encoding="utf-8").strip()

    for f in midia + ([post["capa"]] if post.get("capa") else []):
        if not (pasta / f).exists():
            raise RuntimeError(f"Arquivo não encontrado: {pasta.name}/{f}")

    if tipo == "reel":
        p = {"media_type": "REELS", "video_url": url(midia[0]), "caption": legenda,
             "share_to_feed": str(post.get("no_feed", True)).lower()}
        if post.get("capa"):
            p["cover_url"] = url(post["capa"])
        cid = criar_container(ig, p)
    elif tipo == "imagem":
        cid = criar_container(ig, {"image_url": url(midia[0]), "caption": legenda})
    elif tipo == "story":
        chave = "video_url" if eh_video(midia[0]) else "image_url"
        cid = criar_container(ig, {"media_type": "STORIES", chave: url(midia[0])})
    elif tipo == "carrossel":
        if not 2 <= len(midia) <= 10:
            raise RuntimeError("Carrossel precisa de 2 a 10 arquivos.")
        filhos = []
        for f in midia:
            p = ({"media_type": "VIDEO", "video_url": url(f)} if eh_video(f)
                 else {"image_url": url(f)})
            p["is_carousel_item"] = "true"
            c = criar_container(ig, p)
            if not DRY_RUN:
                esperar_container(c)
            filhos.append(c)
        cid = criar_container(ig, {"media_type": "CAROUSEL", "children": ",".join(filhos),
                                   "caption": legenda})
    else:
        raise RuntimeError(f"Tipo desconhecido: {tipo}")

    if DRY_RUN:
        log(f"   [dry-run] POST {ig}/media_publish creation_id={cid}")
        return "DRY_RUN"
    esperar_container(cid)
    return api("POST", f"{ig}/media_publish", {"creation_id": cid})["id"]


def conectar():
    """Testa o token nos dois hosts da Meta e usa o que funcionar."""
    global API
    ig = os.environ["IG_USER_ID"]
    erros = []
    for host in HOSTS:
        API = f"https://{host}/{GRAPH_VERSION}"
        try:
            me = api("GET", ig, {"fields": "username"})
            log(f"Conectado como @{me.get('username')} via {host}")
            return
        except RuntimeError as e:
            erros.append(str(e))
    sys.exit("Não consegui conectar com o token:\n" + "\n".join(erros))


def main():
    if not DRY_RUN:
        conectar()
    state =json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    agora = datetime.now(timezone.utc)
    base = media_base_url()
    mudou = False

    pastas = sorted(p for p in POSTS_DIR.iterdir() if (p / "post.json").exists())
    for pasta in pastas:
        reg = state.get(pasta.name, {})
        if reg.get("status") == "publicado" or reg.get("tentativas", 0) >= MAX_TENTATIVAS:
            continue
        post = json.loads((pasta / "post.json").read_text(encoding="utf-8"))
        if post.get("pausado"):
            continue
        quando = datetime.fromisoformat(post["quando"])
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=TZ)
        if quando > agora:
            continue

        log(f"-> {pasta.name} ({post['tipo']}, agendado {post['quando']})")
        try:
            media_id = publicar(post, pasta, base)
            if DRY_RUN:
                continue
            state[pasta.name] = {"status": "publicado", "media_id": media_id,
                                 "em": agora.isoformat()}
            log(f"   publicado! media_id={media_id}")
        except Exception as e:  # noqa: BLE001
            if DRY_RUN:
                log(f"   erro: {e}")
                continue
            t = reg.get("tentativas", 0) + 1
            state[pasta.name] = {"status": "erro", "tentativas": t, "erro": str(e)[:1000]}
            log(f"   ERRO (tentativa {t}/{MAX_TENTATIVAS}): {e}")
        mudou = True

    if mudou:
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    if any(v.get("status") == "erro" for v in state.values()):
        sys.exit(1)  # deixa o run vermelho no GitHub pra você ver


if __name__ == "__main__":
    main()
