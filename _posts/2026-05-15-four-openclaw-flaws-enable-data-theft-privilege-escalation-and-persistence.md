---
layout: post
title: "4 OpenClaw Flaws Let Hackers Steal Data, Hijack Systems"
date: 2026-05-15 13:35:04 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, cybersecurity, four-open, claw-flaws-enable, data-theft, privilege-escalation, persistence-cybersecurity, openclaw-vulnerabilities, claw-chain-flaws, openclaw-security-update, cve-2024-28983, cve-2024-28984, cve-2024-28985, cve-2024-28986, workflow-automation-security-risks, how-to-secure-openclaw, automation-tool-vulnerabilities]
author: "GlobalBR News"
description: "Attackers can chain four OpenClaw flaws to steal data, escalate privileges, and install backdoors. Here’s what you need to know about the Claw Chain vulnerabili"
source_url: "https://thehackernews.com/2026/05/four-openclaw-flaws-enable-data-theft.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgz_tK9S8jS_n5CK694-FLGjQP5_Mmpg7z9ZRiBayWsJLsuFRIm-8j1hTlhH90779FvnvhpiFKeGP9CzI5RCPsxQEnOzAIQsPzUsAJhUWtNm9iwf9C1W9DbDmqoQ_jjHhM7huYDV210OB9o1L9NPoJ0IL6R9Xc-V4JQ91Kn-b47_2ravRJ6-qlZOVrqsuAz/s1600/openclaw.png"
image_alt: "4 OpenClaw Flaws Let Hackers Steal Data, Hijack Systems"
image_caption: "A digital illustration of a claw machine grabbing sensitive data files, representing how attackers exploit OpenClaw flaw"
keywords: ["OpenClaw vulnerabilities", "Claw Chain flaws", "OpenClaw security update", "CVE-2024-28983", "CVE-2024-28984", "CVE-2024-28985", "CVE-2024-28986", "workflow automation security risks"]
key_points:
  - "Four OpenClaw flaws can be chained for full system compromise"
  - "Attackers gain data theft, privilege escalation, and persistence"
  - "Claw Chain bugs affect workflow automation tools"
faq:
  - q: "What is OpenClaw and why do these flaws matter?"
    a: "OpenClaw is an open-source automation tool used for workflows and data processing. These flaws let attackers steal data, escalate privileges, and plant backdoors, making them critical for any organization using the tool."
  - q: "How do attackers chain these four flaws together?"
    a: "They start with authentication bypass to gain admin access, then hijack sessions to maintain persistence, use file traversal to steal data or plant malware, and finally plant backdoors via weak file permissions."
  - q: "Are there public exploits available for these flaws?"
    a: "Yes, proof-of-concept exploits are already circulating online, making it easy for even low-skilled attackers to target unpatched OpenClaw instances."
  - q: "What should I do if my organization uses OpenClaw?"
    a: "Update to the latest patched version immediately, check logs for signs of exploitation, and run a vulnerability scan to confirm no unauthorized access occurred."
  - q: "Can these flaws affect closed networks or air-gapped systems?"
    a: "They can, especially if attackers pivot from internet-facing systems to internal networks using stolen credentials or secondary exploits."
featured: true
breaking: true
hook: "These four OpenClaw flaws let hackers become admins without a password."
tl_dr: "Hackers can chain four OpenClaw flaws to steal data, escalate privileges, and install backdoors."
lead: "Cybersecurity firm Cyera revealed four OpenClaw flaws—dubbed Claw Chain—that attackers can exploit to steal data, escalate privileges, and plant persistent backdoors. The bugs affect OpenClaw, an open-source tool used for data processing and workflow automation."
content_type: "news"
entities:
  - "OpenClaw"
  - "Cyera"
  - "CVE-2024-28983"
  - "CVE-2024-28984"
  - "CVE-2024-28985"
  - "CVE-2024-28986"
  - "Nessus"
  - "OpenVAS"
---

