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
  "logo_url": "/assets/logo.png",
  "title": "VidFind",
  "theme": "nocturne",
  "lang": "pt",
  "resolutions": ["4k", "1080p", "720p"]
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `logo_url` | string ou null | URL/path da logo. `null` exibe o `title` em texto (marca waveform + nome). |
| `title` | string ou null | Nome exibido no header, tab do browser e footer. |
| `theme` | `"nocturne"` \| `"ocean"` \| `"palenight"` \| `"onedark"` | Tema padrão (pode ser sobrescrito pelo usuário via seletor). |
| `lang` | `"pt"` \| `"en"` | Idioma padrão da **interface** (pode ser sobrescrito pelo usuário via seletor). |
| `resolutions` | string[] | Tokens de resolução para o menu de download, em ordem de exibição. Ver §4.3. |

O frontend carrega via `GET /api/config`. Falhas silenciosas — o sistema funciona sem o arquivo.

### Regra de prioridade de tema
1. `localStorage.getItem("vf-theme")` (escolha do usuário)
2. `config.json > theme`
3. Fallback: `"nocturne"`

---

## 3. Sistema de temas

Temas são controlados pelo atributo `data-theme` na tag `<html>`. Nunca hardcode cores — use sempre variáveis CSS.

Cada tema define **apenas 5 roles**; todas as rampas de cor (100–900), o divider e as
sombras **derivam por fórmula** (`color-mix`) desses 5 valores. Assim um tema novo só
precisa dessas 5 linhas.

```css
:root, [data-theme="nocturne"] {  /* padrão */
  --color-bg: #161826; --color-surface: #232532; --color-text: #e9e9ed;
  --color-accent: #9184d9; --color-accent-2: #a7a1db;
}
[data-theme="ocean"]     { --color-bg: #0b0f17; --color-surface: #121826; --color-text: #d4dced; --color-accent: #4fd8c4; --color-accent-2: #5ec2e0; }
[data-theme="palenight"] { --color-bg: #1b1e2b; --color-surface: #242840; --color-text: #eae9f5; --color-accent: #c895ea; --color-accent-2: #f07bb0; }
[data-theme="onedark"]   { --color-bg: #21252b; --color-surface: #282c34; --color-text: #c7ccd6; --color-accent: #61afef; --color-accent-2: #e5c07b; }
```

### Roles (definidos por tema) + rampas derivadas

| Variável | Uso |
|----------|-----|
| `--color-bg` | Fundo da página |
| `--color-surface` | Fundo de cards/painéis |
| `--color-text` | Texto principal |
| `--color-accent` / `--color-accent-2` | Destaque (linhas, texto ativo, botão primário, `<mark>`) |
| `--color-accent-100..900` | Rampa do accent (derivada) |
| `--color-neutral-100..900` | Rampa neutra derivada de text↔bg (labels, bordas, muted) |
| `--color-divider` | Divisórias (`text 16%` transparente) |
| `--shadow-sm/md/lg` | Sombras (contorno + drop shadow) |

`<mark>` de busca usa `--color-accent-800` (fundo) + `--color-accent-100` (texto).

O seletor de tema (popover **TEMA** no topo) troca entre os 4 temas, aplica em
`data-theme` e persiste em `localStorage["vf-theme"]`. A página `/video` compartilha
a mesma chave (tema segue de uma página pra outra).

> **`video.html`** usa uma camada de *aliases* (`--bg`, `--surface`, `--border`,
> `--accent`, etc. → tokens `--color-*`) para reaproveitar seu CSS existente. Em
> código novo, prefira os tokens `--color-*` diretamente.

---

## 4. Tipografia

Fonte única: **Inter** (Google Fonts), exposta como `--font-heading` e `--font-body`.

| Peso | Uso |
|------|-----|
| `500` (às vezes 600) | Títulos, labels, botões, contadores, timestamps |
| `400` | Texto corrido, cards, UI geral |

- **Tamanho base**: `15px` (body)
- **Labels**: `11px` uppercase + `letter-spacing: .06em`
- **Texto de resultado**: `14px`

## 4.1 Ícones

Ícones são **SVG inline self-hosted** (sem CDN — o app roda offline/LAN). No
`index.html` há um mapa `ICONS` (markup de cada ícone) e um helper `icon(name, cls)`
que devolve o `<svg viewBox="0 0 24 24">`. Para adicionar um ícone, inclua a entrada
em `ICONS` e use `icon("nome")`. `video.html` usa glyphs unicode simples.

## 4.2 Internacionalização (i18n) — só a interface

A i18n cobre **apenas os textos da interface**, não o conteúdo indexado (falas/cenas
seguem no idioma do acervo). Módulo compartilhado: [`web/static/i18n.js`](web/static/i18n.js),
carregado por `index.html` e `video.html` via `<script src="/static/i18n.js">`. Sem
build, sem dependência.

