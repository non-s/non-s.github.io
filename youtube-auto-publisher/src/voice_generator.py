"""
voice_generator.py - Geracao de voz com edge-tts (Microsoft TTS PT-BR)
Converte texto em audio usando Microsoft Edge TTS (gratuito, suporta PT-BR)
"""
import json
import random
import asyncio
from pathlib import Path
from typing import Optional
from groq import Groq
from loguru import logger
import config


class VoiceGenerator:
    """Gera narracoes em voz usando edge-tts (Microsoft TTS PT-BR)"""

    EDGE_VOICES = [
        "pt-BR-FranciscaNeural",
        "pt-BR-AntonioNeural",
        "pt-BR-ThalitaNeural",
    ]

    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.default_voice = self.EDGE_VOICES[0]
        self.available_voices = self.EDGE_VOICES

    def generate_audio(self, text, output_path, voice=None, speed=1.0):
        import edge_tts
        if not voice or "PlayAI" in str(voice):
            voice = self.EDGE_VOICES[0]
        logger.info(f"Gerando audio com voz '{voice}'...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async def _generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
        asyncio.run(_generate())
        logger.success(f"Audio gerado: {output_path}")
        return output_path

    def generate_curiosity_script(self, topic, duration_seconds=60, language="pt-BR"):
        words_per_minute = 140
        target_words = int((duration_seconds / 60) * words_per_minute)
        prompt = f"""Crie roteiro de CURIOSIDADES em {language} sobre: \"{topic}\"

Aprox {target_words} palavras. Formato:
1. Abertura impactante com pergunta ou fato chocante
2. 3-5 fatos incriveis e surpreendentes com dados especificos
3. Encerramento: Curta, compartilhe e se inscreva!

Regras: linguagem simples e entusiasmada, frases curtas, apenas texto narrado sem marcacoes.
"""
        completion = self.client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Voce e roteirista especialista em curiosidades para YouTube. Cria conteudo viral e educativo."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.85,
            max_tokens=1200,
        )
        script = completion.choices[0].message.content.strip()
        logger.info(f"Roteiro gerado: {len(script.split())} palavras")
        return script

    def generate_script(self, topic, duration_seconds=60, style="engajante", language="pt-BR"):
        return self.generate_curiosity_script(topic, duration_seconds, language)

    def generate_random_voice_audio(self, text, output_path):
        voice = random.choice(self.EDGE_VOICES)
        logger.info(f"Voz selecionada: {voice}")
        return self.generate_audio(text, output_path, voice=voice)

    def generate_title_and_description(self, topic, script):
        prompt = f"""Crie metadata SEO para video de CURIOSIDADES sobre \"{topic}\".
Formato JSON exato:
{{"title": "titulo com emoji max 80 chars", "description": "descricao com hashtags", "tags": "tag1,tag2,tag3"}}
Topico: {topic}
Roteiro: {script[:200]}
Responda APENAS com JSON valido:"""
        try:
            completion = self.client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Especialista em SEO YouTube. Responda APENAS com JSON valido."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=600,
            )
            content = completion.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Erro ao gerar metadata: {e}")
            return {
                "title": f"Curiosidades Incriveis sobre {topic.title()} 🤯",
                "description": f"Descubra fatos surpreendentes sobre {topic}! #curiosidades #fatos #educacao",
                "tags": f"curiosidades,{topic},fatos incriveis,voce sabia,educacao",
            }
