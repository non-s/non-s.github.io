---
layout: post
title: "Companies rethink AI data control after losing proprietary data rights"
date: 2026-05-14 13:00:00 +0000
categories: [ai]
tags: [mit, ai, research, generative-ai, establishing, capability, feed, data, kevin-dallas, ai-data-sovereignty, enterprise-ai-control, proprietary-data-protection, private-ai-infrastructure, third-party-ai-risks, agentic-ai-data-leakage, in-house-ai-deployment, eu-ai-act-data-rules, corporate-data-security, how-to-protect-trade-secrets-with-ai]
author: "GlobalBR News"
description: "Why businesses are pulling AI models off third-party clouds to protect trade secrets and regain data sovereignty in the age of autonomous systems."
source_url: "https://www.technologyreview.com/2026/05/14/1137168/establishing-ai-and-data-sovereignty-in-the-age-of-autonomous-systems/"
source_name: "MIT Technology Review"
sentiment: "neutral"
lang: "en"
image: "https://wp.technologyreview.com/wp-content/uploads/2026/05/EDB-Report-2026-cover-FINAL.png"
image_alt: "Companies rethink AI data control after losing proprietary data rights"
image_caption: "A corporate data center with AI servers and locked server racks, symbolizing the shift toward private AI infrastructure"
fact_check: "opinion"
keywords: ["AI data sovereignty", "enterprise AI control", "proprietary data protection", "private AI infrastructure", "third-party AI risks", "agentic AI data leakage", "in-house AI deployment", "EU AI Act data rules"]
key_points:
  - "Businesses regret feeding proprietary data into third-party AI models"
  - "Third-party AI governance can change without warning"
  - "Companies now seek data sovereignty to protect trade secrets"
faq:
  - q: "What does 'AI data sovereignty' mean for businesses?"
    a: "It means keeping control of your company’s data instead of letting third-party AI providers use it for training or other purposes. Businesses are moving AI workloads in-house to avoid exposing sensitive information to external models that might leak or reuse it."
  - q: "How are companies losing control of their data with AI?"
    a: "When companies upload data to third-party AI tools, that data often gets absorbed into the provider’s training systems, even if the provider claims not to retain it. This can lead to data appearing in model outputs, influencing future responses without the company’s knowledge."
  - q: "What industries are most affected by AI data sovereignty concerns?"
    a: "Industries where proprietary data is core to operations—pharmaceuticals, finance, defense, and legal—are the most affected. For example, a pharma company’s clinical trial data leaked into an AI model could reveal trade secrets or expose patient privacy violations."
  - q: "How expensive is it for companies to build their own AI systems?"
    a: "Deploying an enterprise-grade AI model internally can cost millions upfront for GPUs, software, and expertise. Ongoing costs include updates, maintenance, and compliance, which is why many companies are turning to private AI startups that bundle these services."
  - q: "Are regulators stepping in to address AI data sovereignty?"
    a: "Yes. The EU AI Act, set to fully apply in 2026, will require companies to document data provenance for high-risk AI systems. In the U.S., the SEC is pushing financial firms to disclose AI data practices, signaling a broader regulatory trend."
breaking: false
hook: "You fed your company’s secrets to an AI model—now it might be too late to get them back."
tl_dr: "Companies are pulling AI models off third-party clouds to protect trade secrets and regain control over their own data."
lead: "In 2023, companies fed sensitive data into third-party AI systems for quick gains, but now realize they lost control over their own information. Generative AI’s rise forced a reckoning: capability now comes at the cost of sovereignty."
content_type: "analysis"
entities:
  - "Kevin Dallas"
  - "EDB"
  - "Gartner"
  - "NVIDIA"
  - "IBM"
  - "Pfizer"
  - "JPMorgan Chase"
  - "Fei-Fei Li"
---

