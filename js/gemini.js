// Gemini AI Script & Metadata Generator

import { CONFIG } from './config.js';

// Pre-packaged high quality fallback templates for instant generation
const FALLBACK_TEMPLATES = {
    meditation: {
        title: "Meditação Guiada de 5 Minutos para Calma e Paz Interior 🧘‍♂️✨ | Sons Relaxantes",
        script: `Feche os olhos suavemente. Respire fundo pelo nariz... e solte o ar devagar pela boca.\n\nSinta todo o peso dos seus ombros desaparecer a cada expiração. Imagine uma luz serena e acolhedora iluminando a sua mente. Este momento é exclusivamente seu. Deixe que todos os pensamentos da rotina se esvaiam como folhas flutuando em um rio calmo.\n\nVocê está seguro, você está no presente. Respire paz... e exale qualquer tensão acumulada. Permaneça nesse estado de presença e calma.`,
        description: "Bem-vindo ao canal AuraZen! Esta meditação guiada foi desenvolvida para ajudar você a encontrar paz interior, aliviar a ansiedade e recarregar suas energias.\n\n🎧 Recomendamos o uso de fones de ouvido para uma experiência totalmente imersiva.\n\n✨ Se inscreva no canal e ative o sininho para novos vídeos diários de meditação e relaxamento!",
        tags: "#meditacao #relaxamento #pazinterior #ansiedade #mindfulness #foco"
    },
    sleep: {
        title: "Sons de Chuva Suave para Sono Profundo e Insônia (Chuva na Janela 🌙🌧️)",
        script: `A noite chegou trazendo quietude e conforto. O som da chuva caindo suavemente lá fora embala o seu descanso...\n\nSinta seu corpo afundar confortavelmente na cama. A cada gota de chuva que toca a janela, sua mente se acalma mais e mais. Não há nada a fazer agora, nada a resolver. Apenas entregar-se ao sono restaurador e profundo.\n\nTenha uma noite tranquila e revigorante.`,
        description: "Deixe a chuva suave e os sons relaxantes da noite levarem embora toda a insônia e cansaço. Ideal para dormir, estudar ou meditar.\n\n😴 Durma bem e acerte o despertador com renovação de energias.\n\n inscreva-se no AuraZen para mais noites de sono tranquilo!",
        tags: "#chuvaparadormir #sonoprofundo #insonia #sonsrelaxantes #somdachuva"
    },
    focus: {
        title: "Música Lo-Fi & Foco Profundo para Estudo e Trabalho 📚☕ | Concentração Total",
        script: `Bem-vindo ao seu ambiente de foco profundo.\n\nElimine todas as distrações. Ajuste sua postura, tome um gole d'água e prepare sua mente para entrar no estado de Flow.\n\nA cada minuto que passa, sua capacidade de aprendizado e atenção se multiplicam. Você é capaz, disciplinado e compenetrado.\n\nConcentre-se no seu objetivo agora. Bom trabalho.`,
        description: "Trilha sonora perfeita para momentos de estudo intenso, leitura, programação e foco no trabalho.\n\n☕ Pegue seu café/chá e mantenha a produtividade no topo!\n\nDeixe seu like e se inscreva no canal para acompanhar nossa playlist de foco.",
        tags: "#lofi #estudo #focoprofundo #concentracao #musicaestudo #trabalho"
    },
    stoicism: {
        title: "Citações Estoicas de Marco Aurélio & Sêneca para Fazer Você Inabalável 🏛️⚔️",
        script: `"Você tem poder sobre sua mente - não sobre eventos externos. Perceba isso, e você encontrará força." - Marco Aurélio.\n\nA sabedoria estoica nos lembra diariamente: não somos perturbados pelas coisas que acontecem, mas pela opinião que formamos sobre elas.\n\nMantenha a calma diante do caos. Domine suas reações e cultive a virtude da virtude inabalável. Hoje, escolha ser mais forte do que suas desculpas.`,
        description: "Reflexões e filosofias de vida inspiradas no Estoicismo. Aprenda a dominar suas emoções, desenvolver resiliência mental e superar dificuldades com sabedoria estoica.\n\n🏛️ Se inscreva no canal AuraZen para reflexões diárias de filosofia e autocontrole.",
        tags: "#estoicismo #filosofia #marcoaurelio #seneca #resiliencia #motivação"
    },
    nature: {
        title: "Sons da Natureza e Floresta Encantada para Relaxar e Aliviar o Estresse 🌿🕊️",
        script: `Caminhe mentalmente por uma floresta serena, onde o vento suave balança as folhas e os pássaros cantam suavemente ao fundo.\n\nSinta a energia purificadora da natureza renovando cada célula do seu corpo. Respire o ar puro. Conecte-se com a essência da terra e permita-se desacelerar.`,
        description: "Sons relaxantes da natureza com imagens HD de floresta e rio. Excelente para acalmar a mente, diminuir a pressão do dia a dia e renovar o espírito.\n\n🌿 Inscreva-se no canal para mais vídeos de paisagens e sons naturais!",
        tags: "#sonsdanatureza #floresta #relaxamento #estresse #natureza #paz"
    },
    affirmations: {
        title: "Afirmações Positivas Matinais para Atrair Prosperidade, Confiança e Paz ✨🌅",
        script: `Repita mentalmente ou em voz alta:\n\nEu sou merecedor de paz, felicidade e sucesso.\nEu confio no processo da vida e nas minhas habilidades.\nHoje será um dia abençoado, produtivo e repleto de oportunidades extraordinárias.\nEu escolho emanar gratidão e amor por onde eu passar.`,
        description: "Comece o seu dia com a vibração elevada! Estas afirmações diárias reprogramam a mente para a abundância, autoconfiança e paz interior.\n\n🌅 Pratique todas as manhãs para ver transformações reais na sua rotina.\n\nInscreva-se no AuraZen!",
        tags: "#afirmaçõespositivas #gratidao #abundancia #lei-da-atracao #mindset"
    }
};

