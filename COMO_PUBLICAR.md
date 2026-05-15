# 🚀 Guia Completo — Como Publicar o GlobalBR News no GitHub Pages

**Repositório:** `non-s.github.io`  
**URL final:** `https://non-s.github.io`  
**Usuário GitHub:** `non-s`

---

## Pré-requisitos

- Conta no GitHub (já tem: `non-s`)
- Git instalado no computador (opcional — pode usar a interface web)
- Os arquivos do blog nesta pasta

---

## Passo 1 — Criar o repositório no GitHub

1. Acesse [github.com/new](https://github.com/new)
2. Em **Repository name**, digite exatamente: `non-s.github.io`
   > ⚠️ O nome deve ser **exatamente** `<seu-usuario>.github.io` para funcionar como GitHub Pages
3. Deixe o repositório **Public** (GitHub Pages gratuito exige público)
4. **NÃO** marque "Add a README file", "Add .gitignore" ou "Choose a license"
   > (já temos todos os arquivos prontos)
5. Clique em **Create repository**

---

## Passo 2 — Fazer upload dos arquivos

### Opção A — Via interface web do GitHub (mais fácil)

1. No repositório recém-criado, clique em **"uploading an existing file"**
2. Arraste **todos os arquivos e pastas** desta pasta para a área de upload:
   ```
   _config.yml
   Gemfile
   index.html
   fetch_news.py
   assets/
   _includes/
   _layouts/
   _posts/
   .github/
   ```
   > ⚠️ Atenção: a pasta `.github` pode estar oculta no Windows. Ative "Mostrar arquivos ocultos" no Explorer.
3. No campo "Commit changes", escreva: `🎉 Publicação inicial do GlobalBR News`
4. Clique em **Commit changes**

### Opção B — Via Git no terminal (recomendado para atualizações futuras)

```bash
# Na pasta onde estão os arquivos do blog:
git init
git add .
git commit -m "🎉 Publicação inicial do GlobalBR News"
git branch -M main
git remote add origin https://github.com/non-s/non-s.github.io.git
git push -u origin main
```

---

## Passo 3 — Ativar o GitHub Pages

1. No repositório, clique em **Settings** (engrenagem)
2. No menu lateral esquerdo, clique em **Pages**
3. Em **Source**, selecione:
   - Branch: `main`
   - Folder: `/ (root)`
4. Clique em **Save**
5. Aguarde 1-3 minutos
6. Aparecerá a mensagem: _"Your site is live at https://non-s.github.io"_ 🎉

> 💡 O GitHub Pages roda Jekyll automaticamente — não é necessário instalar nada!

---

## Passo 4 — Verificar se o blog está no ar

1. Acesse **https://non-s.github.io** no navegador
2. Você deve ver o post de boas-vindas
3. Para ver o status do deploy: repositório → aba **Actions**

Se aparecer erro de build, veja a seção **Solução de Problemas** abaixo.

---

## Passo 5 — Ativar as permissões do GitHub Actions

Para que a automação de notícias funcione (commit automático):

1. No repositório, vá em **Settings → Actions → General**
2. Em **Workflow permissions**, selecione:
   - ✅ **Read and write permissions**
3. Marque também:
   - ✅ **Allow GitHub Actions to create and approve pull requests**
4. Clique em **Save**

---

## Passo 6 — Testar a automação manualmente

1. No repositório, clique na aba **Actions**
2. No menu lateral, clique em **📰 Fetch News RSS**
3. Clique em **Run workflow → Run workflow**
4. Aguarde ~1 minuto
5. Verifique se novos posts apareceram na pasta `_posts/`
6. Acesse o blog e veja as notícias! 🎉

A partir de agora, o workflow roda automaticamente às **8h, 12h e 18h (horário de Brasília)**.

---

## Passo 7 — Personalizações opcionais

### 7.1 Ativar Google Analytics

1. Crie uma conta em [analytics.google.com](https://analytics.google.com)
2. Obtenha seu ID (formato `G-XXXXXXXXXX`)
3. Em `_config.yml`, descomente e preencha:
   ```yaml
   google_analytics: "G-XXXXXXXXXX"
   ```
4. Em `_includes/head.html`, descomente o bloco do Analytics

### 7.2 Ativar Google AdSense

1. Cadastre-se em [adsense.google.com](https://adsense.google.com)
2. Adicione o site `non-s.github.io` e aguarde aprovação
3. Após aprovado, em `_config.yml` adicione:
   ```yaml
   adsense_publisher_id: "ca-pub-XXXXXXXXXXXXXXXXX"
   ```
4. Nos arquivos de layout, descomente os blocos `<!-- ADSENSE -->` e substitua pelos códigos reais

### 7.3 Ativar links de afiliado Amazon

1. Cadastre-se em [associados.amazon.com.br](https://associados.amazon.com.br)
2. Obtenha sua tag de afiliado (ex: `techbrnews-20`)
3. Em `_config.yml` adicione:
   ```yaml
   amazon_affiliate_tag: "techbrnews-20"
   ```
4. Substitua os `PLACEHOLDER` nos arquivos `_layouts/default.html`, `_layouts/post.html` e `index.html` pelos seus links reais

### 7.4 Adicionar mais feeds RSS

Edite o arquivo `fetch_news.py`, na seção `FEEDS`:

```python
FEEDS = [
    # ... feeds existentes ...
    {
        "name":     "Nome do Portal",
        "url":      "https://exemplo.com/feed.xml",
        "category": "tecnologia",
        "tags":     ["tecnologia", "portal"],
        "source":   "Nome do Portal",
    },
]
```

---

## Estrutura de arquivos

```
non-s.github.io/
├── _config.yml              ← Configuração do Jekyll
├── Gemfile                  ← Dependências Ruby
├── index.html               ← Página inicial
├── fetch_news.py            ← Script de coleta RSS
├── fetch_news.log           ← Log das execuções (gerado automaticamente)
│
├── _posts/                  ← Posts do blog
│   └── 2026-05-13-welcome.md
│
├── _layouts/
│   ├── default.html         ← Layout base (navbar + footer)
│   └── post.html            ← Layout de post individual
│
├── _includes/
│   └── head.html            ← Meta tags, SEO, CSS
│
├── assets/
│   └── css/
│       └── style.scss       ← CSS customizado
│
└── .github/
    └── workflows/
        └── fetch-news.yml   ← GitHub Actions (automação)
```

---

## Solução de Problemas

### Erro: "Page build failed"

1. Vá em **Settings → Pages** e verifique se há mensagem de erro
2. Verifique a aba **Actions** para detalhes do erro
3. Causa comum: frontmatter YAML incorreto em algum post
   - Solução: abra o arquivo `.md` com problema e verifique os `---`

### Workflow não está fazendo push

1. Verifique se as permissões estão corretas (Passo 5)
2. Na aba Actions, clique no workflow com erro para ver o log
3. Causa comum: a branch padrão é `master` e não `main`
   - Solução: no arquivo `fetch-news.yml`, troque `origin HEAD` por `origin main`

### Posts não aparecem no blog

1. O GitHub Pages pode demorar 1-3 minutos para rebuildar
2. Verifique se os arquivos estão na pasta `_posts/`
3. O nome do arquivo deve seguir o formato: `YYYY-MM-DD-titulo.md`
4. O frontmatter deve começar com `---` na primeira linha

### Feed RSS não carrega

- Alguns sites bloqueiam requisições automáticas
- O script tenta com User-Agent identificado como bot
- Se um feed específico falhar repetidamente, remova-o da lista `FEEDS`

---

## Links úteis

- 📖 [Documentação Jekyll](https://jekyllrb.com/docs/)
- 📖 [GitHub Pages + Jekyll](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll)
- 📖 [GitHub Actions](https://docs.github.com/en/actions)
- 💰 [Google AdSense](https://adsense.google.com)
- 🛒 [Amazon Associados Brasil](https://associados.amazon.com.br)
- 📊 [Google Analytics](https://analytics.google.com)
- 🔍 [Google Search Console](https://search.google.com/search-console) (para SEO)

---

*Criado com ❤️ para Julio — GlobalBR News (non-s.github.io)*
