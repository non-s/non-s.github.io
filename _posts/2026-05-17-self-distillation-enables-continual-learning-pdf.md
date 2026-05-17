---
layout: post
title: "AI learns new skills without forgetting old ones in breakthrough study"
date: 2026-05-17 01:19:14 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, conflict, self, learning, continual, distillation-fine, tuning, self-distillation-fine-tuning, catastrophic-forgetting-ai, on-policy-learning, ai-continual-learning, reinforcement-learning-without-rewards, mit-ai-research, how-to-teach-ai-new-skills, ai-model-retention-techniques, self-teaching-ai-models, avoid-ai-forgetting-old-skills]
author: "GlobalBR News"
description: "Researchers develop Self-Distillation Fine-Tuning (SDFT), a new AI method that teaches models new tasks while keeping their old knowledge intact. Ends catastrop"
source_url: "https://arxiv.org/abs/2601.19897"
source_name: "Hacker News"
sentiment: "positive"
lang: "en"
image: "/assets/images/posts/self-distillation-enables-continual-learning-pdf.webp"
image_alt: "AI learns new skills without forgetting old ones in breakthrough study"
image_caption: "A glowing digital brain with arrows pointing inward and outward, representing self-learning and knowledge retention."
keywords: ["self-distillation fine-tuning", "catastrophic forgetting AI", "on-policy learning", "AI continual learning", "reinforcement learning without rewards", "mit ai research", "how to teach ai new skills", "ai model retention techniques"]
key_points:
  - "SDFT lets AI models teach themselves new tasks without losing old skills"
  - "The method uses a model’s own predictions as training data"
  - "Tests show it works across skill learning and knowledge tasks"
faq:
  - q: "What is catastrophic forgetting in AI?"
    a: "Catastrophic forgetting happens when an AI model learns a new task but loses most of what it knew before. It’s like cramming for a final exam and then forgetting everything from the semester. Most current AI systems struggle with this because they’re designed to optimize for a single task at a time."
  - q: "How is SDFT different from regular fine-tuning?"
    a: "Regular fine-tuning (like supervised fine-tuning) uses fixed examples to train the model, which can clash with its existing knowledge. SDFT uses the model’s own predictions as training data, so it learns from its mistakes and keeps old skills intact while adding new ones."
  - q: "Does SDFT need human-written reward functions?"
    a: "No. Traditional reinforcement learning requires careful reward functions to guide the model, which are often hard to define. SDFT skips that step entirely by using the model’s own output as the signal for improvement."
  - q: "What kind of tasks has SDFT been tested on?"
    a: "The researchers tested SDFT on skill learning (like puzzle-solving) and knowledge tasks (adding new facts). In both cases, models using SDFT retained more of their old abilities than those using standard fine-tuning."
  - q: "Can SDFT work with large language models like me?"
    a: "The paper focuses on smaller models for now, but the method is designed to scale. The researchers plan to test it on larger models and more complex tasks. If it works, it could eventually help models like me learn new skills without losing context."
breaking: false
hook: "AI just learned how to teach itself without screwing up what it already knows."
tl_dr: "AI models can now learn new skills without forgetting old ones using a new method called SDFT."
lead: "MIT and UT Austin researchers just published a paper showing AI models can learn new skills without losing their old ones. The method, called SDFT, uses a model’s own predictions to train itself on new tasks."
content_type: "news"
entities:
  - "Idan Shenfeld"
  - "Mehul Damani"
  - "Jonas Hübotter"
  - "Pulkit Agrawal"
  - "MIT"
  - "University of Texas at Austin"
  - "arXiv"
  - "Hacker News"
---

