---
layout: post
title: "Estudo inovador mostra IA aprendendo novas habilidades sem esquecer as antigas"
date: 2026-05-17 01:19:14 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, conflict, self, learning, continual, distillation-fine, tuning, self-distillation-fine-tuning, catastrophic-forgetting-ai, on-policy-learning, ai-continual-learning, reinforcement-learning-without-rewards, mit-ai-research, how-to-teach-ai-new-skills, ai-model-retention-techniques, self-teaching-ai-models, avoid-ai-forgetting-old-skills]
author: "GlobalBR News"
description: "Pesquisadores desenvolvem Self-Distillation Fine-Tuning (SDFT), um novo método de IA que ensina modelos a realizar novas tarefas mantendo seus conhecimentos anteriores intactos. Acaba com a"
source_url: "https://arxiv.org/abs/2601.19897"
source_name: "Hacker News"
sentiment: "positive"
lang: "pt-br"
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
permalink: "/pt/technology/2026/05/17/self-distillation-enables-continual-learning-pdf/"
translated_from: "2026-05-17-self-distillation-enables-continual-learning-pdf.md"
---

Pesquisadores do [MIT](https://pt.wikipedia.org/wiki/Massachusetts_Institute_of_Technology) e da [Universidade do Texas em Austin](https://pt.wikipedia.org/wiki/Universidade_do_Texas_em_Austin) acabam de publicar um estudo que pode mudar para sempre a forma como a IA aprende. Seu método, chamado *Self-Distillation Fine-Tuning* (SDFT), resolve um problema que assombra o aprendizado de máquina há anos: o *esquecimento catastrófico*. Isso ocorre quando um modelo de IA aprende uma nova tarefa, mas esquece tudo o que sabia antes. O SDFT mantém o conhecimento antigo seguro enquanto permite que o modelo adquira novas habilidades. A equipe publicou o trabalho no [arXiv](https://arxiv.org) em 27 de janeiro de 2026. Ainda é apenas um artigo, mas o método parece promissor o suficiente para chamar atenção rapidamente no [Hacker News](https://news.ycombinator.com) e além.

A ideia central é simples: usar o próprio modelo como professor. A maioria dos treinamentos de IA depende de conjuntos de dados fixos ou exemplos escritos por humanos, mas o SDFT inverte esse paradigma. O modelo gera seus próprios sinais de treinamento ao analisar exemplos do que deveria fazer e, em seguida, ensina a si mesmo a fazer melhor na próxima vez. É como um aluno usando suas próprias provas antigas para estudar, em vez de depender de um livro didático escrito por outra pessoa. Trata-se de um aprendizado *on-policy* — em que os dados de treinamento vêm das próprias ações do modelo, não de uma fonte externa. A alternativa atual é o *supervised fine-tuning* (SFT), que é *off-policy*. Isso significa que o treinamento é feito com exemplos que o modelo não criou, o que pode gerar conflitos entre habilidades antigas e novas. O SDFT elimina esse problema por completo.

## Como o SDFT funciona na prática

O artigo da equipe detalha o processo da seguinte forma: primeiro, o modelo recebe um conjunto de demonstrações — exemplos de uma tarefa sendo executada corretamente. Em vez de usar essas demonstrações para treinar diretamente, o modelo as utiliza para condicionar suas próprias previsões. Depois, compara suas previsões com as demonstrações e ajusta-se com base na diferença. A chave está no fato de que o modelo não está simplesmente copiando as demonstrações. Ele está aprendendo com o quão próximo seu próprio resultado está da resposta certa. Ao longo de várias rodadas, esse ciclo de autocorreção mantém o modelo afiado em novas tarefas sem apagar o que já sabe.

O método se baseia no *in-context learning*, uma técnica em que os modelos se adaptam a novas tarefas simplesmente ao visualizar exemplos em sua entrada. É por isso que funciona mesmo quando não há uma função de recompensa perfeita — um problema comum no aprendizado por reforço.

## Resultados dos testes

Os pesquisadores submeteram o SDFT a dois tipos de testes: aprendizado de habilidades e tarefas de conhecimento. No aprendizado de habilidades, eles avaliaram quão bem o modelo conseguia adquirir novas capacidades, como resolver quebra-cabeças ou seguir novas instruções. Nas tarefas de conhecimento, verificaram se o modelo conseguia adicionar novos fatos à sua memória sem corromper os antigos. Os resultados mostram que o SDFT supera o ajuste fino tradicional em todos os testes. Modelos usando SDFT retiveram 90% de suas habilidades antigas após aprenderem novas, enquanto o ajuste fino padrão reduziu essa retenção para 60%. Isso é significativo porque a maioria dos modelos de IA hoje ou permanecem estáticos após o treinamento ou exigem retreinamento massivo para adicionar novas habilidades. Até mesmo os melhores métodos de aprendizado por reforço têm dificuldade aqui porque precisam de sinais de recompensa precisos, que são difíceis de definir para tarefas complexas. O SDFT contorna esse problema inteiramente.

## Por que isso importa além do laboratório

O esquecimento é um dos maiores obstáculos para tornar a IA verdadeiramente útil. Hoje, a maioria dos sistemas de IA é estática — eles não conseguem continuar aprendendo após a implantação sem quebrar. É por isso que os chatbots esquecem suas preferências após uma atualização ou por que os carros autônomos enfrentam problemas quando surgem novas placas de trânsito. O SDFT muda o jogo ao permitir que os modelos evoluam em tempo real sem perder seu desempenho.

As implicações se espalham por diversos setores. Na robótica, um robô de fábrica poderia aprender novas tarefas de montagem sem esquecer os protocolos de segurança. Na área da saúde, um assistente de IA poderia adicionar novas diretrizes médicas à sua base de conhecimento sem desaprender as antigas. Até mesmo na tecnologia do consumidor, o assistente de IA do seu celular poderia se adaptar a novos aplicativos ou recursos sem parecer que está começando do zero toda vez.

Claro, ainda estamos nos primeiros passos. O artigo mostra promessa em testes controlados, mas o uso no mundo real trará desafios inesperados. A equipe já planeja experimentos com modelos maiores e tarefas mais complexas. Eles também estão investigando se o SDFT pode ajudar no aprendizado multimodal — ensinando a IA a lidar com imagens, texto e som simultaneamente, sem conflitos.

## O que vem pela frente

Espere ouvir mais sobre o SDFT nos próximos meses. Os pesquisadores disponibilizaram o código-fonte aberto no GitHub, o que significa que outras equipes podem começar a testá-lo imediatamente. Se o método se mantiver sob pressão do mundo real, poderemos ver as primeiras aplicações comerciais em até um ano. Isso é rápido para a pesquisa em IA. Até lá, o artigo permanece no arXiv, aguardando que outros especialistas encontrem falhas ou confirmem suas forças. Uma coisa é certa: se o SDFT cumprir sua promessa, não vai apenas ajustar como a IA aprende. Vai redefinir o que a IA pode fazer.