API (`window.VFI18N` + global `t`):

| Chamada | Uso |
|---------|-----|
| `VFI18N.init(configLang?)` | Uma vez, cedo. Define o idioma: `localStorage["vf-lang"]` → `config.lang` → `"pt"` |
| `t("chave", { var })` | Traduz, com interpolação `{var}` |
| `VFI18N.applyStatic(root?)` | Preenche `[data-i18n]` (textContent), `[data-i18n-ph]` (placeholder), `[data-i18n-title]` (title) |
| `VFI18N.setLang("en")` | Troca idioma: persiste, seta `<html lang>`, aplica estáticos e dispara `onChange` |
| `VFI18N.onChange(fn)` | Callback de re-render ao trocar idioma |
| `VFI18N.langs` / `VFI18N.lang` | Idiomas disponíveis `[{id,label}]` / idioma atual |

**Dois tipos de string:**
- **Estáticas no HTML** → marcadas com `data-i18n="chave"` (ou `-ph`/`-title`); traduzidas por `applyStatic()`.
- **Geradas por JS** (render de resultados, cards, diálogos) → usam `t("chave")` direto; a
  troca de idioma re-renderiza (via `refreshI18n()` em index.html / `onChange` em video.html).

**Nunca** ponha `data-i18n` em elemento cujo texto é dado dinâmico (ex.: `#detail-name`
recebe o nome do vídeo) — o `applyStatic()` sobrescreveria o dado.

Seletor de idioma: botão + popover ao lado do seletor de tema (index.html); botão que
cicla PT/EN no header (video.html). Formatação de número/data segue o idioma
(`pt-BR`/`en-US`).

### Regra de prioridade de idioma
1. `localStorage.getItem("vf-lang")` (escolha do usuário)
2. `config.json > lang`
3. Fallback: `"pt"`

---

## 4.3 Download por resolução

O botão **VÍDEO** (resultados de busca e cards de vídeo) baixa o arquivo. Quando o
acervo tem o mesmo vídeo em várias resoluções, o botão vira um **menu** para o
usuário escolher qual baixar (label + tamanho do arquivo).

**Convenção de acervo (pasta + sufixo espelhados):** a resolução aparece **tanto**
no primeiro segmento de pasta sob `VIDEOS_PATH` **quanto** como sufixo `_<token>` no
nome do arquivo. Só o `1080p` é indexado; as demais são derivadas dele:

```
1080p/STUDIO HEXATA/SINDUSCON/C0214_169_1080p.mp4   ← indexado
   4k/STUDIO HEXATA/SINDUSCON/C0214_169_4k.mp4      ← derivado (troca pasta + sufixo)
 720p/STUDIO HEXATA/SINDUSCON/C0214_169_720p.mp4
```

**Fluxo:**
1. O front (só conhece o path do `1080p`) chama `GET /api/resolutions?video_path=`.
2. O backend deriva os candidatos para cada token de `config.json > resolutions`,
   **checa `os.path.exists`** e retorna só os que existem em disco
   (`{ token, label, path, size }`), na ordem do config.
3. **0 ou 1 variante** → baixa direto o original (botão simples, sem menu).
   **2+** → abre o menu `.dl-menu` (label do backend + `fmtBytes(size)`); cada item
   dispara `GET /api/video?path=<variante>&download=1`. Fecha por clique-fora ou `Esc`.

Config-driven e existence-checked: enquanto o acervo tiver só uma resolução, o botão
não muda; ao adicionar os arquivos espelhados (4K/720p), o menu surge sozinho — sem
tocar no código. Tokens não-reconhecidos no 1º segmento de pasta ou paths fora de
`VIDEOS_PATH` retornam lista vazia (fallback seguro para download único).

---

## 5. Estrutura e componentes (`index.html`)

Layout flex-coluna 100vh: **nav (topo)** / **body (sidebar + main)** / **footer**.

### `.nav` — Barra superior
Marca (waveform + título) à esquerda. À direita: `.stats-btn` (contadores
legendas/cenas/vídeos, clicável → diálogo **Dados do sistema**) e o `.theme-wrap`
(botão + `.theme-pop`, popover de 4 temas com swatches).

### `.sidebar` — Navegação vertical redimensionável
Substitui as antigas abas horizontais. Contém `.nav-item` (Legendas/Cenas/Vídeos,
ícone + label + contador), divisória e o bloco **ATALHOS**.
- Largura inicial `216px`, min `160px`, max `420px`; arrastada via `.resize-handle`,
  persistida em `localStorage["sidebar-w"]`. Inicializada por `initResize()` (IIFE).
