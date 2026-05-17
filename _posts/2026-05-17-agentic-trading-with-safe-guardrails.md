---
layout: post
title: "New AI trading tool adds safety rails to autonomous agents"
date: 2026-05-17 12:44:24 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, agentic-trading, safe-guardrails-article, shuriken, trade, comments, ai-trading-bot-with-guardrails, open-source-trading-agent-safety, shurikentrade-github, safe-ai-trading-tools, guardrails-for-automated-trading, autonomous-trading-bot-risks, interactive-brokers-api-trading, skills-based-trading-automation, python-trading-bot-guardrails, hacker-news-trading-tools]
author: "GlobalBR News"
description: "ShurikenTrade’s agentic AI trading bot uses guardrails to reduce risk. It’s open source with 15 upvotes on Hacker News."
source_url: "https://github.com/ShurikenTrade/shuriken-skills"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "https://opengraph.githubassets.com/7c0e093bb089723a2399daa756adb2e67268ed4f094c93d92390293a16b21d45/ShurikenTrade/shuriken-skills"
image_alt: "New AI trading tool adds safety rails to autonomous agents"
image_caption: "A terminal window showing Python code for a trading bot with a red error message blocking an illegal trade."
keywords: ["AI trading bot with guardrails", "open-source trading agent safety", "ShurikenTrade GitHub", "safe AI trading tools", "guardrails for automated trading", "autonomous trading bot risks", "Interactive Brokers API trading", "skills-based trading automation"]
key_points:
  - "New tool puts guardrails on AI trading agents"
  - "Code is open-source on GitHub under ShurikenTrade"
  - "Runs on Friday's Hacker News with 15 upvotes"
faq:
  - q: "What trading platforms does ShurikenTrade work with?"
    a: "Right now it only supports Interactive Brokers through their API. The team says they’re looking at adding other brokers, but no timeline is set."
  - q: "Can I use ShurikenTrade for crypto or options trading?"
    a: "Not yet. The code only handles U.S. stocks. The GitHub issues list shows users asking for crypto support, but nothing is implemented."
  - q: "How do the guardrails actually stop bad trades?"
    a: "Every trade must pass a skill check before the bot can place it. If the skill tries to break your rules, the system kills the order and logs the attempt, preventing the trade entirely."
  - q: "Is this safe for beginners to use?"
    a: "The repo warns that even with guardrails, the bot can still lose money in fast markets. They recommend paper trading first and keeping position sizes small until you’re confident."
  - q: "Who built ShurikenTrade and why?"
    a: "The project started as a side project by a solo developer called Shuriken on GitHub. They built it after seeing friends lose money on bots that ignored position sizing and risk limits."
breaking: false
hook: "After watching friends lose money, one coder built a trading bot that won’t let AI agents run wild."
tl_dr: "New open-source AI trading bot runs trades for you but won’t let it lose your shirt."
lead: "Open-source AI trading software called ShurikenTrade now lets software agents trade stocks automatically while keeping them from blowing up. The project posted on Hacker News Friday and quickly drew 15 upvotes and 5 comments."
content_type: "news"
entities:
  - "ShurikenTrade"
  - "Hacker News"
  - "Interactive Brokers"
  - "LangGraph"
  - "Shuriken (GitHub user)"
  - "Trade Ideas"
  - "TrendSpider"
---

A small team just dropped an open-source project that tries to solve a problem plenty of traders worry about: letting AI agents loose in the market without ending up with a blown account. The project, called ShurikenTrade, posted on Hacker News Friday morning and climbed to 15 upvotes by midday. Five users left comments, mostly asking how it actually keeps the bot from going rogue.

The tool is built around something it calls “skills”—think of them as plug-ins that tell the AI exactly what it can and can’t do. You can load up a skill that buys Apple stock when it dips 3%, but you can’t add a skill that shorts Tesla every hour without approval. The whole thing runs on Python and uses a system of “safeguards” to stop the bot if it breaks the rules you set.

Under the hood, ShurikenTrade leans on the LangGraph framework, the same library many people use to build AI agents that chain together tasks. The difference here is the safety layer. While most trading bots let you set stop-losses or time limits, this one ties every trade to a skill that must pass a review step before the bot even thinks about placing an order. If the skill tries to break the rules, the system kills the trade instantly and logs the attempt.

The GitHub repo is light on examples right now. The main README shows a single skill file that buys $SPY when the 50-day moving average crosses above the 200-day line. The team behind it says they built it because existing trading bots either lock you out of automation or give you too much rope to hang yourself. They argue that by forcing every trade through a skills-based gate, the bot stays within the lines you drew.

