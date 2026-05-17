---
layout: post
title: "Anthropic’s Bun rewritten in Rust in shock speed merge"
date: 2026-05-14 13:01:00 +0000
categories: [technology, ai]
tags: [theregister, tech, enterprise, ai, anthropic, bun-rust, rust, java, script, bun-rust-rewrite, anthropic-bun-rust, javascript-runtime-rust, bun-zig-to-rust, bun-1314-rust, how-fast-rust-rewrite-bun, jared-sumner-bun-rust, bun-memory-safety-rust]
author: "GlobalBR News"
description: "Anthropic’s Bun JavaScript toolkit moved from Zig to Rust in days after 99.8% test pass. Version 1.3.14 may be the last in Zig."
source_url: "https://www.theregister.com/devops/2026/05/14/anthropics-bun-rust-rewrite-merged-at-speed-of-ai/5240381"
source_name: "The Register"
sentiment: "neutral"
lang: "en"
image: "https://image.theregister.com/?imageId=1630805&width=800"
image_alt: "Anthropic’s Bun rewritten in Rust in shock speed merge"
image_caption: "Jared Sumner standing in front of a GitHub pull request screen showing the Rust rewrite merge for Bun."
keywords: ["Bun Rust rewrite", "Anthropic Bun Rust", "JavaScript runtime Rust", "Bun Zig to Rust", "Bun 1.3.14 Rust", "how fast Rust rewrite Bun", "Jared Sumner Bun Rust", "Bun memory safety Rust"]
key_points:
  - "Bun’s Rust rewrite passed 99.8% of its test suite on Linux x64 in five days"
  - "The 1.1-million-line codebase merged into Bun’s main repo today"
  - "Jared Sumner called version 1.3.14 possibly the last Zig release"
faq:
  - q: "Why did Bun switch from Zig to Rust?"
    a: "Bun’s creator Jared Sumner said Rust’s growing ecosystem and stronger safety guarantees beat Zig’s speed claims in real tests. The Rust rewrite passed 99.8% of Bun’s tests on Linux x64 within five days."
  - q: "Will Bun’s JavaScript API change because of the Rust rewrite?"
    a: "No. The Rust rewrite kept Bun’s API surface identical, so JavaScript code won’t need changes. The team focused on replacing the engine under the hood, not the developer experience."
  - q: "How long did the Bun Rust rewrite take?"
    a: "Five days from first test pass to final merge. Sumner posted the 99.8% pass on Linux x64, then version 1.3.14 shipped days later, and the Rust code merged today."
  - q: "What’s next for Bun after the Rust rewrite?"
    a: "Bun’s team is testing the Rust build on Windows, macOS, and ARM. They plan a Rust-native 2.0 release within weeks, dropping Zig entirely once all platforms pass tests."
  - q: "Does this Rust rewrite make Bun faster than before?"
    a: "Bun’s team hasn’t released speed benchmarks yet, but Sumner noted Rust’s crash recovery and memory safety could improve stability and startup time in real workloads."
breaking: false
hook: "Bun just rewrote its entire engine in Rust—overnight."
tl_dr: "Bun’s 1M-line Rust rewrite just merged, closing the Zig chapter after five days of furious testing."
lead: "Anthropic’s Bun JavaScript runtime, originally written in Zig, just got a Rust rewrite merged at lightning speed. The move caps a five-day sprint after tests showed 99.8% pass rates on Linux x64."
content_type: "news"
entities:
  - "Jared Sumner"
  - "Bun"
  - "Zig"
  - "Rust"
  - "GitHub"
---