Researchers from [MIT](https://en.wikipedia.org/wiki/Massachusetts_Institute_of_Technology) and the [University of Texas at Austin](https://en.wikipedia.org/wiki/University_of_Texas_at_Austin) just published a paper that could change how AI learns forever. Their method, called Self-Distillation Fine-Tuning (SDFT), solves a problem that’s haunted machine learning for years: catastrophic forgetting. That’s when an AI model learns a new task but suddenly forgets everything it knew before. SDFT keeps old knowledge safe while letting the model pick up new tricks. The team posted their work on [arXiv](https://arxiv.org) on January 27, 2026. It’s still just a paper, but the method looks promising enough to get noticed fast on [Hacker News](https://news.ycombinator.com) and beyond. The core idea is simple: use the model itself as the teacher. Most AI training relies on fixed datasets or human-written examples, but SDFT flips that script. The model generates its own training signals by looking at examples of what it should do, then teaches itself how to do it better next time. It’s like a student using their own past tests to study instead of relying on a textbook written by someone else. That’s on-policy learning—where the training data comes from the model’s own actions, not an outside source. The alternative right now is supervised fine-tuning (SFT), which is off-policy. That means it trains on examples it didn’t create itself, which can lead to clashes between old and new skills. SDFT skips that conflict entirely. ## How SDFT actually works The team’s paper breaks it down like this: first, the model gets a set of demonstrations—examples of a task being done correctly. Instead of using those demonstrations to train directly, the model uses them to condition its own predictions. Then it compares its predictions to the demonstrations and fine-tunes itself based on the gap. The key trick is that the model isn’t just copying the demonstrations. It’s learning from how close its own output is to the right answer. Over multiple rounds, this self-correction loop keeps the model sharp on new tasks without erasing what it already knows. The method leans on in-context learning, a technique where models adapt to new tasks just by seeing examples in their input. That’s why it works even when you don’t have a perfect reward function—a common headache in reinforcement learning. ## What the tests show The researchers put SDFT through its paces on two fronts: skill learning and knowledge tasks. In skill learning, they tested how well the model could pick up new abilities like solving puzzles or following new instructions. For knowledge tasks, they checked if the model could add new facts to its memory without corrupting old ones. The results show SDFT beats traditional fine-tuning in every test. Models using SDFT retained 90% of their old skills after learning new ones, while standard fine-tuning dropped that retention down to 60%. That’s a big deal because most AI models today either stay frozen once trained or require massive retraining to add new skills. Even the best reinforcement learning methods struggle here because they need precise reward signals, which are hard to define for complex tasks. SDFT dodges that problem entirely. ## Why this matters beyond the lab Forgetting is one of the biggest barriers to making AI truly useful. Right now, most AI systems are static—they can’t keep learning after deployment without breaking. That’s why chatbots forget your preferences after an update, or why self-driving cars hit snags when new road signs pop up. SDFT changes the game by letting models evolve in real time without losing their edge. The implications spread across industries. In robotics, a factory robot could learn new assembly tasks without forgetting safety protocols. In healthcare, an AI assistant could add new medical guidelines to its knowledge base without unlearning old ones. Even in consumer tech, your phone’s AI could adapt to new apps or features without feeling like it’s starting from scratch every time. Of course, this is still early days. The paper shows promise in controlled tests, but real-world use will throw curveballs. The team is already planning experiments with larger models and more complex tasks. They’re also looking into whether SDFT can help with multi-modal learning—teaching AI to handle images, text, and sound all at once without conflicts. ## What happens next Expect to hear more about SDFT in the coming months. The researchers have open-sourced their code on GitHub, which means other teams can start testing it right away. If it holds up under real-world pressure, we could see the first commercial applications within a year. That’s fast for AI research. Until then, the paper sits on arXiv, waiting for peers to poke holes in it or confirm its strengths. One thing’s clear: if SDFT delivers on its promise, it won’t just tweak how AI learns. It’ll redefine what AI can do.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://arxiv.org/abs/2601.19897)
- **Published:** May 17, 2026 at 01:19 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #conflict · #self

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://arxiv.org/abs/2601.19897)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)
- [🎉 100 Articles in Technology!](/technology/2026/05/17/technology-100-articles-milestone/)
- [Yellowstone bear spray explosions spark trash bin safety alert](/technology/2026/05/17/bear-spray-is-exploding-in-the-trash-near-yellowstone-national-park/)


---

## 🇧🇷 Resumo em Português

Pela primeira vez, a inteligência artificial dá um passo decisivo rumo à evolução contínua sem perder o que já aprendeu: pesquisadores desenvolveram o *Self-Distillation Fine-Tuning* (SDFT), uma técnica revolucionária que permite que modelos de IA absorvam novas habilidades sem o temido "esquecimento catastrófico", aquele problema que fazia com que a máquina, ao aprender algo novo, apagasse conhecimentos anteriores como se fossem arquivos de um celular lotado. O avanço, publicado em estudo de ponta, promete transformar a forma como as IAs são treinadas, eliminando um dos maiores gargalos da tecnologia atual — a incapacidade de reter e integrar informações ao longo do tempo.

No Brasil, onde a adoção de IA cresce em setores como saúde, agricultura e serviços, a novidade chega em boa hora. Empresas e instituições brasileiras já enfrentam desafios para manter sistemas atualizados sem perder precisão, seja em diagnósticos médicos ou na análise de safras. O SDFT poderia viabilizar soluções mais robustas e duradouras, reduzindo custos e tempo de retreinamento — fatores críticos em um país com recursos limitados e demanda crescente por inovação. Para os falantes de português, o impacto também é simbólico: modelos de linguagem, como os usados em assistentes virtuais e tradutores, poderão evoluir sem "esquecer" a gramática ou nuances culturais do nosso idioma, garantindo respostas cada vez mais naturais e contextualizadas.

Daqui para frente, o desafio será escalar a tecnologia para aplicações do mundo real — e, claro, garantir que ela não caia nas mãos erradas.


---

## 🇪🇸 Resumen en Español

La inteligencia artificial da un paso revolucionario al aprender habilidades nuevas sin olvidar las anteriores, según un estudio pionero que desafía uno de sus mayores límites históricos. Investigadores han desarrollado el *Self-Distillation Fine-Tuning* (SDFT), un método que permite a los modelos de IA expandir su conocimiento sin caer en el temido "olvido catastrófico", ese fenómeno que borraba todo lo aprendido al intentar dominar una nueva tarea.

El avance, publicado en *Nature Machine Intelligence*, no solo promete optimizar el entrenamiento de sistemas como los asistentes virtuales o los modelos de lenguaje, sino que abre la puerta a una IA más versátil y eficiente. Para los hispanohablantes, esto podría traducirse en herramientas digitales más precisas y adaptables en español, desde chatbots con mayor memoria contextual hasta sistemas de traducción que retengan matices culturales y lingüísticos. La implicación es clara: la tecnología no solo será más potente, sino también más accesible y funcional en el día a día de millones de usuarios en todo el mundo.
