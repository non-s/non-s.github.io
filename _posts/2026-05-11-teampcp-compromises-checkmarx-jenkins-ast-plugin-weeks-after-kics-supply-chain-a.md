---
layout: post
title: "TeamPCP Compromises Checkmarx Jenkins AST Plugin Weeks After KICS Supply Chain Attack"
date: 2026-05-11 18:30:00 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, cybersecurity, team, compromises-checkmarx-jenkins, supply-chain-attack, checkmarx, jenkins, checkmarx-jenkins-ast-plugin-hack, jenkins-marketplace-compromised, supply-chain-attack-jenkins, malicious-jenkins-plugin, checkmarx-plugin-security-alert, how-to-secure-jenkins-server, jenkins-plugin-supply-chain-risk, checkmarx-2013-829vc72453fa-1c16-update]
author: "GlobalBR News"
description: "Checkmarx confirms a malicious version of its Jenkins AST plugin was pushed to the Jenkins Marketplace. Affected users must verify their plugin version immediat"
source_url: "https://thehackernews.com/2026/05/teampcp-compromises-checkmarx-jenkins.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
last_updated: "2026-05-11"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiq0A3_8O89uC968dpFnFxE4v3J4fpr5nEqC-2QiSJ_rtZlgPocPYIaowCvCMeONhcrFiaoSdBVeNsuTa2ipAZZ3HBMUDcfO8DZ06pughteYJItHhMLeBr_jnfLL-5WX6xBE_EjIfPDGjCYyDCa6aImjimPNl7FtM1evdnTUVEk54x9pczRaFlmEZy1Cv8B/s1600/Jenkins.jpg"
image_alt: "TeamPCP Compromises Checkmarx Jenkins AST Plugin Weeks After KICS Supply Chain Attack"
image_caption: "A Jenkins server login screen shown on a laptop screen, symbolizing the compromise of the Checkmarx plugin in the Jenkin"
keywords: ["Checkmarx Jenkins AST plugin hack", "Jenkins Marketplace compromised", "supply chain attack Jenkins", "malicious Jenkins plugin", "Checkmarx plugin security alert", "how to secure Jenkins server", "Jenkins plugin supply chain risk", "Checkmarx 2.0.13-829.vc72453fa_1c16 update"]
key_points:
  - "Hackers published a fake Jenkins AST plugin to the Jenkins Marketplace"
  - "Checkmarx advises users to downgrade to version 2.0.13-829.vc72453fa_1c16"
  - "Attack follows the recent KICS supply chain breach"
faq:
  - q: "What is the Jenkins AST plugin?"
    a: "The Jenkins AST plugin is a tool that integrates Checkmarx’s static application security testing into Jenkins pipelines, letting developers scan code for vulnerabilities during builds. It’s widely used in DevOps workflows to catch security issues early in the development process."
  - q: "How can I check if I installed the malicious version?"
    a: "Open Jenkins, go to Manage Plugins, then Installed. Look for the Checkmarx Jenkins AST Plugin and check the version number. If it’s 2.0.13-829.vc72453fa_01c16 or missing a verified signature, uninstall it immediately and install the correct version from Checkmarx’s official site."
  - q: "What happens if I don’t update the plugin?"
    a: "Running the malicious version could let attackers execute arbitrary code on your Jenkins server, giving them access to your build pipelines and potentially your company’s internal network. The risk is highest if the plugin has admin privileges or interacts with sensitive systems."
  - q: "Why did Checkmarx publish a malicious update?"
    a: "The fake update wasn’t published by Checkmarx. Hackers uploaded it to the Jenkins Marketplace pretending to be Checkmarx, bypassing the platform’s security checks. Checkmarx only became aware of the issue after users reported problems."
  - q: "Has this attack been used in real-world breaches yet?"
    a: "Checkmarx hasn’t reported any active breaches linked to this specific compromise. However, supply chain attacks like this often go undetected for weeks or months, so companies should assume they’ve been targeted and scan their systems thoroughly."
featured: true
breaking: true
hook: "A fake Checkmarx plugin just hit Jenkins—and it’s already letting hackers run code on your servers."
tl_dr: "Checkmarx advises Jenkins plugin users to switch to version 2.0.13-829.vc72453fa_1c16 after a malicious update appeared on the Jenkins Marketplace."
lead: "Checkmarx confirmed hackers pushed a compromised version of its Jenkins AST plugin to the Jenkins Marketplace weeks after the KICS supply chain attack. Users must verify they’re running version 2.0.13-829.vc72453fa_1c16 or earlier."
content_type: "news"
entities:
  - "Checkmarx"
  - "Jenkins"
  - "KICS"
  - "Jenkins Marketplace"
  - "VS Code"
  - "DevOps"
---

> 📰 **Continuing coverage:** [OpenAI confirms TanStack supply chain attack hit two employee Macs](/security/2026/05/15/tanstack-supply-chain-attack-hits-two-openai-employee-devices-forces-macos-updat/)

