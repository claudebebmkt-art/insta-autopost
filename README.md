# insta-autopost

Posta no Instagram nos horários agendados, **de graça**, usando GitHub Actions + API oficial do Instagram.
Sem servidor, sem mensalidade, sem risco de ban (é a API oficial da Meta).

## Como funciona

- Cada post é uma pasta em `posts/` com a mídia e um `post.json`.
- A cada 15 minutos o GitHub roda `scripts/publish.py`, que publica o que já passou do horário.
- O que foi publicado fica registrado em `state/published.json` (nunca posta duas vezes).
- Dia 1 e 15 de cada mês o token é renovado sozinho.

## Configuração (uma vez só, ~20 min)

### 1. Conta do Instagram
Instagram → Configurações → Tipo de conta → **mudar para conta profissional (Empresa / Business)**.

### 2. App na Meta (grátis)
1. Entra em <https://developers.facebook.com/apps> → **Create App** → caso de uso **Manage messaging & content on Instagram**.
2. Em **Use cases → Customize → API setup with Unified login**, conecta um portfólio de negócios (obrigatório).
3. Em **App roles → Roles → Add People**, adiciona tua conta do Instagram como **Instagram Tester** e aceita o convite no Instagram (Configurações → Apps e sites → Convites do testador).
4. Volta em **2. Generate access tokens**: a conta aparece com o ID e o link **Generate token**.
   - Copia o **token** (dura 60 dias e é renovado automaticamente pelo workflow).
   - Copia o **ID da conta do Instagram** (número embaixo do @).

> Como é tua própria conta, o app pode ficar em modo desenvolvimento. Não precisa de análise da Meta.

### 3. Repositório no GitHub
1. Cria um repositório **público** e sobe esta pasta inteira.
   (Precisa ser público pra Meta conseguir baixar a mídia, e repositório público tem Actions ilimitado e grátis.
   A mídia fica visível no repo antes de ir pro ar; a senha/token não, ficam em secrets.)
2. **Settings → Secrets and variables → Actions → New repository secret**:
   | Nome | Valor |
   |---|---|
   | `IG_USER_ID` | o ID da conta do passo 2 |
   | `IG_ACCESS_TOKEN` | o token do passo 2 |
   | `GH_PAT` | um token do GitHub ([criar aqui](https://github.com/settings/personal-access-tokens/new)): só este repo, permissão **Secrets: Read and write**. É o que deixa o token do Instagram renovar sozinho. |
3. **Settings → Actions → General → Workflow permissions → Read and write**.

### 4. Testar
Aba **Actions → Publicar no Instagram → Run workflow**. Se aparecer verde, tá tudo certo.

## Criando um post

```
posts/
  2026-11-20-lancamento/
    post.json
    video.mp4
    legenda.txt
```

`post.json`:
```json
{
  "quando": "2026-11-20T18:00",
  "tipo": "reel",
  "midia": ["video.mp4"],
  "legenda_arquivo": "legenda.txt"
}
```

| Campo | O que é |
|---|---|
| `quando` | horário de Brasília (`AAAA-MM-DDTHH:MM`) |
| `tipo` | `reel`, `imagem`, `carrossel` ou `story` |
| `midia` | arquivos da pasta. Carrossel: 2 a 10 (pode misturar foto e vídeo) |
| `legenda` / `legenda_arquivo` | texto direto ou arquivo .txt |
| `capa` | (reel) imagem de capa, opcional |
| `no_feed` | (reel) `false` = só na aba Reels |
| `pausado` | `true` = não publica |

Formatos: **imagem só JPG**; vídeo MP4 (H.264 + AAC), 9:16, 1080×1920. Reel de 3 s a 15 min. Story de até 60 s.

Pode subir o post semanas antes; ele só sai no horário. Atraso normal de 5 a 20 min (fila do GitHub).

## Se der erro

- Aba **Actions** → abre o run vermelho → o log mostra a mensagem da Meta.
- O erro fica salvo em `state/published.json`. Depois de 3 tentativas ele desiste daquele post.
  Pra tentar de novo, apaga a entrada dele nesse arquivo.
- **Vídeo recusado ao baixar da URL**: liga o GitHub Pages (Settings → Pages → Deploy from branch → `main` / root)
  e cria a variável `MEDIA_BASE_URL` (Settings → Secrets and variables → Actions → **Variables**) com
  `https://SEU-USUARIO.github.io/NOME-DO-REPO/posts`.
- **Token expirado** (passou 60 dias sem renovar): gera outro no painel da Meta e troca o secret.

Limite da Meta: 50 posts por dia via API.