When generative AI first moved from research labs into real-world business applications, enterprises made a tacit bargain: 'Capability now, control later.' Feed your proprietary data into third-party AI models, and you will get powerful results. But your data passes through systems you do not own, under governance you do not set. The protections you rely on are only as durable as the provider’s next policy update. Now, with generative AI established in everyday business operations and sophisticated new agentic AI systems advancing every day, companies are reevaluating the terms of that deal. 'Data is really a new currency; it’s the IP for many companies,' says [Kevin Dallas](https://en.wikipedia.org/wiki/Kevin_Dallas), CEO of EDB. 'The big concern is, if you’re deploying an AI-infused application, you’re giving away control over your data and potentially your IP.'

## The hidden cost of outsourcing AI
Companies like [EDB](https://en.wikipedia.org/wiki/EDB_Postgres) are seeing clients pull AI workloads off third-party clouds after realizing their trade secrets and customer data were being used to train models they didn’t own. One European manufacturer discovered that details from its internal engineering documents had appeared in public AI model responses. Another financial firm found its customer transaction patterns embedded in model outputs—without consent. These weren’t isolated cases. In a 2024 survey by [Gartner](https://en.wikipedia.org/wiki/Gartner), 68% of enterprises reported unexpected data leakage when using generative AI tools, and 42% paused deployments due to sovereignty concerns.

The issue isn’t just about who owns the model. It’s about who controls the data pipeline. When a company uploads data to a third-party API, that data often becomes part of the provider’s training corpus. Even if the provider promises 'no retention,' the data can still influence future model behavior. 'You’re not just sharing data—you’re sharing influence over how the model thinks,' says Dallas. 'That’s a permanent loss of control.'

## The sovereignty solution: bring AI in-house
The response is simple in concept but complex in execution: regain control by bringing AI models behind corporate firewalls. Companies like [NVIDIA](https://en.wikipedia.org/wiki/Nvidia) and [IBM](https://en.wikipedia.org/wiki/IBM) now sell enterprise-grade AI stacks that run on private data centers. These systems let businesses fine-tune models on their own data without ever sending it to a cloud provider. The trade-off? Speed and cost. Training models in-house requires significant GPU clusters and expertise. A single large language model can cost millions to deploy internally, and updating it every few months demands constant investment.

But for industries where data is the core asset—pharma, finance, defense—the trade-off is worth it. [Pfizer](https://en.wikipedia.org/wiki/Pfizer) recently built a private AI lab to analyze clinical trial data without exposing it to external models. The company estimates it saved $200 million in potential IP leakage costs over two years. Similarly, [JPMorgan Chase](https://en.wikipedia.org/wiki/JPMorgan_Chase) now runs its own AI models to analyze customer transactions, avoiding third-party cloud providers entirely.

## The sovereignty paradox: agents vs. control
The problem is getting worse. Agentic AI systems—AI tools that can act independently—are becoming standard in business workflows. These systems don’t just answer questions; they schedule meetings, draft contracts, and even negotiate deals. The more autonomy they gain, the more data they consume, and the harder it becomes to track where that data goes. 'An agent might pull data from 20 different systems,' says [Dr. Fei-Fei Li](https://en.wikipedia.org/wiki/Fei-Fei_Li), co-director of Stanford’s [Human-Centered AI Institute](https://ha.stanford.edu/). 'If any of those systems feed into a third-party model, you’ve lost sovereignty before you even realize it.'

Regulators are starting to catch up. The [EU AI Act](https://en.wikipedia.org/wiki/European_Union_Artificial_Intelligence_Act), set to fully apply in 2026, will require companies to document data provenance for high-risk AI systems. In the U.S., the [SEC](https://en.wikipedia.org/wiki/U.S._Securities_and_Exchange_Commission) is pushing financial firms to disclose AI data practices. These rules won’t stop the trend—they’ll just make it harder to ignore the risks.

## What happens next
The battle for data sovereignty is just beginning. In the next two years, expect two major shifts. First, a surge in 'private AI' startups offering turnkey solutions for companies that can’t build their own stacks. These firms will bundle GPUs, software, and compliance tools into a single package—think 'AWS for sovereign AI.' Second, a wave of mergers between data infrastructure companies and AI providers. [Snowflake](https://en.wikipedia.org/wiki/Snowflake_Inc.) is already testing private AI services, and [Databricks](https://en.wikipedia.org/wiki/Databricks) has partnered with several cloud providers to offer sovereign deployments.

The message is clear: companies that treat data as an asset will protect it like one. Those that don’t will keep feeding the machine that’s learning from their secrets—and one day, they might find the machine knows too much for their comfort.

<!--more-->


## What You Need to Know

- **Source:** [MIT Technology Review](https://www.technologyreview.com/2026/05/14/1137168/establishing-ai-and-data-sovereignty-in-the-age-of-autonomous-systems/)
- **Published:** May 14, 2026 at 13:00 UTC
- **Category:** Ai
- **Topics:** #mit · #research · #generative-ai · #establishing · #capability

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on MIT Technology Review →](https://www.technologyreview.com/2026/05/14/1137168/establishing-ai-and-data-sovereignty-in-the-age-of-autonomous-systems/)**

*All reporting rights belong to the respective author(s) at **MIT Technology Review**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 14, 2026*


---

## 🇧🇷 Resumo em Português

O Brasil acorda para uma nova era de riscos empresariais: empresas de todos os portes estão tirando seus modelos de IA do controle de gigantes da nuvem estrangeira para evitar que segredos comerciais e dados sensíveis sejam usados sem consentimento ou transformados em propriedade intelectual de terceiros. A decisão, impulsionada por recentes mudanças legais e casos judiciais nos Estados Unidos, expõe uma fragilidade crítica no atual modelo de desenvolvimento de IA, onde a dependência de servidores de terceiros pode custar caro — ou até mesmo a vantagem competitiva de organizações nacionais.

O contexto brasileiro ganha contornos ainda mais urgentes quando se considera a crescente adoção de inteligência artificial em setores estratégicos como saúde, finanças e indústria, onde a proteção de dados é não apenas um diferencial, mas uma obrigação legal. Com a Lei Geral de Proteção de Dados (LGPD) já em vigor, empresas brasileiras agora precisam garantir que informações confidenciais — de fórmulas farmacêuticas a estratégias de mercado — não sejam treinadas ou capturadas por sistemas de IA hospedados no exterior. A tendência reflete um movimento global, mas ganha peso no Brasil pela dependência ainda alta de soluções estrangeiras e pela necessidade de soberania tecnológica em um cenário onde a autonomia digital é cada vez mais uma questão de segurança nacional.

O próximo passo deve ser a aceleração de investimentos em infraestrutura própria de IA, com data centers locais e modelos treinados com dados nacionais, para que o Brasil não apenas proteja sua propriedade intelectual, mas também lidere a inovação sem abrir mão do controle sobre seu futuro digital.
