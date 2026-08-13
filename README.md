# Liquid Wire

Canal automatizado de arte generativa procedural para YouTube. O projeto gera
videos abstratos com wireframes liquidos, movimento lento e audio ambiente
sintetizado localmente.

## Principio

- Sem acervos externos de vídeo, imagem ou música.
- Visual criado por Python a partir de matematica, seeds e malhas deformadas.
- Audio ambiente sintetico local para reduzir risco de Content ID.
- Cada video salva um `generator_profile` no metadata para rastreabilidade.

## Gerar um video

```bash
python generate_liquid_wire_video.py --preset short
python generate_liquid_wire_video.py --preset live-test --duration 120
python generate_liquid_wire_video.py --preset long --duration 900
```

Saidas:

- `_videos/liquid_wire_*.mp4`
- `_videos/liquid_wire_*.json`
- `_assets/thumbnails/liquid_wire_*.jpg`

## Upload

O upload usa OAuth do YouTube em `youtube_token.json` ou no secret
`YOUTUBE_TOKEN`.

```bash
python upload_youtube.py --mode upload --privacy private --prefix liquid_wire_
```

Use `private` nos primeiros testes para validar Content ID antes de publicar.

## GitHub Actions

Variaveis:

- `LIQUID_WIRE_ENABLED=1`
- `YOUTUBE_PRIVACY=private` inicialmente

Secrets:

- `YOUTUBE_TOKEN`
- `GEMINI_API_KEY` opcional
- `GH_PAT` opcional para refresh automatico do token OAuth

Workflow principal:

- `Liquid Wire - Generate and Upload`

## Nova identidade

- Nome: Liquid Wire
- Handle: `@LiquidWireStudio`
- Descricao: slow generative visuals, liquid wireframes, soft motion, and
  ambient soundscapes for focus, rest, and late-night calm.
