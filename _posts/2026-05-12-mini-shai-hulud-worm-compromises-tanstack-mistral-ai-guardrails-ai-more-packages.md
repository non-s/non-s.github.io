---
layout: post
title: "Mini Shai-Hulud Worm Compromises TanStack, Mistral AI, Guardrails AI & More Packages"
date: 2026-05-12 11:46:00 +0000
categories: [security, ai]
tags: [hackernews, security, vulnerabilities, ai, mistral, mini-shai, hulud-worm-compromises, stack, guardrails, mini-shai-hulud-attack, teampcp-supply-chain-attack, npm-package-compromise, pypi-package-compromise, router-initjs-malware, open-source-security-breach, how-to-check-for-compromised-npm-packages, mistral-ai-security-breach, tanstack-query-malware]
author: "GlobalBR News"
description: "TeamPCP linked to attack that poisoned npm and PyPI packages for TanStack, UiPath, Mistral AI and others. Obfuscated JavaScript files profile systems before exf"
source_url: "https://thehackernews.com/2026/05/mini-shai-hulud-worm-compromises.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhXIhs2kZt0YGdDcd-Io67mq1GIN_iI_71LYhuin4qqmlgUgCuZ3fGUvglg_5nh5DK8kfPP8RHki86yMyqh4rTE27PGgPBh4RQjkh91-QGoB8cav5NUsYAwcV3ZJ7aEf-uEoH3pLGQ2eWuCh8lZSWAlTIa2U5I6eeB3HZmYMn4q-YoV7Ytmkpr1tN0lC2rG/s1600/mistral.jpg"
image_alt: "Mini Shai-Hulud Worm Compromises TanStack, Mistral AI, Guardrails AI & More Packages"
image_caption: "A stylized illustration of a sandworm emerging from a server rack, symbolizing the Mini Shai-Hulud supply-chain attack."
keywords: ["Mini Shai-Hulud attack", "TeamPCP supply-chain attack", "npm package compromise", "PyPI package compromise", "router_init.js malware", "open source security breach", "how to check for compromised npm packages", "mistral ai security breach"]
key_points:
  - "Threat actor TeamPCP ran the Mini Shai-Hulud supply-chain campaign."
  - "Five npm/PyPI packages were poisoned: TanStack, UiPath, Mistral AI, OpenSearch, Guardrails AI."
  - "Attackers included obfuscated JavaScript that profiles infected systems."
faq:
  - q: "What is the Mini Shai-Hulud campaign?"
    a: "Mini Shai-Hulud is a supply-chain attack by threat actor TeamPCP that poisons npm and PyPI packages with obfuscated JavaScript to profile and exfiltrate data from infected systems. It’s named after the giant sandworms in Frank Herbert’s Dune series due to its worm-like spreading behavior."
  - q: "Which packages were compromised in this attack?"
    a: "The compromised packages include TanStack Query, TanStack Table, UiPath automation tools, Mistral AI libraries, OpenSearch components, and Guardrails AI tools. All were modified to include a hidden router_init.js file that profiles systems."
  - q: "How does the malicious JavaScript work?"
    a: "The injected router_init.js file runs automatically when the package is installed. It collects basic system info like OS version and IP address, then sends the data to a remote server controlled by the attackers. The file is obfuscated to evade detection."
  - q: "Who is behind the Mini Shai-Hulud attacks?"
    a: "The threat actor TeamPCP is linked to these attacks. Security researchers have traced the campaign back to this group, which has a history of targeting open-source ecosystems with supply-chain attacks."
  - q: "How can I tell if my system is infected?"
    a: "Check your project’s node_modules folder for the router_init.js file and scan for unusual network connections to unknown domains. Update affected packages immediately and verify no unauthorized changes were made to your dependencies."
featured: true
breaking: true
hook: "A new sandworm-style attack is crawling through your open-source code right now."
tl_dr: "TeamPCP poisoned five npm/PyPI packages including TanStack and Mistral AI with obfuscated profiling code."
lead: "TeamPCP, a known threat actor, has poisoned npm and PyPI packages for TanStack, UiPath, Mistral AI, OpenSearch and Guardrails AI using a new Mini Shai-Hulud supply-chain campaign. The attackers added obfuscated JavaScript to profile victim machines before stealing data."
content_type: "news"
entities:
  - "TeamPCP"
  - "TanStack"
  - "Mistral AI"
  - "UiPath"
  - "OpenSearch"
  - "Guardrails AI"
---

