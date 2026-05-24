# Frontend — Documento de Design (SDD)

> Leia junto com `CLAUDE.md`. Este arquivo descreve a arquitetura do frontend e serve como fonte de verdade para futuras modificações de UI.

---

## 1. Páginas

| Rota | Template | Função |
|------|----------|--------|
| `/` | `index.html` | Busca, cenas, listagem de vídeos (abas) |
| `/video?path=&t=` | `video.html` | Detalhe de vídeo: player + legenda + cenas |

---

## 2. Configuração injetável (`web/config.json`)

Permite que quem usa o projeto personalize a identidade visual **sem alterar código**.

```json
{
  "logo_url": "/static/logo.png",
  "title": "VidFind",
  "theme": "dark"
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `logo_url` | string ou null | URL/path da logo. `null` exibe o `title` em texto. |
| `title` | string ou null | Nome exibido no header, tab do browser e footer. |
| `theme` | `"dark"` \| `"mid"` \| `"light"` | Tema padrão (pode ser sobrescrito pelo usuário via toggle). |

O frontend carrega via `GET /api/config`. Falhas silenciosas — o sistema funciona sem o arquivo.

### Regra de prioridade de tema
1. `localStorage.getItem("theme")` (escolha do usuário)
2. `config.json > theme`
3. Fallback: `"dark"`

---

## 3. Sistema de temas

Temas são controlados pelo atributo `data-theme` na tag `<html>`. Nunca hardcode cores — use sempre variáveis CSS.

```css
[data-theme="dark"]  { --bg: #000; --surface: #0d0d0d; ... }
[data-theme="mid"]   { --bg: #141414; --surface: #1e1e1e; ... }
[data-theme="light"] { --bg: #f5f5f5; --surface: #fff; ... }
```

### Variáveis disponíveis

| Variável | Uso |
|----------|-----|
| `--bg` | Fundo da página |
| `--surface` | Fundo de cards/painéis |
| `--surface2` | Hover de cards |
| `--border` | Borda padrão |
| `--border2` | Borda destacada |
| `--accent` | Cor de destaque (texto ativo, botão primário) |
| `--accent-dim` | Versão atenuada do accent |
| `--text` | Texto principal |
| `--muted` | Texto secundário / labels |
| `--mark-bg` | Fundo de `<mark>` (highlight de busca) |
| `--mark-fg` | Texto de `<mark>` |
| `--tab-bg` | Fundo da barra de abas |
| `--tab-active-bg` | Fundo da aba ativa |

O toggle de tema cicla `dark → mid → light → dark` e salva em `localStorage`.

---

## 4. Tipografia

| Font | Uso |
|------|-----|
| `DM Sans` | Texto corrido, cards, UI geral |
| `DM Mono` | Labels, timestamps, badges, metadados |
| `Bebas Neue` | Timestamps grandes (hit cards, modal de legenda) |

- **Tamanho base**: `16px` (body)
- **Labels**: `0.62rem` uppercase + `letter-spacing`
- **Texto de resultado**: `0.92rem`

---

## 5. Componentes

### `.sidebar` — Painel lateral redimensionável

```html
<aside class="sidebar" id="<id>-sidebar">
  <!-- conteúdo -->
  <div class="resize-handle"></div>
</aside>
```

- Largura inicial: `280px`. Min: `140px`. Max: `560px`.
- Arrastada via `.resize-handle` (posicionado absolutamente na borda direita).
- Largura persistida em `localStorage` com chave `sidebar-w-<id>`.
- Em mobile (`max-width: 700px`): `.resize-handle` oculto, sidebar vira full-width horizontal.
- Inicializar com `initResize("<id>-sidebar")`.

### `.tab-btn` — Aba de navegação

Abas têm estilo clássico de "tab folder":
- **Inativa**: borda + fundo `--surface`, texto `--muted`
- **Ativa**: borda `--border2` + fundo `--tab-active-bg`, texto `--text`, `border-bottom` da cor do fundo (mescla visualmente com o conteúdo)
- Hover: fundo `--surface2`, texto `--text`

### `.hit-card` — Card de resultado de busca

Grid 2 colunas: timestamp badge | corpo (path + texto + ações).
- Hover eleva visualmente (background + border).
- `<mark>` dentro do texto recebe `--mark-bg` / `--mark-fg`.

### `.vcard` — Card de vídeo

Clicável integralmente (navega para `/video?path=...`).
- `.vcard-actions` tem `onclick="event.stopPropagation()"` para não disparar navegação ao clicar em botões.

### `.action-btn` — Botão/link de ação

Estilo minimal: borda + texto `--muted`. Hover aumenta contraste.
- `.primary`: destaque leve (borda `--border2`).
- `.copied`: borda + texto `--accent` (feedback de clipboard).

---

## 6. Página de detalhe de vídeo (`/video`)

### Parâmetros de URL
- `path` (obrigatório): caminho do vídeo codificado com `encodeURIComponent`
- `t` (opcional): timestamp em segundos para iniciar o seek

### Layout (flex coluna, 100vh)
```
header (64px)
─────────────────────────
video player (max 55vh)
video-info-bar (nome, pasta, downloads)
detail-tab-bar (Legenda | Cenas)
detail-tab-content (flex:1, overflow-y:auto)
─────────────────────────
footer (48px)
```

### Comportamento
- Clicar em linha de legenda → `player.currentTime = seg.start`
- Download de cenas → `GET /api/scenes/txt?video_path=...`
- Botão voltar: `history.back()` se `document.referrer` for a mesma origem, senão `/`

---

## 7. APIs consumidas pelo frontend

| Método | Rota | Usado em |
|--------|------|----------|
| `GET` | `/api/config` | Toda página — logo, título, tema |
| `GET` | `/api/stats` | Header — contagem de documentos |
| `GET` | `/api/folders` | Sidebar de busca e cenas |
| `GET` | `/api/search?q=&folder=&limit=` | Aba Legendas |
| `GET` | `/api/search/scenes?q=&folder=&limit=` | Aba Cenas |
| `GET` | `/api/videos` | Aba Vídeos |
| `GET` | `/api/transcript?video_path=` | Modal de legenda (index), aba Legenda (video.html) |
| `GET` | `/api/scenes?video_path=` | Aba Cenas (video.html) |
| `GET` | `/api/subtitle?video_path=` | Download SRT |
| `GET` | `/api/transcript/txt?video_path=` | Download TXT |
| `GET` | `/api/scenes/txt?video_path=` | Download descrição de cenas |
| `GET` | `/api/video?path=&download=1` | Download de vídeo |
| `GET` | `/api/video?path=` | Streaming para `<video>` |

---

## 8. State management (index.html)

Todo estado vive em variáveis module-level no `<script>`:

| Variável | Tipo | Descrição |
|----------|------|-----------|
| `activeFolder` | string | Pasta ativa na aba Legendas |
| `scenesActiveFolder` | string | Pasta ativa na aba Cenas |
| `videosActiveFolder` | string | Pasta ativa na aba Vídeos |
| `allVideos` | array | Cache de todos os vídeos (filtro client-side) |
| `videosLoaded` | bool | Lazy load da aba Vídeos |
| `scenesFoldersLoaded` | bool | Lazy load das pastas de Cenas |

---

## 9. Regras de extensão

- **Novo tema**: adicionar `[data-theme="nome"] { --bg: ...; ... }` com todas as variáveis + incluir na array `THEMES` do JS.
- **Novo campo no config.json**: ler em `fetch("/api/config").then(...)` e aplicar. Manter retrocompatibilidade (campos opcionais).
- **Nova aba em index.html**: adicionar `.tab-btn` no nav, novo panel `#panel-<nome>` no `.content-wrap`, e handler no listener do `.tab-bar`.
- **Novo botão de ação**: usar classe `.action-btn`. Adicionar `data-action="..."` e tratar no listener de delegação do painel pai.
- **Novos campos de vídeo no detalhe**: adicionar na response de `/api/videos` e renderizar em `renderFilteredVideos()`.
