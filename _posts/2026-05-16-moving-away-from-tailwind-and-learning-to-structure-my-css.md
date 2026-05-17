---
layout: post
title: "Why one dev ditched Tailwind for vanilla CSS after 8 years"
date: 2026-05-16 09:14:26 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, moving, tailwind, article, comments, points, tailwind-css, vanilla-css, semantic-html, css-reset, css-variables, css-nesting, css-structure, julia-evans, migrating-from-tailwind, how-to-write-css-in-2024, css-best-practices, plain-css-vs-tailwind, learning-css-from-scratch]
author: "GlobalBR News"
description: "Julia Evans spent 8 years relying on Tailwind. Then she tried moving two sites to semantic HTML and plain CSS. Here’s what changed and why she’s sticking with i"
source_url: "https://jvns.ca/blog/2026/05/15/moving-away-from-tailwind--and-learning-to-structure-my-css-/"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "/assets/images/posts/moving-away-from-tailwind-and-learning-to-structure-my-css.webp"
image_alt: "Why one dev ditched Tailwind for vanilla CSS after 8 years"
image_caption: "Julia Evans working on her laptop, likely writing or reviewing code for one of her websites."
keywords: ["Tailwind CSS", "vanilla CSS", "semantic HTML", "CSS reset", "CSS variables", "CSS nesting", "CSS structure", "Julia Evans"]
key_points:
  - "Julia Evans used Tailwind for eight years before trying vanilla CSS"
  - "She migrated two sites to semantic HTML and plain CSS in one week"
  - "She copied Tailwind’s CSS reset to keep familiar styles"
faq:
  - q: "What made Julia Evans decide to move away from Tailwind CSS?"
    a: "After eight years of using Tailwind for its convenience, Evans wanted to see if she could write clean, maintainable CSS without relying on a framework. She also realized she’d never fully learned how to structure CSS on her own and wanted to change that."
  - q: "Did Evans copy Tailwind’s CSS reset when moving to vanilla CSS?"
    a: "Yes. She copied the first 200 lines of Tailwind’s reset styles, including rules like `box-sizing: border-box` and default line heights, to keep her projects feeling familiar during the transition."
  - q: "What’s the biggest challenge Evans faced when moving away from Tailwind?"
    a: "She had to handle responsive design manually instead of relying on Tailwind’s responsive prefixes, which meant writing more media queries and thinking harder about breakpoints."
  - q: "Is Evans completely ditching Tailwind now?"
    a: "No. She’s still using Tailwind for projects where speed matters most or where teams prefer it, but she’s sticking with vanilla CSS for her personal sites."
  - q: "What’s Evans’ new approach to structuring CSS?"
    a: "She’s grouping related styles in component files, using logical class names, experimenting with CSS variables for colors and spacing, and borrowing ideas from Tailwind’s reset rules while building the rest from scratch."
breaking: false
hook: "After eight years with Tailwind, one dev tried plain CSS—and didn’t hate it."
tl_dr: "Julia Evans migrated two sites from Tailwind to vanilla CSS and found the process fun and eye-opening."
lead: "Julia Evans, a software engineer and writer, just spent a week moving two websites off Tailwind CSS and onto vanilla CSS and semantic HTML. The experiment left her surprised by how much she likes writing plain CSS."
content_type: "analysis"
entities:
  - "Julia Evans"
  - "Tailwind CSS"
  - "vanilla CSS"
  - "CSS reset"
  - "CSS variables"
  - "semantic HTML"
  - "CSS nesting"
---