A threat group called TeamPCP has launched a fresh supply-chain attack that compromised multiple widely used npm and PyPI packages, including ones owned by TanStack, [UiPath](https://en.wikipedia.org/wiki/UiPath), [Mistral AI](https://en.wikipedia.org/wiki/Mistral_AI), OpenSearch and Guardrails AI. The campaign, dubbed Mini Shai-Hulud after the giant sandworms in Frank Herbert’s Dune series, uses a new tactic: injecting obfuscated JavaScript files into legitimate packages to silently profile systems before exfiltrating data. Security researchers say the attackers have been active since at least March, but the latest wave shows an escalation in targeting major open-source libraries that developers rely on daily. The affected packages include popular front-end tools and AI frameworks, meaning the attack could spread far beyond the initial victims. At least one package maintainer confirmed the breach after noticing unauthorized commits to the project’s repository, but others remain unaware their packages have been weaponized. The incident underscores how supply-chain attacks keep evolving, hitting the software we trust without warning.

## How the attack works
The poisoned packages all contain a hidden file named router_init.js that’s disguised as normal utility code. When installed, the script runs automatically in the background and collects basic system information like the operating system, installed software versions, and local IP addresses. It then attempts to send this data to a remote server controlled by the attackers. What makes this attack stealthy is the obfuscation: the JavaScript is minified and encoded to bypass basic security scans, only revealing its true purpose after execution. Researchers at [Checkmarx](https://checkmarx.com) first spotted the campaign after detecting unusual network traffic from a customer’s development environment. They traced it back to the compromised packages and found the same obfuscation technique across multiple repositories. The attackers don’t just stop at data collection; in some cases, they’ve also added backdoors that could let them take control of a victim’s machine later. This isn’t the first time TeamPCP has targeted open-source ecosystems, but it’s the first time they’ve used a worm-like behavior to spread automatically.

## Who’s affected and what to do
Developers who installed any of the compromised packages in the last three months should treat their systems as potentially compromised. The affected packages include the popular TanStack Query, TanStack Table, and several Mistral AI libraries used for fine-tuning large language models. The attack isn’t limited to developers either; the poisoned packages can spread to end-user applications if the malicious code isn’t caught early. Companies using UiPath’s automation tools or OpenSearch’s data analytics platform might also be at risk, especially if they’ve integrated these tools into larger systems. The good news is that the obfuscated JavaScript is relatively easy to spot if you know where to look. Developers should check their project’s node_modules folder for the router_init.js file and scan for any unusual network connections to unknown domains. Maintainers of the affected packages have already started releasing clean versions, but users need to update immediately and verify their dependencies haven’t been tampered with. This isn’t just a technical issue; it’s a supply-chain problem that affects everyone who relies on open-source software.

## Why supply-chain attacks keep working
The success of campaigns like Mini Shai-Hulud shows how hard it is to secure the software supply chain. Attackers don’t need to hack a major corporation directly; they just need to slip malicious code into a package that thousands of developers trust. Even well-funded organizations like [Mistral AI](https://en.wikipedia.org/wiki/Mistral_AI) can’t always catch these breaches in time, especially when the attack uses obfuscation to hide its tracks. The problem is compounded by the fact that many developers don’t have the time or tools to audit every dependency in their projects. Some companies have started using software composition analysis tools to scan for suspicious changes, but these solutions aren’t foolproof. The open-source community is pushing for better security practices, like mandatory code reviews for critical packages and stricter signing requirements, but adoption is slow. Until those measures become standard, attacks like Mini Shai-Hulud will keep happening. The only real defense is constant vigilance: developers need to monitor their dependencies, maintainers must act fast when breaches are discovered, and end-users should demand transparency from the companies they rely on.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/mini-shai-hulud-worm-compromises.html)
- **Published:** May 12, 2026 at 11:46 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #mistral · #mini-shai

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/mini-shai-hulud-worm-compromises.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 12, 2026*


---

## 🇧🇷 Resumo em Português

**Um novo verme digital, disfarçado como uma versão reduzida da criatura lendária Shai-Hulud de *Duna*, está se infiltrando em bibliotecas de código essenciais usadas por gigantes da tecnologia brasileira.** Pesquisadores revelaram que o *Mini Shai-Hulud Worm* — um malware oculto em pacotes do npm e PyPI — já comprometeu bibliotecas como TanStack, Mistral AI, Guardrails AI e até UiPath, ferramenta amplamente adotada por empresas no Brasil para automação. A estratégia do ataque é tão sorrateira que o código malicioso se esconde dentro de arquivos JavaScript ofuscados, que coletam informações dos sistemas infectados antes de agir, como um verme que se alimenta silenciosamente dos dados alheios.

O Brasil, um dos maiores mercados de desenvolvimento de software da América Latina, está diretamente no radar desse tipo de ameaça. Bibliotecas como as da TanStack (usada em frameworks populares no país) e a integração com a Mistral AI — que tem crescido no mercado brasileiro de IA — tornam o ataque especialmente perigoso. Especialistas alertam que, com a popularização de ferramentas open source no ecossistema nacional, a exposição a riscos como esse só tende a aumentar, exigindo mais fiscalização e atualizações constantes por parte das empresas e desenvolvedores.

A próxima etapa agora é identificar todas as vítimas e mitigar os danos, enquanto a comunidade de segurança digital corre para conter a propagação desse verme digital antes que ele se espalhe ainda mais.