export async function generateContentWithGemini(themeKey, customPrompt, tone, length) {
    const geminiKey = CONFIG.GEMINI_API_KEY;

    // If Gemini key is provided, make real API request
    if (geminiKey) {
        try {
            const systemPrompt = `Você é um roteirista sênior especializado em canais do YouTube de Relaxamento, Meditação e Foco.
Sua missão é criar um roteiro sereno e cativante em português, além de metadados perfeitos para o YouTube.

Retorne EXATAMENTE um objeto JSON (sem marcações markdown adicionais) no seguinte formato:
{
  "title": "Título chamativo com emojis para YouTube",
  "script": "Texto completo da narração/roteiro relaxante...",
  "description": "Descrição completa do vídeo com convite para inscrição",
  "tags": "#hashtag1 #hashtag2 #hashtag3 #hashtag4"
}`;

            const userPrompt = `Tema: ${themeKey}
Instruções adicionais: ${customPrompt || 'Nenhuma'}
Tom: ${tone}
Duração: ${length}`;

            const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiKey}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [
                        { role: 'user', parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }] }
                    ],
                    generationConfig: { responseMimeType: "application/json" }
                })
            });

            if (response.ok) {
                const data = await response.json();
                const textContent = data.candidates?.[0]?.content?.parts?.[0]?.text;
                if (textContent) {
                    return JSON.parse(textContent);
                }
            }
        } catch (err) {
            console.warn("Gemini API call error, falling back to local generator:", err);
        }
    }

    // Fallback Generator
    const base = FALLBACK_TEMPLATES[themeKey] || FALLBACK_TEMPLATES.meditation;
    
    let scriptText = base.script;
    if (customPrompt && customPrompt.trim()) {
        scriptText = `${customPrompt.trim()}\n\n${base.script}`;
    }

    return {
        title: base.title,
        script: scriptText,
        description: base.description,
        tags: base.tags
    };
}
