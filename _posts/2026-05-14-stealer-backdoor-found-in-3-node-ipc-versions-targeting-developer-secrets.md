---
layout: post
title: "Malicious backdoor found in 3 versions of npm package node-ipc"
date: 2026-05-14 17:22:43 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, cybersecurity, stealer-backdoor-found, node, versions-targeting-developer, secrets-cybersecurity, socket, node-ipc-backdoor, npm-package-security, node-ipc-malicious-versions, supply-chain-attack-npm, developer-secrets-theft, npm-registry-security, open-source-security-risks, remove-node-ipc-916-923-1201]
author: "GlobalBR News"
description: "Security firms confirm malicious backdoor in node-ipc npm packages 9.1.6, 9.2.3, and 12.0.1. Attackers steal developer secrets via npm registry. Here's what you"
source_url: "https://thehackernews.com/2026/05/stealer-backdoor-found-in-3-node-ipc.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhTj2m9-HHmDEDzKIsalsJ_HJcwcUsIFajvcpTLP9QMyqS9F_JroTH7lXeOGZFuO6j6F-RzbIo1kBIQ0udSFQGzjN2hxO8ZfyFeHM5557BPI1sjiJ7cEMJJE62t11e07Wt1CsmAntpLHSM0XbnQDvVYNBfNdAOsob9kN6G6-mQjKX68fEE1nzy_Bn4TvxyK/s1600/node.jpg"
image_alt: "Malicious backdoor found in 3 versions of npm package node-ipc"
image_caption: "A laptop screen showing npm registry warnings about malicious node-ipc packages, with code snippets of the backdoor in t"
keywords: ["node-ipc backdoor", "npm package security", "node-ipc malicious versions", "supply chain attack npm", "developer secrets theft", "npm registry security", "open source security risks", "remove node-ipc 9.1.6 9.2.3 12.0.1"]
key_points:
  - "Remove node-ipc versions 9.1.6, 9.2.3, and 12.0.1 now"
  - "Backdoor steals developer secrets via npm registry"
  - "Security firms Socket and StepSecurity confirmed attacks"
faq:
  - q: "What is node-ipc and why do developers use it?"
    a: "Node-ipc is a Node.js package that enables inter-process communication between different parts of an application. It’s commonly used for local and remote communication between services, especially in microservices architectures. Developers rely on it because it simplifies communication without requiring complex setup."
  - q: "How does the node-ipc backdoor steal secrets?"
    a: "The backdoor in node-ipc versions 9.1.6, 9.2.3, and 12.0.1 was designed to scan a developer’s system for sensitive files like environment variables, SSH keys, and configuration files. It then sends these files to a remote server controlled by the attacker, potentially exposing passwords, API keys, and other credentials."
  - q: "Which versions of node-ipc are affected by the backdoor?"
    a: "The malicious backdoor was found in node-ipc versions 9.1.6, 9.2.3, and 12.0.1. These versions were published to the npm registry between February and April 2022 and have since been yanked. Any projects using these versions should be treated as compromised."
  - q: "What should developers do if they used a compromised node-ipc version?"
    a: "Developers who installed any of the three compromised versions should immediately check their systems for signs of compromise. Rotate all exposed secrets, including API keys, passwords, and SSH keys. Audit your dependency tree to ensure no other packages depend on the compromised versions."
  - q: "Is this the first time node-ipc has had security issues?"
    a: "No, node-ipc has a history of controversy. In early 2022, its maintainer added a controversial feature allowing remote kill switch functionality, which was later removed after public backlash. This recent backdoor incident has further damaged trust in the package."
featured: true
breaking: true
hook: "Three popular npm packages are stealing developer secrets right now."
tl_dr: "Remove node-ipc versions 9.1.6, 9.2.3, and 12.0.1 immediately to prevent secret theft."
lead: "Three malicious versions of the popular npm package node-ipc were found stealing developer secrets. Security firms Socket and StepSecurity confirmed attacks through versions 9.1.6, 9.2.3, and 12.0.1. The packages were quietly altered to include a backdoor."
content_type: "breaking"
entities:
  - "Socket"
  - "StepSecurity"
  - "RIAEvangelist"
  - "npm registry"
  - "SolarWinds cyberattacks"
---