Checkmarx [confirmed](https://www.checkmarx.com) that a malicious update for its Jenkins AST plugin made it to the Jenkins Marketplace over the weekend. The company urged users to check their plugin versions right away, warning that any installation of the fake update could let attackers run arbitrary code on Jenkins servers. The affected version, 2.0.13-829.vc72453fa_01c16, was pushed without Checkmarx’s approval and includes code that isn’t in the legitimate release. Users who installed it should uninstall it immediately and switch to the verified version released on December 17, 2025, or earlier. Checkmarx didn’t say how many users downloaded the malicious update, but Jenkins admins should treat this as an active threat until they confirm their systems are clean.

The attack comes weeks after hackers breached [KICS](https://en.wikipedia.org/wiki/KICS), a rival static analysis tool, and used its supply chain to push malicious updates to thousands of users. Unlike KICS, where attackers gained direct access to the vendor’s build pipeline, the Jenkins plugin compromise appears to have been a fake update uploaded to the public marketplace. Still, the pattern shows attackers are targeting open-source CI/CD tools to spread malware through trusted channels. Jenkins is one of the most widely used automation servers, so a successful breach could give attackers a foothold in countless development pipelines.

## Jenkins Marketplace compromised again

This isn’t the first time attackers have abused the Jenkins Marketplace. In 2023, researchers found over 100 malicious plugins uploaded to the platform, some of which stole credentials or mined cryptocurrency. Jenkins Marketplace relies on community contributions, so security checks aren’t as strict as they are for official vendor channels. Users often trust plugins from the marketplace without verifying signatures or hashes, making it an attractive target for supply chain attacks. Checkmarx’s advice to stick to version 2.0.13-829.vc72453fa_1c16 is a reminder that even trusted vendors can be tricked into publishing bad updates.

## What users should do now

Jenkins administrators need to act fast. First, check the plugin manager to see which version is installed. If it’s 2.0.13-829.vc72453fa_01c16 or anything labeled “Checkmarx Jenkins AST Plugin” without a verified signature, remove it immediately. Then install the correct version from Checkmarx’s official site or a trusted source. Jenkins also lets admins block specific plugin versions, so restricting installations to signed releases could prevent future attacks. Companies should scan their Jenkins servers for signs of compromise, like unexpected network traffic or new admin accounts, just in case the malicious plugin was active long enough to do damage.

Checkmarx says it’s working with Jenkins maintainers to tighten controls on the marketplace, but for now, users are on their own. The company hasn’t disclosed how the fake update got past its checks, but supply chain attacks like this one often start with stolen credentials or a compromised developer’s machine. Jenkins isn’t the only target—last month, attackers pushed a malicious [VS Code extension](https://en.wikipedia.org/wiki/Visual_Studio_Code) through Microsoft’s extension store, showing how attackers are exploiting every corner of the dev tool ecosystem.

The broader risk here isn’t just bad code running on a server. If an attacker can control a Jenkins pipeline, they can steal source code, inject backdoors, or pivot to other systems inside a company’s network. Small teams that rely on free plugins from public stores are especially vulnerable because they often lack the resources to vet every update. Checkmarx’s warning is a wake-up call: even tools you trust can be weaponized, and the only way to stay safe is to verify everything yourself.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/teampcp-compromises-checkmarx-jenkins.html)
- **Published:** May 11, 2026 at 18:30 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #cybersecurity · #team · #compromises-checkmarx-jenkins

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/teampcp-compromises-checkmarx-jenkins.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 11, 2026*


---

## 🇧🇷 Resumo em Português

Um plugin essencial para o desenvolvimento seguro de software no Brasil foi infectado por hackers semanas depois de outra grave brecha de segurança na cadeia de suprimentos. A Checkmarx, empresa especializada em segurança de aplicações, confirmou que uma versão maliciosa do seu plugin Jenkins AST foi injetada no mercado oficial da plataforma, colocando em risco empresas e desenvolvedores que dependem da ferramenta para identificar vulnerabilidades no código.

O ataque ocorreu semanas após a própria Checkmarx ter sido vítima de um *supply chain attack* por meio da ferramenta KICS, o que demonstra como os cibercriminosos estão explorando cadeias de suprimentos de segurança para distribuir malwares. No Brasil, onde o desenvolvimento de software tem crescido exponencialmente, especialmente em setores como *fintechs* e *govtech*, a notícia acende um alerta vermelho: milhares de organizações podem estar usando a versão comprometida sem saber, expondo seus sistemas a ataques ainda mais graves. A recomendação é imediata: verificar a versão instalada do plugin e, se necessário, removê-lo e substituí-lo pela versão oficial.

O episódio reforça a necessidade de auditorias constantes em ferramentas de segurança e uma revisão urgente nos protocolos de validação de atualizações por parte das empresas brasileiras.
