/* VidFind — UI internationalization (interface only, not content).
   Shared by index.html and video.html. No build step, no dependencies.

   Usage:
     VFI18N.init(configLang);          // once, early (reads localStorage → config → 'pt')
     VFI18N.t("key", { var: value });  // translate (with {var} interpolation)
     VFI18N.applyStatic(root);         // fill [data-i18n]/[data-i18n-ph]/[data-i18n-title]
     VFI18N.setLang("en");             // switch language (persists + fires onChange)
     VFI18N.onChange(fn);              // re-render callback on language switch
     VFI18N.langs                      // [{id,label}] available languages
     VFI18N.lang                       // current language id

   To add a language: add an entry to TRANSLATIONS and to LANGS. */
(function () {
  const LANGS = [
    { id: "pt", label: "Português" },
    { id: "en", label: "English" },
  ];

  const TRANSLATIONS = {
    pt: {
      "brand.sub": "ÍNDICE DE MÍDIA",
      "app.tagline": "busca por conteúdo local",

      "nav.captions": "Legendas",
      "nav.scenes": "Cenas",
      "nav.videos": "Vídeos",

      "shortcuts.title": "ATALHOS",
      "shortcuts.search": "Buscar",
      "shortcuts.switchTab": "Trocar aba",
      "shortcuts.closePlayer": "Fechar player",

      "filter.searchSpeech": "BUSCAR FALA",
      "filter.searchScene": "BUSCAR CENA",
      "filter.searchSpeechPh": "ex: produto, slogan, marca…",
      "filter.searchScenePh": "ex: parede verde, palco…",
      "filter.folder": "FILTRAR PASTA",
      "filter.allFolders": "Todas as pastas",
      "folder.root": "(raiz)",

      "stats.captions": "legendas",
      "stats.scenes": "cenas",
      "stats.videos": "vídeos",
      "stats.title": "Dados do sistema",

      "empty.captionsIndexed": "legendas indexadas",
      "empty.scenesDescribed": "cenas descritas",
      "empty.videos": "vídeos",
      "empty.folders": "pastas",
      "empty.recent": "BUSCAS RECENTES",
      "empty.hintSpeech": "Digite para buscar nas falas",
      "empty.hintScene": "Digite para buscar nas cenas",

      "results.one": "resultado",
      "results.many": "resultados",
      "results.none": 'Nada encontrado para "{q}"',
      "tag.caption": "LEGENDA",
      "tag.scene": "CENA",

      "btn.play": "VER VÍDEO",
      "btn.video": "VÍDEO",
      "btn.copy": "COPIAR",
      "btn.copied": "COPIADO",

      "videos.one": "vídeo",
      "videos.many": "vídeos",
      "videos.segmentsOne": "segmento",
      "videos.segmentsMany": "segmentos",
      "videos.none": "Nenhum vídeo encontrado",

      "error.server": "Erro ao conectar com o servidor",
      "error.videos": "Erro ao carregar vídeos",

      "modal.jumpedTo": "saltou para",
      "modal.openFull": "Abrir página completa",

      "about.madeBy": "Feito por Dante Basso",
      "about.desc": "Indexador e buscador de vídeos self-hosted. Gera legendas (SRT), descrições de cenas a cada 10s e deixa tudo pesquisável por conteúdo — falas, cenas e arquivos — em uma única interface.",
      "about.linkSite": "Site pessoal",
      "about.linkProject": "Página do projeto",
      "about.linkSource": "Código-fonte",
      "about.linkGithub": "GitHub",
      "about.openSource": "Projeto open-source",
      "about.viewRepo": "Ver repositório",

      "system.folders": "Pastas indexadas",
      "system.videos": "Vídeos indexados",
      "system.captions": "Legendas geradas (SRT)",
      "system.scenes": "Cenas descritas (10s)",
      "system.lastIndexed": "Última indexação",
      "system.diskUsed": "Espaço indexado",
      "system.close": "FECHAR",

      "video.back": "Voltar",
      "video.theme": "Tema",
      "video.tabSubtitle": "Legenda",
      "video.tabScenes": "Cenas",
      "video.dlSrt": "SRT",
      "video.dlTxt": "TXT",
      "video.dlScenes": "Cenas",
      "video.dlVideo": "Vídeo",
      "video.loading": "Carregando…",
      "video.missingPath": "Parâmetro path ausente",
      "video.noSubtitle": "Sem legenda disponível",
      "video.errSubtitle": "Erro ao carregar legenda",
      "video.noScenes": "Sem descrições de cena disponíveis",
      "video.errScenes": "Erro ao carregar cenas",
      "video.footer": "Detalhe do Vídeo",
    },
    en: {
      "brand.sub": "MEDIA INDEX",
      "app.tagline": "local content search",

      "nav.captions": "Subtitles",
      "nav.scenes": "Scenes",
      "nav.videos": "Videos",

      "shortcuts.title": "SHORTCUTS",
      "shortcuts.search": "Search",
      "shortcuts.switchTab": "Switch tab",
      "shortcuts.closePlayer": "Close player",

      "filter.searchSpeech": "SEARCH SPEECH",
      "filter.searchScene": "SEARCH SCENE",
      "filter.searchSpeechPh": "e.g. product, slogan, brand…",
      "filter.searchScenePh": "e.g. green wall, stage…",
      "filter.folder": "FILTER FOLDER",
      "filter.allFolders": "All folders",
      "folder.root": "(root)",

      "stats.captions": "subtitles",
      "stats.scenes": "scenes",
      "stats.videos": "videos",
      "stats.title": "System data",

      "empty.captionsIndexed": "subtitles indexed",
      "empty.scenesDescribed": "scenes described",
      "empty.videos": "videos",
      "empty.folders": "folders",
      "empty.recent": "RECENT SEARCHES",
      "empty.hintSpeech": "Type to search speech",
      "empty.hintScene": "Type to search scenes",

      "results.one": "result",
      "results.many": "results",
      "results.none": 'Nothing found for "{q}"',
      "tag.caption": "SUBTITLE",
      "tag.scene": "SCENE",

      "btn.play": "PLAY",
      "btn.video": "VIDEO",
      "btn.copy": "COPY",
      "btn.copied": "COPIED",

      "videos.one": "video",
      "videos.many": "videos",
      "videos.segmentsOne": "segment",
      "videos.segmentsMany": "segments",
      "videos.none": "No videos found",

      "error.server": "Error connecting to the server",
      "error.videos": "Error loading videos",

      "modal.jumpedTo": "jumped to",
      "modal.openFull": "Open full page",

      "about.madeBy": "Made by Dante Basso",
      "about.desc": "Self-hosted video indexer and search. Generates subtitles (SRT), scene descriptions every 10s and makes everything searchable by content — speech, scenes and files — in a single interface.",
      "about.linkSite": "Personal site",
      "about.linkProject": "Project page",
      "about.linkSource": "Source code",
      "about.linkGithub": "GitHub",
      "about.openSource": "Open-source project",
      "about.viewRepo": "View repository",

      "system.folders": "Indexed folders",
      "system.videos": "Indexed videos",
      "system.captions": "Generated subtitles (SRT)",
      "system.scenes": "Described scenes (10s)",
      "system.lastIndexed": "Last indexed",
      "system.diskUsed": "Indexed space",
      "system.close": "CLOSE",

      "video.back": "Back",
      "video.theme": "Theme",
      "video.tabSubtitle": "Subtitle",
      "video.tabScenes": "Scenes",
      "video.dlSrt": "SRT",
      "video.dlTxt": "TXT",
      "video.dlScenes": "Scenes",
      "video.dlVideo": "Video",
      "video.loading": "Loading…",
      "video.missingPath": "Missing path parameter",
      "video.noSubtitle": "No subtitle available",
      "video.errSubtitle": "Error loading subtitle",
      "video.noScenes": "No scene descriptions available",
      "video.errScenes": "Error loading scenes",
      "video.footer": "Video detail",
    },
  };

  let lang = "pt";
  const listeners = [];

  function t(key, vars) {
    let s = (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]);
    if (s == null) s = TRANSLATIONS.pt[key];
    if (s == null) return key;
    if (vars) for (const k in vars) s = s.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
    return s;
  }

  function applyStatic(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.getAttribute("data-i18n")); });
    scope.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph"))); });
    scope.querySelectorAll("[data-i18n-title]").forEach((el) => { el.setAttribute("title", t(el.getAttribute("data-i18n-title"))); });
  }

  function setLang(l) {
    if (!TRANSLATIONS[l]) l = "pt";
    lang = l;
    try { localStorage.setItem("vf-lang", l); } catch (e) {}
    document.documentElement.setAttribute("lang", l);
    applyStatic();
    listeners.forEach((fn) => { try { fn(l); } catch (e) {} });
  }

  function init(configLang) {
    let saved = null;
    try { saved = localStorage.getItem("vf-lang"); } catch (e) {}
    lang = (saved && TRANSLATIONS[saved]) ? saved : (TRANSLATIONS[configLang] ? configLang : "pt");
    document.documentElement.setAttribute("lang", lang);
    return lang;
  }

  window.VFI18N = {
    t: t,
    setLang: setLang,
    init: init,
    applyStatic: applyStatic,
    onChange: (fn) => listeners.push(fn),
    langs: LANGS,
    get lang() { return lang; },
    hasSaved: () => { try { return !!localStorage.getItem("vf-lang"); } catch (e) { return false; } },
  };
  window.t = t;
})();