Cybersecurity researchers at [Socket](https://en.wikipedia.org/wiki/Socket_(computing)) and [StepSecurity](https://en.wikipedia.org/wiki/Step_Management) confirmed three corrupted versions of the node-ipc npm package are actively stealing developer secrets. The malicious code was found in versions 9.1.6, 9.2.3, and 12.0.1 of node-ipc, a widely used inter-process communication library for Node.js applications. These versions were published to the npm registry between February 1 and April 22, 2022, but the tampering went unnoticed until April 2022, when Socket’s security team flagged the issue. StepSecurity later verified the findings independently. The backdoor was designed to exfiltrate sensitive files from a developer’s system, including environment variables, SSH keys, and configuration files, sending them to a remote server controlled by the attacker. So far, there’s no public evidence of widespread exploitation, but security experts warn that even a single compromised developer could expose entire organizations to supply chain attacks. The npm registry has since yanked the malicious versions, but the incident raises fresh concerns about the security of open-source software dependencies. The attack follows a similar trend of supply chain compromises, where attackers target widely used libraries to reach a broad victim base. In 2021, the infamous [SolarWinds hack](https://en.wikipedia.org/wiki/SolarWinds_cyberattacks) used a similar approach, infiltrating thousands of organizations through a single compromised software update. Unlike that attack, which required sophisticated nation-state resources, this node-ipc incident appears to have been executed by less-skilled threat actors, suggesting the barrier to entry for supply chain attacks is dropping. Developers who installed any of the three compromised versions should immediately audit their systems for signs of compromise and rotate all exposed secrets, including API keys, passwords, and SSH keys. The npm registry’s security team has published guidance on detecting and removing the malicious code, but the cleanup process could take weeks for organizations with large codebases. This isn’t the first time node-ipc has been in the spotlight. In early 2022, the package’s maintainer, [RIAEvangelist](https://en.wikipedia.org/wiki/Richard_Spencer_(programmer)), faced backlash for including a controversial feature in node-ipc that allowed the package to act as a remote kill switch for systems running it. That feature was later removed after public outcry, but the recent backdoor incident has reignited debates about the trustworthiness of open-source maintainers and the reliability of npm packages. The node-ipc incident also highlights the risks of transitive dependencies. Many projects rely on node-ipc indirectly through other packages, meaning developers might be using the compromised versions without realizing it. Tools like [Socket](https://socket.dev) and [Dependabot](https://github.com/dependabot) can help detect vulnerable dependencies, but they’re not foolproof. The npm registry has yet to comment publicly on whether it will implement stricter vetting for package updates, but the incident is likely to accelerate calls for better security practices in the open-source ecosystem. For now, developers should treat this as a reminder to audit their dependency trees regularly and avoid running untrusted code. The npm registry’s immediate response—yanking the malicious versions—is a step in the right direction, but the broader issue of supply chain security remains unresolved.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/stealer-backdoor-found-in-3-node-ipc.html)
- **Published:** May 14, 2026 at 17:22 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #cybersecurity · #stealer-backdoor-found · #node

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/stealer-backdoor-found-in-3-node-ipc.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 14, 2026*


---

## 🇧🇷 Resumo em Português

Um golpe silencioso masletalmente eficiente atingiu o coração da programação brasileira: hackers esconderam uma porta dos fundos em três versões populares de uma biblioteca JavaScript usada por milhares de desenvolvedores no país. A descoberta de uma backdoor maliciosa nos pacotes *node-ipc* (versões 9.1.6, 9.2.3 e 12.0.1) expôs como invasores podem roubar segredos de profissionais e empresas apenas explorando vulnerabilidades em ferramentas de código aberto amplamente disseminadas no ecossistema de desenvolvimento nacional.

O incidente coloca em xeque a confiança em repositórios como o *npm*, onde milhares de desenvolvedores brasileiros buscam soluções rápidas para seus projetos — desde startups até grandes corporações. A backdoor, que se ativava em circunstâncias específicas, permitia o vazamento de dados sensíveis, como chaves de API ou credenciais, diretamente para servidores controlados pelos atacantes. Especialistas alertam que o Brasil, um dos maiores mercados de TI da América Latina, é especialmente vulnerável a esse tipo de ataque, dada a dependência de ferramentas estrangeiras e a falta de fiscalização rigorosa sobre pacotes de terceiros.

A situação exige ação imediata: desenvolvedores brasileiros devem verificar suas dependências e migrar para versões seguras do *node-ipc*, enquanto órgãos reguladores e empresas precisam reforçar suas políticas de segurança para evitar que novos pacotes infectados se espalhem.
