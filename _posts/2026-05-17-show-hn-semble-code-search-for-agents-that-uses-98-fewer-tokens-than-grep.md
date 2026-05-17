---
layout: post
title: "Show HN: Semble – Code search for agents that uses 98% fewer tokens than grep"
date: 2026-05-17 15:37:07 +0000
categories: [technology, ai]
tags: [hackernews, programming, tech, ai, anthropic, claude, show, semble, code, stephan, thomas, semble-code-search, ai-code-search-tool, grep-alternative-for-developers, static-embeddings-for-code-search, cpu-based-code-search-tool, open-source-code-search, model2vec-embeddings, bm25-code-search, ai-coding-agents-token-usage, grep-vs-semble-token-comparison]
author: "GlobalBR News"
description: "Semble uses Model2Vec embeddings and BM25 to search code with 98% fewer tokens than grep. No API keys needed and runs on CPU. Open-source now."
source_url: "https://github.com/MinishLab/semble"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "https://opengraph.githubassets.com/4a00c017322d8a53a2169c3cf24416246f18d054ba026b8c07598d89541da254/MinishLab/semble"
image_alt: "Show HN: Semble – Code search for agents that uses 98% fewer tokens than grep"
image_caption: "Semble’s interface showing a code search result with highlighted matches and token usage comparison to grep."
keywords: ["Semble code search", "AI code search tool", "grep alternative for developers", "static embeddings for code search", "CPU-based code search tool", "open-source code search", "Model2Vec embeddings", "BM25 code search"]
key_points:
  - "Semble cuts token use by 98% versus grep for code search"
  - "Uses static Model2Vec embeddings and BM25 with RRF fusion"
  - "Runs entirely on CPU with no transformers required"
faq:
  - q: "What exactly is Semble and who built it?"
    a: "Semble is an open-source code search tool built by Stephan and Thomas to help AI coding agents find relevant code without burning tokens. It combines static embeddings with BM25 and runs entirely on CPU."
  - q: "How does Semble cut token usage by 98% compared to grep?"
    a: "Semble uses static Model2Vec embeddings and BM25 instead of reading full files like grep. It indexes just enough to find matches without loading entire files, so the AI model sees far fewer tokens."
  - q: "Does Semble work with any programming language?"
    a: "Yes. The tool supports 19 languages in its benchmark, including Python, JavaScript, Go, Rust, and Java. The developers plan to add more based on user feedback."
  - q: "Do I need GPUs to run Semble?"
    a: "No. Semble runs entirely on CPU, so you don’t need GPUs or cloud services. The static embeddings precompute quickly, and the search happens locally."
  - q: "Where can I download Semble and how do I set it up?"
    a: "You can find the code on GitHub under an MIT license. The setup involves cloning the repo, installing dependencies, and indexing your codebase. The developers provide a quick-start guide in the README."
breaking: false
hook: "If your AI agent’s code search is burning tokens like crazy, meet Semble."
tl_dr: "Semble cuts token usage by 98% versus grep for code search while keeping accuracy high."
lead: "Two developers just open-sourced Semble, a code search tool that uses 98% fewer tokens than grep while finding relevant code faster. It combines static embeddings with BM25 and runs entirely on CPU."
content_type: "news"
entities:
  - "Stephan"
  - "Thomas"
  - "Semble"
  - "Claude Code"
  - "potion-code-16M"
---