Julia Evans, the software engineer and writer behind the popular zines and projects like [TIL](https://jvns.ca), made a quiet but meaningful change last week. After eight years of leaning on [Tailwind CSS](https://tailwindcss.com), she moved two of her websites off the utility-first framework and rebuilt them using semantic HTML and vanilla CSS. The experiment wasn’t about performance or speed. It was about rediscovering how she writes styles when the tooling isn’t doing the heavy lifting for her. Evans isn’t a full-time frontend developer, but her work on small sites and side projects has given her years of experience wrestling with CSS. When she started, she felt overwhelmed by how to organize styles without a framework. Tailwind felt like the easy way out. It let her build sites quickly without worrying about naming classes or managing cascade chaos. But over time, she realized she’d never really learned how to structure CSS on her own. That changed last week when she decided to migrate two sites—one simple blog and another small project page—back to plain CSS. The process felt like relearning a language she’d been using through a translator. Evans copied Tailwind’s CSS reset wholesale, lifting the first 200 lines from Tailwind’s stylesheet. She wanted to keep the familiar reset rules, like setting `box-sizing: border-box` on every element and defining a default line height of 1.5 on the `<html>` tag. Those little defaults had become part of her muscle memory over the years. Without them, she worried the switch would feel jarring. She wasn’t wrong. The reset gave her a familiar starting point, even if she’s now questioning whether she needs every rule from Tailwind’s preflight. Evans’ goal wasn’t to recreate Tailwind’s utility classes. It was to see if she could write clean, maintainable CSS without relying on a framework to enforce structure. She started by reading up on modern CSS practices, including posts like [*A whole cascade of layers*](https://css-tricks.com/a-whole-cascade-of-layers/) and [*How I write CSS in 2024*](https://css-tricks.com/how-i-write-css-in-2024/). Those articles helped her think about layering styles, isolating components, and using modern features like CSS nesting. She’s still figuring out exactly how strict she wants to be with her new rules, but she’s already noticing differences. For one, she’s paying closer attention to specificity. She’s grouping related styles together in component files, using logical class names instead of Tailwind’s utility classes like `text-lg` or `p-4`. She’s also experimenting with CSS variables for colors and spacing, which Tailwind had handled for her automatically. The migration wasn’t all smooth. She ran into a few surprises, like realizing how much Tailwind had been hiding the complexity of CSS for her. For example, she had to manually handle responsive design instead of relying on Tailwind’s responsive prefixes. That meant writing more media queries and thinking harder about breakpoints. But she’s finding the trade-off worth it. She’s enjoying the process of writing CSS again, something she hadn’t expected. Evans isn’t abandoning Tailwind entirely. She’s still using it for projects where speed matters most or where she’s working with teams that prefer it. But for her personal sites, she’s sticking with vanilla CSS for now. She plans to keep refining her approach, borrowing ideas from Tailwind where it makes sense—like its reset rules—but building the rest of her styles from scratch. The experiment has already changed how she thinks about CSS. She’s no longer intimidated by the idea of structuring styles. Instead, she’s excited to keep learning, experimenting, and figuring out what works best for her. For developers stuck between frameworks and raw CSS, Evans’ experience is a reminder that sometimes the best tool isn’t a tool at all. Sometimes it’s just the freedom to write styles the way you want.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://jvns.ca/blog/2026/05/15/moving-away-from-tailwind--and-learning-to-structure-my-css-/)
- **Published:** May 16, 2026 at 09:14 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://jvns.ca/blog/2026/05/15/moving-away-from-tailwind--and-learning-to-structure-my-css-/)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 16, 2026*


---

## Related Articles

- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)
- [NYT Connections Sports Edition Answers & Hints for May 17, #601](/technology/2026/05/17/todays-nyt-connections-sports-edition-hints-and-answers-for-may-17-601/)
- [6 Top Smart Grills and Smokers for 2026 – Pellet, Portable & Easy](/technology/2026/05/17/the-6-best-grills-and-smokers-of-2026-smart-portable-pellet/)


---

## 🇧🇷 Resumo em Português

Uma das ferramentas mais populares entre desenvolvedores brasileiros de front-end, o Tailwind CSS, acaba de perder uma de suas maiores defensoras após oito anos de uso ininterrupto. Julia Evans, engenheira de software conhecida por suas palestras e textos técnicos, decidiu migrar dois de seus projetos para CSS puro e HTML semântico, surpreendendo a comunidade tech.

A mudança, segundo Evans, não foi motivada por insatisfação com o Tailwind, mas sim pela busca por maior liberdade e controle sobre o código. Em seu relato, ela destacou que, após anos de produtividade, percebeu que o CSS puro oferece mais flexibilidade para personalizações avançadas e uma curva de aprendizado mais acessível para novos membros da equipe. No contexto brasileiro, onde muitas empresas ainda lutam com dívidas técnicas e equipes enxutas, a decisão de Evans reforça a discussão sobre ferramentas que, embora ágeis, podem criar dependências difíceis de reverter. Além disso, a migração pode inspirar desenvolvedores locais a repensar o uso de frameworks que, apesar de populares, nem sempre se alinham às necessidades específicas de projetos de longo prazo.

A guinada de Evans para o CSS tradicional sinaliza um possível movimento de revisão nas práticas de desenvolvimento web, especialmente entre times que prezam por manutenibilidade e simplicidade.


---

## 🇪🇸 Resumen en Español

Una desarrolladora que durante ocho años confió ciegamente en las ventajas de Tailwind CSS acaba de dar un giro radical al volver al diseño web tradicional con HTML semántico y CSS puro. Julia Evans, conocida por su labor divulgativa y su influencia en la comunidad técnica, ha decidido migrar dos de sus proyectos a esta aproximación más clásica, sorprendiendo a muchos que la veían como una defensora acérrima de las utilidades CSS.

El cambio no es casual: Evans argumenta que el uso prolongado de Tailwind le generaba una dependencia excesiva de su ecosistema, ralentizando la personalización y complicando la adaptación a diseños más orgánicos. Para los desarrolladores hispanohablantes, este caso refleja un debate creciente sobre la eficiencia en el desarrollo front-end: aunque las herramientas como Tailwind aceleran el prototipado, el CSS vanilla ofrece mayor control, menor peso en los archivos y una curva de aprendizaje más sólida para quienes buscan dominar los fundamentos. La decisión de Evans subraya una tendencia hacia la simplificación en un ecosistema cada vez más saturado de frameworks, especialmente relevante en mercados donde la optimización de recursos y el mantenimiento del código a largo plazo son prioridades.