## How it stacks up to what’s already out there

Most retail trading bots—think Trade Ideas, TrendSpider, or even the algo bots on Interactive Brokers—require you to set one-off rules like “sell if price drops 5%.” They don’t stop you from stacking rules that cancel each other out or from running the bot 24/7 in a crash loop. ShurikenTrade’s skill system is more like a permission slip system. You can hand the bot a list of allowed actions, and it can’t deviate without throwing an error.

The project’s initial commit came from a solo developer who goes by “Shuriken” on GitHub. They say they built it after watching friends lose money on fully automated bots that ignored position sizing. The repo’s license is MIT, so anyone can fork it, tweak the skills, or add new ones. The Hacker News thread shows a few users asking whether the guardrails actually work in live markets, but the repo hasn’t seen a public backtest yet.

## What’s missing and what’s next

For now, ShurikenTrade only works with U.S. stocks via the Interactive Brokers API. It doesn’t handle options, crypto, or forex yet. The team hints at a roadmap that includes a “skill marketplace” where users can share and rate pre-built skills, but nothing is live. Anyone can open an issue on GitHub if they find a bug or want a new feature, and the repo is already set up for pull requests.

If you’re comfortable with Python and willing to read through the docs, you can spin up a demo in under an hour. The hardest part isn’t the code—it’s deciding which skills to trust the bot with. The repo warns that even with guardrails, the bot can still lose money if the market moves fast. The team recommends paper trading first and keeping position sizes small until you’re confident the skills behave.

The project is still tiny—just a few dozen commits and a handful of contributors—but the idea matches a growing push toward safer AI automation. Other open-source projects like AutoGen and CrewAI focus on multi-agent systems, but none have pushed guardrails as hard as ShurikenTrade does. Whether it catches on will depend on whether traders actually trust a bot that writes its own rulebook before it places a trade.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://github.com/ShurikenTrade/shuriken-skills)
- **Published:** May 17, 2026 at 12:44 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://github.com/ShurikenTrade/shuriken-skills)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Wanted: Digital chief for England's schools. Must enjoy data, AI, and concrete problems](/technology/2026/05/17/wanted-digital-chief-for-englands-schools-must-enjoy-data-ai-and-concrete-proble/)


---

## 🇧🇷 Resumo em Português

Em um cenário onde a inteligência artificial já domina desde recomendações de séries até diagnósticos médicos, agora ela invade o mercado financeiro com mais uma inovação: o ShurikenTrade, um robô de trading autônomo que promete reduzir riscos graças a “trilhos de segurança” implementados por guardrails. A ferramenta, que já chama atenção por ser open source e acumular 15 upvotes no Hacker News, surge como uma alternativa para investidores que buscam automatizar operações sem abrir mão do controle sobre suas estratégias.

O lançamento chega em um momento crucial para o Brasil, onde o interesse por investimentos digitais e ferramentas de IA cresce exponencialmente, especialmente após a popularização de corretoras online e a entrada de pequenos investidores no mercado de ações e criptomoedas. A relevância da ferramenta está justamente na promessa de mitigar perdas: ao contrário de outros bots que operam de forma opaca, o ShurikenTrade permite que os usuários definam limites claros para operações arriscadas, algo que pode atrair não só traders experientes, mas também aqueles que ainda engatinham no mundo dos investimentos automatizados.

Com isso, a comunidade de desenvolvedores e investidores brasileiros pode estar diante do primeiro passo para uma nova geração de robôs financeiros mais transparentes e seguros, abrindo caminho para uma adoção ainda maior de tecnologias de IA no mercado nacional.


---

## 🇪🇸 Resumen en Español

La inteligencia artificial da un paso adelante en los mercados financieros con un bot de trading autónomo que promete reducir riesgos. ShurikenTrade ha lanzado su herramienta de *agentic AI*, diseñada para operar en bolsa con salvaguardas que limitan las pérdidas y evitan decisiones impulsivas, una innovación que ya capta la atención de la comunidad tecnológica.

Este proyecto de código abierto, aunque aún en fase temprana con solo quince apoyos en Hacker News, refleja la creciente demanda de soluciones más seguras en un sector donde los errores de los algoritmos pueden costar millones. Para los inversores hispanohablantes, especialmente aquellos con perfil tecnológico, la propuesta de ShurikenTrade abre un debate sobre el equilibrio entre automatización y control, un tema clave en un mercado cada vez más dominado por la inteligencia artificial.