- Em mobile (`max-width: 700px`): handle oculto, sidebar full-width horizontal.
- `.nav-item.active`: fundo `--color-accent-800`, texto `--color-accent-100`.

### `.filter-bar` — Barra de filtros (topo do `main`)
Campo de busca (`.field.grow`, **oculto na aba Vídeos**) + `<select>` de pasta
(`.field.folder`, `#folder-select`, reconstruído por aba em `buildFolderSelect()`).

### Estado vazio (`.empty`) — Legendas/Cenas sem query
4 `.stat-card` (legendas, cenas, vídeos, pastas) + `.chips` de **buscas recentes**
(`localStorage["vf-recent"]`, dedupe, até 8; clique preenche a busca) + hint.

### `.card.rcard` — Resultado de busca
Linha: coluna de timestamp + tag (LEGENDA/CENA) | corpo (path/câmera + texto com
`<mark>` + ações). Botões variam: Legenda → VER VÍDEO/SRT/TXT/VÍDEO/COPIAR;
Cena → VER VÍDEO/VÍDEO/COPIAR (sem SRT/TXT).

### `.card.vcard` — Card de vídeo
Clicável (navega para `/video?path=...`). `.vcard-actions` tem
`onclick="event.stopPropagation()"`. Botões: VER VÍDEO/SRT/TXT/VÍDEO.

### `.btn` — Botão/link de ação
Variantes: `.btn-primary` (accent), `.btn-secondary` (borda neutra),
`.btn-ghost` (sem borda), `.btn-icon`, `.copied` (feedback de clipboard).

### Diálogos e modal
`.dialog-backdrop` + `.dialog` para **Sobre** (`#about-dialog`, estático) e
**Dados do sistema** (`#system-dialog`, populado por `/api/system` com fallback).
`.dialog-backdrop.vm` (`#video-modal`) é o **modal de player**: abre pelo botão
VER VÍDEO, faz `currentTime = start` no `loadedmetadata`, mostra "saltou para
HH:MM:SS" e link "abrir página completa" → `/video`. Fecha por X, clique fora e `Esc`.

### Atalhos de teclado
`/` foca a busca; `1·2·3` trocam de aba; `Esc` fecha modal/diálogo/popover.
Ignorados quando o foco está num campo (exceto `Esc`).

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
| `GET` | `/api/stats` | Header — contagem de legendas/cenas |
| `GET` | `/api/system` | Diálogo "Dados do sistema" (pastas, vídeos, legendas, cenas, última indexação, espaço) |
| `GET` | `/api/folders` | `<select>` de pasta (Legendas/Cenas) |
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
| `GET` | `/api/resolutions?video_path=` | Variantes de resolução em disco (menu de download) |

---

## 8. State management (index.html)

Todo estado vive em variáveis module-level no `<script>`:

| Variável | Tipo | Descrição |
|----------|------|-----------|
| `activeTab` | string | Aba ativa (`legendas`/`cenas`/`videos`) |
| `folderByTab` | object | Pasta ativa por aba `{ legendas, cenas, videos }` |
| `foldersCaptions` | array | Pastas de `/api/folders` (Legendas/Cenas) |
| `allVideos` | array | Cache de todos os vídeos (filtro client-side) |
| `videosLoaded` | bool | Lazy load da aba Vídeos |
| `statsData` | object | `{ captions, scenes, videos, folders }` (contadores) |
| `lastResults` / `lastVideos` | array | Últimos itens renderizados (referenciados por `data-idx` no play/copy) |

---

## 9. Regras de extensão

- **Novo tema**: adicionar `[data-theme="nome"] { --color-bg/surface/text/accent/accent-2 }`
  (só 5 roles — as rampas caem por fórmula) + incluir em `THEME_DEFS`/`THEMES` do JS
  (em `index.html` e `video.html`).
- **Novo idioma**: adicionar uma entrada em `TRANSLATIONS` e em `LANGS` no
  `web/static/i18n.js` (traduzindo todas as chaves existentes). Nada mais a mudar.
- **Nova string de UI**: adicionar a chave em `TRANSLATIONS` (pt **e** en) e usar
  `t("chave")` (JS) ou `data-i18n="chave"` (HTML estático).
- **Novo ícone**: adicionar entrada em `ICONS` e usar `icon("nome")`.
- **Novo campo no config.json**: ler em `fetch("/api/config").then(...)` e aplicar. Manter retrocompatibilidade (campos opcionais).
- **Nova aba em index.html**: adicionar `.nav-item[data-tab]` na sidebar, tratar em `setTab()`/`render()`, e um `TAB_DEFS`.
- **Novo botão de ação**: usar classe `.btn`. Adicionar `data-action="..."` e tratar no listener de delegação de `#content`.
- **Novos campos de vídeo no detalhe**: adicionar na response de `/api/videos` e renderizar em `renderVideos()`.