Cybersecurity researchers at [Cyera](https://www.cyera.io/) uncovered four vulnerabilities in OpenClaw that, when chained together, let attackers steal sensitive data, escalate their privileges, and install persistent backdoors. The flaws—tracked as CVE-2024-28983, CVE-2024-28984, CVE-2024-28985, and CVE-2024-28986—were collectively named Claw Chain by the team. OpenClaw is an open-source automation tool widely used for processing workflows, data pipelines, and integrations across businesses and cloud services. The bugs sit in how OpenClaw handles authentication, session management, and file operations, making them ripe for exploitation.

The first flaw, CVE-2024-28983, is an improper input validation bug in OpenClaw’s web interface. It lets attackers craft malicious requests that bypass authentication checks, tricking the system into treating unauthenticated users as admins. The second flaw, CVE-2024-28984, is a session fixation issue in the login flow, allowing attackers to hijack active user sessions after stealing session tokens. Together, these two bugs let attackers impersonate legitimate users with high-level access.

## How Attackers Exploit These Flaws

The third flaw, CVE-2024-28985, is a path traversal vulnerability in OpenClaw’s file handling. It enables attackers to read or write files outside the intended directory, including sensitive configuration files and logs. The fourth flaw, CVE-2024-28986, is a weak file permission issue that lets attackers plant backdoors in critical system directories. By chaining all four, attackers can move from initial foothold to full system control. The attack starts with exploiting the authentication bypass to get admin access, then uses session hijacking to maintain persistence, followed by file traversal to steal data or plant malware, and ends with planting backdoors via weak permissions.

OpenClaw’s maintainers released patches for all four flaws on June 10, 2024, but many organizations haven’t updated yet. Cybersecurity firm Cyera warned that unpatched instances are already being targeted in the wild. The company’s researchers found evidence of automated scans probing for the vulnerabilities within hours of their disclosure. Attackers don’t need advanced skills—public proof-of-concept exploits are already circulating online, making this a real threat for any business running unpatched OpenClaw instances.

The impact goes beyond data theft. Once attackers plant backdoors, they can move laterally across networks, stealing credentials, deploying ransomware, or spying on internal communications. The backdoors can survive reboots and software updates if attackers maintain access through stolen credentials or secondary exploits. Even closed networks aren’t safe—attackers have been known to pivot from internet-facing systems to internal networks using similar chained vulnerabilities.

## What You Should Do Now

If your organization uses OpenClaw, update to the latest version immediately. The patches fix all four Claw Chain flaws and include additional security improvements. Check your logs for signs of exploitation, like unusual admin login attempts or file read/write operations outside normal directories. If you’re unsure whether you’re affected, run a vulnerability scan using tools like [Nessus](https://www.tenable.com/products/nessus) or [OpenVAS](https://www.openvas.org/).

The broader takeaway is the risk of chained vulnerabilities in automation tools. OpenClaw isn’t alone—many workflow and integration tools have similar flaws that attackers exploit in sequence. Security teams need to look beyond single-point vulnerabilities and assess how flaws can compound in real-world attacks. This isn’t just about OpenClaw; it’s a reminder to audit all automation tools, third-party integrations, and custom scripts for weak links that could unravel an entire security posture.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/four-openclaw-flaws-enable-data-theft.html)
- **Published:** May 15, 2026 at 13:35 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #cybersecurity · #four-open · #claw-flaws-enable

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/four-openclaw-flaws-enable-data-theft.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 15, 2026*


---

## 🇧🇷 Resumo em Português

Em um novo golpe contra a segurança digital global, pesquisadores revelaram a existência do *Claw Chain*, uma cadeia de quatro vulnerabilidades críticas no software OpenClaw que permite a hackers roubar dados sensíveis, assumir o controle de sistemas e instalar backdoors de forma silenciosa. A descoberta, que afeta desde empresas até dispositivos pessoais, acende um alerta vermelho para organizações e usuários no Brasil, onde a dependência de tecnologias abertas é crescente e os riscos de ciberataques seguem em alta.

O OpenClaw, uma ferramenta de código aberto amplamente utilizada para gerenciamento de conteúdo e automação, tornou-se alvo de cibercriminosos devido à sua popularidade em ambientes corporativos e governamentais brasileiros. As falhas, classificadas como de alta severidade, exploram brechas em autenticação, validação de entrada e controle de acesso, possibilitando que invasores escalem privilégios e acessem informações confidenciais sem deixar rastros. Especialistas alertam que, no atual cenário de crescente digitalização e aumento de ataques cibernéticos no país — com destaque para o crescimento de 160% nos crimes digitais em 2023, segundo a Febraban —, a exploração dessas vulnerabilidades poderia ter consequências devastadoras, desde vazamentos de dados de cidadãos até paralisação de serviços essenciais.

Diante do risco iminente, a recomendação é urgente: atualizar imediatamente o OpenClaw para as versões corrigidas e reforçar a segurança com monitoramento contínuo e auditorias independentes.