Two engineers open-sourced Semble this week, a code search tool designed to solve a persistent problem for AI coding agents. Stephan and Thomas built it after repeatedly hitting the same issue with [Claude Code](https://github.com/anthropics/claude-code): when agents can’t locate code directly, they fall back to grep, which eats up tokens and often misses the right files. Existing tools either indexed too slowly, required API keys, or gave poor results. Semble fixes that by combining two search methods—static embeddings from their potion-code-16M model and BM25—then merging them with reciprocal rank fusion and reranking with code-aware signals. The whole system runs on CPU, so no GPUs or cloud APIs are needed. On their benchmark of 1,250 query/document pairs across 63 repositories and 19 programming languages, Semble matched grep’s accuracy while using 98% fewer tokens. That matters because tokens equal cost in most AI workflows. Every extra token a model reads adds up fast when you’re searching through large codebases. Semble’s approach keeps the search light but effective by avoiding transformer models entirely. Instead, it relies on static embeddings precomputed for each repository, which are quick to generate and update. The BM25 layer handles keyword matching, while the reranker uses code-specific signals like syntax structure and file paths to prioritize relevant results. The tool is open-source under the MIT license. Anyone can clone it, index their own codebase, and start searching. The developers say it’s already saving them time in their own workflows with Claude Code. They tested it against traditional grep runs and found Semble consistently surfaced the right files with far fewer tokens consumed. The benchmark covered a mix of popular languages including Python, JavaScript, Go, Rust, and Java. Accuracy stayed high even when queries were vague or used different terminology than the actual code. ## Why grep is becoming a bottleneck for AI agents Grep works fine when you know exactly what you’re looking for. But AI agents often need to explore unfamiliar codebases, where exact matches don’t exist. Every character in a file grep reads gets fed to the model as a token, and tokens aren’t cheap. Multiply that by thousands of files in a large repo, and the cost adds up. Companies building AI coding tools have been trying to solve this for years. Some tools use vector databases that need GPUs and can’t index on the fly. Others require API keys or cloud services, adding latency and cost. None matched Semble’s combination of accuracy, speed, and low resource use. The static embeddings mean the index builds in minutes, not hours. No cloud dependencies means it works offline. And CPU-only operation keeps hardware costs down. ## How Semble stacks up against other tools The team compared Semble to three common alternatives: plain grep, a full-text search tool like ripgrep, and a vector search tool using embeddings. On their benchmark, grep returned results quickly but often missed relevant files. Ripgrep was faster at finding text but still loaded too many tokens. Vector search tools gave better results but needed GPUs and took longer to index. Semble split the difference. It returned results in under a second on most queries, used almost no GPU resources, and maintained high recall. The developers admit there’s still work to do. Right now, Semble works best on code it’s seen before—new files in a repo need a fresh index. The 1,250-pair benchmark is solid but not huge. They’re planning to expand testing to more languages and edge cases. Still, for engineers tired of watching their AI agents burn tokens on grep fallbacks, it’s a practical fix. ## What’s next for Semble The code is on GitHub now, and the developers are asking for feedback. They’re particularly interested in hearing from teams using it in production, especially those with large monorepos or polyglot stacks. They also plan to add support for more languages and explore ways to make indexing even faster. The bigger picture is that AI coding tools are getting smarter, but most still rely on brute-force search when they should be smarter about it. Semble shows one path forward: lean on lightweight embeddings and fusion techniques to keep searches fast and cheap. No magic, just good engineering.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://github.com/MinishLab/semble)
- **Published:** May 17, 2026 at 15:37 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #anthropic · #claude

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://github.com/MinishLab/semble)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [XS 1.2.26: A single binary that runs anywhere, no runtime needed](/technology/2026/05/17/xs-a-programming-language-anywhere-anytime-by-anyone/)
- [Sam Altman’s trust on trial as Elon Musk sues OpenAI](/technology/2026/05/17/why-trust-is-a-big-question-at-the-elon-musk-openai-trial/)
- [OpenClaw’s new security steps for safer AI assistants explained](/technology/2026/05/17/where-openclaw-security-is-heading/)


---

## 🇧🇷 Resumo em Português

O Brasil, que impulsiona a inovação tecnológica na América Latina, acaba de ganhar uma ferramenta revolucionária para desenvolvedores: o Semble, um mecanismo de busca de código que promete reduzir em 98% o uso de *tokens* em comparação ao tradicional *grep*, sem depender de APIs ou de poderosos GPUs.

Desenvolvido com base em *embeddings* da Model2Vec e no algoritmo BM25, o Semble se destaca por ser open-source, executável em CPU e livre de chaves de acesso, o que o torna acessível mesmo para pequenas equipes e startups brasileiras. No contexto nacional, onde a otimização de recursos é crucial devido à alta demanda por soluções escaláveis e de baixo custo, essa ferramenta chega como uma alternativa promissora para agilizar a revisão e manutenção de grandes bases de código, especialmente em ambientes com limitações de infraestrutura.

A expectativa é que, com sua adoção, o Brasil dê mais um passo rumo à eficiência na programação, enquanto a comunidade de desenvolvedores brasileiros contribui ativamente para o aprimoramento da ferramenta.


---

## 🇪🇸 Resumen en Español

Semble llega para revolucionar el modo en que los desarrolladores buscan código en sus proyectos, ofreciendo una alternativa hasta un 98% más eficiente en consumo de tokens que herramientas tradicionales como grep. Esta innovación, basada en embeddings de Model2Vec y el algoritmo BM25, promete agilizar la productividad sin depender de claves de API y operando únicamente con CPU, lo que la hace accesible incluso para equipos con recursos limitados.

La relevancia de Semble radica en su capacidad para procesar búsquedas semánticas en código fuente, entendiendo el contexto y no solo coincidencias literales de texto. Para los desarrolladores hispanohablantes, esto significa una herramienta más intuitiva y económica, especialmente útil en entornos donde el hardware o la conectividad pueden ser un obstáculo. Además, su naturaleza de código abierto fomenta la colaboración global y la adaptación a necesidades específicas, democratizando el acceso a tecnologías avanzadas de búsqueda de software.