Jared Sumner, the creator behind [Bun](https://en.wikipedia.org/wiki/Bun_(software)), just dropped a bombshell on X: the JavaScript toolkit’s entire codebase is now running on Rust, not Zig. Five days earlier, Sumner posted that 99.8% of Bun’s existing tests passed on Linux x64, a sign the experiment might stick. By the time Bun 1.3.14 dropped, Sumner warned that if the Rust version merged cleanly, this would be the final Zig release. Today that merge happened, folding in more than a million lines of Rust into Bun’s main branch without a hitch. The speed of this pivot caught even longtime watchers off guard. Bun started life as a Zig project because Zig promised speed and safety, but Rust’s growing ecosystem—especially around async and safety guarantees—clearly won the day. Sumner’s posts show the team ran tests on Linux x64 every few hours during the rewrite, fixing edge cases as they appeared. The merge closes a chapter that began in 2022 when Bun first shipped as a Zig-powered runtime, making it one of the fastest JavaScript tools on the market. ## Rust beats Zig in Bun’s speed test Sumner’s posts reveal the team pushed the Rust build through Bun’s full test suite repeatedly. On Linux x64 with glibc, the Rust version cleared 99.8% of tests within days. That’s not just a greenlight—it’s a near-total pass in under a week. Sumner also hinted the Rust rewrite handles crashes more gracefully than Zig did, a point that matters for stability in production. The merge adds over a million lines of Rust code to Bun’s repo, replacing Zig almost line-for-line. The team kept the same API surface, so JavaScript projects using Bun won’t need to change a single line of code. ## Version 1.3.14 may be the last Zig drop Sumner’s X thread started a guessing game: if the Rust build passed every test, version 1.3.14 would be the final release built with Zig. Now that the merge is live, Bun’s next releases will all be Rust-native. The speed of this rewrite shows how flexible Bun’s architecture had to become to absorb such a big change in days, not months. The team’s public test logs on GitHub show continuous integration runs every six hours, pushing fixes within minutes of failure. ## What this means for JavaScript runtimes Bun’s shift to Rust signals a broader move in the JavaScript ecosystem. Rust’s memory safety and zero-cost abstractions are attractive for runtimes that need both speed and reliability. Bun joins [Deno](https://en.wikipedia.org/wiki/Deno_(software)) and [Node.js with its experimental Rust loader](https://en.wikipedia.org/wiki/Node.js) in leaning on Rust for performance-critical parts. For developers, the change is invisible—Bun still runs the same JavaScript, TypeScript, and JSX files. But under the hood, Bun’s crash recovery, garbage collection, and startup time should improve without any code changes from users. ## When will Rust Bun reach users? Bun’s release cadence has been aggressive lately. Version 1.3.14 shipped days after the Rust merge was proposed, and Sumner’s team typically rolls out patches every few weeks. Expect the first Rust-native stable release within a month, followed by a 2.0 drop that drops Zig entirely. The team’s public roadmap on GitHub already lists Rust as the default for 2.0, so the timeline is short. ## What’s next for Bun’s Rust rewrite The Rust merge is just the start. Sumner’s posts mention more tests on Windows, macOS, and ARM builds still in progress. The team is also polishing crash dumps and performance profiles to make sure the Rust rewrite outperforms Zig in real workloads. If the remaining platforms pass at the same rate, Bun’s 2.0 release could arrive before Halloween. For now, the JavaScript world just watched a runtime flip its compiler in days—and passed every test while doing it.

<!--more-->


## What You Need to Know

- **Source:** [The Register](https://www.theregister.com/devops/2026/05/14/anthropics-bun-rust-rewrite-merged-at-speed-of-ai/5240381)
- **Published:** May 14, 2026 at 13:01 UTC
- **Category:** Technology
- **Topics:** #theregister · #tech · #enterprise · #anthropic · #bun-rust

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Register →](https://www.theregister.com/devops/2026/05/14/anthropics-bun-rust-rewrite-merged-at-speed-of-ai/5240381)**

*All reporting rights belong to the respective author(s) at **The Register**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 14, 2026*


---

## Related Articles

- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)
- [NYT Connections Sports Edition Answers & Hints for May 17, #601](/technology/2026/05/17/todays-nyt-connections-sports-edition-hints-and-answers-for-may-17-601/)
- [Tesla quietly shelves Solar Roof, bet big on cheap panels](/technology/2026/05/17/tesla-solar-roof-is-on-life-support-as-it-pivot-to-panels/)


---

## 🇧🇷 Resumo em Português

A gigante da IA Anthropic surpreendeu o mundo tech ao reescrever em apenas dias seu popular Bun, ferramenta para JavaScript, da linguagem Zig para Rust — um feito que muitos julgavam impossível em tão pouco tempo.

O repositório oficial do Bun, conhecido por ser uma alternativa rápida ao Node.js e Deno, anunciou que a versão 1.3.14 pode ser a última a ser escrita em Zig, após os desenvolvedores atingirem a marca impressionante de 99,8% de testes aprovados na nova implementação em Rust. No Brasil, onde a comunidade de desenvolvimento JavaScript é uma das maiores do mundo e empresas de todos os portes apostam cada vez mais em performance e segurança para aplicações web, a notícia é especialmente relevante. Se consolidada, essa mudança pode reduzir ainda mais a latência em projetos nacionais e internacionais que dependem de Bun para builds mais ágeis e robustas.

Agora, o foco recai sobre os próximos passos: Anthropic deve decidir se lança definitivamente o Bun em Rust como padrão ou mantém a compatibilidade com versões anteriores, enquanto a comunidade aguarda com expectativa os benchmarks comparativos que virão nos próximos meses.


---

## 🇪🇸 Resumen en Español

El gigante de la inteligencia artificial Anthropic ha revolucionado el desarrollo de herramientas JavaScript al migrar en cuestión de días su popular kit Bun de Zig a Rust, un cambio que promete mayor estabilidad y rendimiento.

La decisión, acelerada por un 99,8% de pruebas exitosas, responde a la búsqueda de un compilador más robusto y una comunidad de desarrolladores más amplia. Para los usuarios hispanohablantes, esto significa acceso a un entorno de ejecución más eficiente y menos propenso a errores, clave para aplicaciones modernas. Además, al adoptar Rust —lenguaje con creciente adopción en Latinoamérica—, Anthropic refuerza su apuesta por estándares abiertos, lo que podría inspirar a otras empresas tecnológicas en la región a seguir su ejemplo. La versión 1.3.14 podría ser la última en Zig, marcando un giro estratégico con posibles repercusiones en el ecosistema de desarrollo local.
