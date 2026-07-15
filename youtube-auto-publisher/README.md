# YouTube Auto Publisher

Automacao completa para criar e publicar videos no YouTube usando IA.

## Funcionalidades

- **Download de videos**: Busca clipes HD no Pexels por topico
- **Geracao de roteiro**: Usa Groq (LLaMA 3) para criar scripts engajantes
- **Narracao por IA**: Groq PlayAI TTS com multiplas vozes em PT-BR
- **Legendas automaticas**: Transcreve audio com Whisper e gera SRT sincronizado
- **Musica de fundo**: Adiciona musicas CC0 com volume dinamico e fade
- **Edicao de video**: Concatena clipes com efeitos Ken Burns, zoom e transitions
- **Publicacao automatica**: Upload para o YouTube com SEO otimizado
- **Agendador**: Publica videos automaticamente em horarios configurados

## Fluxo do Pipeline

```
Topico → Groq LLM (roteiro) → Groq TTS (voz) → Whisper (legendas)
→ Pexels (clipes) → MusicMixer (audio) → VideoEditor (edicao) → YouTube
```

## Instalacao

### Pre-requisitos

- Python 3.10+
- FFmpeg instalado no sistema
- Conta no Pexels (API gratuita)
- Conta no Groq (API gratuita)
- Projeto no Google Cloud com YouTube Data API v3

### 1. Clone o repositorio

```bash
git clone https://github.com/non-s/youtube-auto-publisher.git
cd youtube-auto-publisher
```

### 2. Instale as dependencias

```bash
pip install -r requirements.txt
```

### 3. Configure as variaveis de ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas chaves de API
```

### 4. Configure as credenciais do YouTube

1. Acesse [Google Cloud Console](https://console.cloud.google.com)
2. Crie um projeto e ative a **YouTube Data API v3**
3. Crie credenciais OAuth 2.0 (Desktop App)
4. Baixe o `credentials.json` e coloque na raiz do projeto

## Configuracao

Edite o arquivo `.env` com suas credenciais:

```env
# Pexels
PEXELS_API_KEY=sua_chave_aqui

# Groq
GROQ_API_KEY=sua_chave_aqui

# YouTube
YOUTUBE_CLIENT_ID=seu_client_id
YOUTUBE_CLIENT_SECRET=seu_client_secret
```

### APIs necessarias

| API | Uso | Link |
|-----|-----|------|
| Pexels | Videos HD gratuitos | [pexels.com/api](https://www.pexels.com/api/) |
| Groq | LLM + TTS (gratuito) | [console.groq.com](https://console.groq.com) |
| YouTube Data API v3 | Upload de videos | [cloud.google.com](https://console.cloud.google.com) |

## Uso

### Criar um video sobre um topico

```bash
python main.py --topic natureza
```

### Opcoes disponiveis

```bash
python main.py --help

# Topico especifico com duracao
python main.py --topic tecnologia --duration 90

# Escolher numero de clipes
python main.py --topic viagem --clips 6

# Escolher voz especifica
python main.py --topic saude --voice Aaliyah-PlayAI

# Modo teste (sem publicar)
python main.py --topic culinaria --dry-run

# Criar video sem publicar
python main.py --topic fitness --no-upload

# Modo agendador automatico
python main.py --schedule

# Listar topicos e vozes
python main.py --list-topics
python main.py --list-voices
```

### Vozes disponiveis (Groq PlayAI)

| Voz | Genero |
|-----|--------|
| Fritz-PlayAI | Masculina |
| Aaliyah-PlayAI | Feminina |
| Adelaide-PlayAI | Feminina |
| Angelo-PlayAI | Masculino |
| Arsenio-PlayAI | Masculino |
| Briggs-PlayAI | Masculino |
| Calum-PlayAI | Masculino |
| Celeste-PlayAI | Feminina |

## Estrutura do Projeto

```
youtube-auto-publisher/
├── main.py                    # Ponto de entrada CLI
├── config.py                  # Configuracoes centralizadas
├── requirements.txt           # Dependencias Python
├── .env.example               # Modelo de variaveis de ambiente
├── .gitignore                 # Arquivos ignorados pelo Git
├── src/
│   ├── pexels_downloader.py   # Download de videos do Pexels
│   ├── voice_generator.py     # TTS com Groq PlayAI
│   ├── subtitle_generator.py  # Legendas com Whisper
│   ├── music_mixer.py         # Mixer de musica de fundo
│   ├── video_editor.py        # Edicao de video com MoviePy
│   └── youtube_uploader.py    # Upload para YouTube
├── assets/
│   ├── music/                 # Musicas CC0 (adicione suas faixas)
│   └── fonts/                 # Fontes customizadas
├── output/                    # Videos finais gerados
├── temp/                      # Arquivos temporarios
├── data/                      # Banco de dados SQLite
└── logs/                      # Logs da aplicacao
```

## Musicas de Fundo

Adicione musicas livres de direitos autorais (CC0/CC-BY) na pasta `assets/music/`.

Fontes recomendadas:
- [Free Music Archive](https://freemusicarchive.org) - Filtrar por CC0
- [ccMixter](http://ccmixter.org) - Musicas CC
- [Pixabay Music](https://pixabay.com/music/) - 100% livre

## Configuracoes Avancadas

### Agendamento automatico

Configure no `.env`:

```env
PUBLISH_SCHEDULE=0 10 * * *    # Todo dia as 10h
MAX_VIDEOS_PER_DAY=3           # Maximo 3 videos por dia
ENABLE_AUTO_PUBLISH=true
```

### Qualidade do video

```env
VIDEO_RESOLUTION=1920x1080
VIDEO_FPS=30
```

### Legendas

```env
SUBTITLE_FONT=Arial
SUBTITLE_FONT_SIZE=48
SUBTITLE_COLOR=white
SUBTITLE_STROKE_COLOR=black
```

## Topicos predefinidos

- natureza, viagem, tecnologia, culinaria
- saude, fitness, negocios, motivacao
- cultura, historia, ciencia, arte

Adicione mais em `config.py` → `VIDEO_TOPICS`

## Notas de Seguranca

- Nunca commite o arquivo `.env` (ja esta no `.gitignore`)
- Proteja o `credentials.json` e `token.json`
- Use variaveis de ambiente em producao

## Licenca

MIT License - veja [LICENSE](LICENSE) para detalhes.

---
Feito com Groq, Pexels API e YouTube Data API v3
