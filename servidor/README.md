# Deploy no Servidor (J1800 + OMV)

Guia completo para colocar o `videos.site.com.br` acessível publicamente via Nginx rodando no mesmo hardware do OpenMediaVault.

---

## Visão geral do que será feito

```
Internet
  │
  ├─ site.com.br          → Dreamhost (não mexer)
  ├─ omv.site.com.br      → J1800 → Nginx → OMV na porta 8888
  └─ videos.site.com.br   → J1800 → Nginx → Ad-Search na porta 8080
```

---

## 1. DNS — criar os CNAMEs no Dreamhost

No painel do Dreamhost, adicionar dois registros do tipo **A** (não CNAME, pois é o apex de subdomínio):

| Nome               | Tipo | Valor                  |
|--------------------|------|------------------------|
| `omv.site.com.br`    | A    | `<IP público do J1800>` |
| `videos.site.com.br` | A    | `<IP público do J1800>` |

> Para saber o IP público atual do J1800: `curl ifconfig.me` no terminal do servidor.

Propagação leva de alguns minutos a até 24h.

---

## 2. Mover o OMV para a porta 8888

O Nginx precisa ocupar a porta 80. O OMV deve ser movido para outra porta.

**No painel do OMV:**
1. Acesse `Sistema → Configurações de Trabalho` (ou *General Settings*)
2. Campo **Port** — troque de `80` para `8888`
3. Salve e confirme o reinício do serviço web

Após isso, o OMV só responde em `http://<IP-local>:8888`. Acesse para confirmar.

---

## 3. Instalar o Nginx no J1800

O OMV roda Debian internamente, então:

```bash
sudo apt update
sudo apt install -y nginx
sudo systemctl enable nginx
```

---

## 4. Copiar e ativar a configuração

```bash
# Desativar o site default do Nginx
sudo rm -f /etc/nginx/sites-enabled/default

# Copiar a configuração deste repositório
sudo cp nginx/nginx.conf /etc/nginx/nginx.conf

# Testar a sintaxe antes de recarregar
sudo nginx -t

# Recarregar sem derrubar conexões
sudo systemctl reload nginx
```

---

## 5. Empacotar e transferir o Ad-Search

### No computador de desenvolvimento

O script `servidor/pack.sh` exporta o código-fonte **e** os dois volumes Docker (legendas + índice de busca) em um único zip datado:

```bash
# Na raiz do projeto
bash servidor/pack.sh
# Gera: /home/dcbasso/worksapce/Hexata/ad-search-YYYYMMDD_HHMM.zip
```

O que é incluído no zip:

```
ad-search/
├── project/          ← código-fonte (sem .env e __pycache__)
└── volumes/
    ├── srt_data.tar.gz    ← legendas .srt geradas
    └── meili_data.tar.gz  ← índice de busca do Meilisearch
```

Transferir para o servidor:

```bash
scp /home/dcbasso/worksapce/Hexata/ad-search-*.zip <usuario>@<IP do J1800>:~/
```

### No servidor J1800

```bash
# Extrair o bundle
unzip ad-search-*.zip
cd ad-search/project

# Criar o .env com os valores do servidor
cat > .env <<'EOF'
VIDEOS_PATH=/srv/dev-disk-by-uuid-XXXX/Hexata/1080p
MEILI_MASTER_KEY=sua-chave-secreta-aqui
EOF

# Criar os volumes Docker antes de restaurar
docker volume create ad-search_srt_data
docker volume create ad-search_meili_data

# Restaurar volume de legendas
docker run --rm \
  -v ad-search_srt_data:/srt \
  -v ~/ad-search/volumes:/backup \
  alpine \
  tar xzf /backup/srt_data.tar.gz -C /srt

# Restaurar índice de busca
docker run --rm \
  -v ad-search_meili_data:/meili_data \
  -v ~/ad-search/volumes:/backup \
  alpine \
  tar xzf /backup/meili_data.tar.gz -C /meili_data

# Subir os serviços (índice já restaurado — não precisa reindexar)
docker compose up -d meilisearch whisper-worker web
```

> **VIDEOS_PATH**: ajuste para o caminho real onde os vídeos estão montados no OMV.
> Use `df -h` ou `ls /srv/` para localizar o disco correto.
>
> Se preferir reindexar do zero no servidor (mais lento, mas dispensa carregar o volume meili):
> ```bash
> docker compose up indexer
> ```

---

## 6. (Recomendado) Habilitar HTTPS com Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx

# Gerar certificados para ambos os subdomínios
sudo certbot --nginx \
  -d omv.site.com.br \
  -d videos.site.com.br \
  --email dcbasso@gmail.com \
  --agree-tos \
  --non-interactive

# O Certbot edita o nginx.conf automaticamente com os blocos SSL
# Renovação automática já vem configurada via systemd timer:
sudo systemctl status certbot.timer
```

Após o certbot rodar, o `nginx.conf` terá blocos `listen 443 ssl` e redirecionamento automático de HTTP para HTTPS.

---

## 7. Verificação final

```bash
# Nginx está rodando?
sudo systemctl status nginx

# Portas abertas?
sudo ss -tlnp | grep -E '80|443|8080|8888'

# Responde externamente? (do seu computador, não do servidor)
curl -I http://videos.site.com.br
curl -I http://omv.site.com.br
```

---

## Portas em uso no servidor

| Porta | Serviço         |
|-------|-----------------|
| 80    | Nginx (HTTP)    |
| 443   | Nginx (HTTPS)   |
| 8080  | Ad-Search web   |
| 7700  | Meilisearch     |
| 9000  | Whisper worker  |
| 8888  | OMV (movido)    |

> Meilisearch (7700) e Whisper (9000) são internos — não expor no roteador.
> Só liberar 80, 443 e, se necessário, 22 (SSH) no port forwarding do roteador.
