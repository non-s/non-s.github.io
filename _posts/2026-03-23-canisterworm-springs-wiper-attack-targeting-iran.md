---
layout: post
title: "Iran hit by new CanisterWorm wiper attack linked to TeamPCP"
date: 2026-03-23 15:43:04 +0000
categories: [security]
tags: [krebs, security, cybersecurity, vulnerability, canister, worm, springs-wiper-attack, targeting-iran, iran, canisterworm, teampcp-cyberattack, iran-cyberattack-2025, worm-malware-targeting-iran, cloud-security-breach-2025, cybercrime-group-targeting-azure-aws, react2shell-vulnerability-exploit, farsi-language-system-wipe-malware, iran-timezone-data-destruction-attack]
author: "GlobalBR News"
description: "TeamPCP’s CanisterWorm destroys data on Iranian systems and cloud servers using exposed Docker APIs and Kubernetes clusters. Here’s what’s known so far."
source_url: "https://krebsonsecurity.com/2026/03/canisterworm-springs-wiper-attack-targeting-iran/"
source_name: "Krebs on Security"
sentiment: "negative"
lang: "en"
image: "https://krebsonsecurity.com/wp-content/uploads/2026/03/aikido-iranwiper.png"
image_alt: "Iran hit by new CanisterWorm wiper attack linked to TeamPCP"
image_caption: "A snippet of the CanisterWorm malware code targeting systems with Iran’s timezone or Farsi language settings."
keywords: ["CanisterWorm", "TeamPCP cyberattack", "Iran cyberattack 2025", "worm malware targeting Iran", "cloud security breach 2025", "cybercrime group targeting Azure AWS", "React2Shell vulnerability exploit", "Farsi language system wipe malware"]
key_points:
  - "CanisterWorm wipes data on systems with Iran's timezone or Farsi language"
  - "TeamPCP spreads worm via exposed Docker APIs and Kubernetes clusters"
  - "Group targets cloud environments since December 2025"
faq:
  - q: "What is CanisterWorm and how does it work?"
    a: "CanisterWorm is a wiper malware that spreads through unsecured cloud services like Docker APIs and Kubernetes clusters. It deletes data on systems configured for Iran’s timezone or Farsi language, making recovery nearly impossible without backups. Attackers also steal credentials to extort victims over Telegram."
  - q: "Who is behind the CanisterWorm attacks on Iran?"
    a: "Security researchers link the attacks to TeamPCP, a financially motivated cybercrime group active since December 2025. They specialize in targeting cloud infrastructure, particularly Azure and AWS, to steal data and extort victims."
  - q: "Why is TeamPCP targeting Iranian systems specifically?"
    a: "While the exact motive isn’t confirmed, the timing of the attacks aligns with geopolitical tensions involving Iran. The group may be exploiting the current climate for financial gain or ideological reasons, though no direct link to a state actor has been established."
  - q: "How can organizations protect themselves from CanisterWorm?"
    a: "Organizations should audit their cloud security, close exposed APIs, and patch vulnerabilities like React2Shell. Enforce multi-factor authentication, limit access to control planes, and monitor for unusual activity. Regular penetration tests can also help identify weak spots."
  - q: "Is there any way to recover data after a CanisterWorm attack?"
    a: "Recovery is extremely difficult because the malware overwrites files, corrupts databases, and often targets backups stored on the same network. The best defense is prevention—ensuring backups are isolated, encrypted, and tested regularly."
featured: true
breaking: true
hook: "Iran’s digital infrastructure is under siege—this time, the attackers aren’t asking for money, they’re burning everythin"
tl_dr: "New CanisterWorm wipes data on Iranian-linked systems and cloud servers using exposed cloud APIs and Docker vulnerabilities."
lead: "A new cyberattack called CanisterWorm is wiping data on systems tied to Iran, spreading via unsecured cloud services this past weekend. Security experts trace the campaign to TeamPCP, a financially motivated group that’s been active since December 2025."
content_type: "news"
entities:
  - "TeamPCP"
  - "CanisterWorm"
  - "Iran"
  - "Flare Systems"
  - "Azure"
  - "AWS"
  - "React2Shell vulnerability"
  - "Docker APIs"
---

A fresh wave of cyberattacks is targeting Iran, this time with a twist: a wiper malware called CanisterWorm that deliberately destroys data on systems linked to the country. The campaign ramped up this past weekend, spreading through poorly secured cloud services and leaving no trace of the files it deletes. Security researchers say the attack follows a pattern linked to TeamPCP, a relatively new cybercrime group that’s been active since December 2025 and has already compromised dozens of corporate cloud environments. [TeamPCP](https://en.wikipedia.org/wiki/Cybercrime) didn’t just happen upon this attack—they’ve been building toward it. In December, the group began targeting exposed control planes in cloud infrastructure, specifically going after unsecured Docker APIs, Kubernetes clusters, and Redis servers. They also exploited the React2Shell vulnerability, a flaw in application servers that lets attackers execute remote commands without authentication. Once inside a network, TeamPCP didn’t just steal data—they moved laterally, siphoning authentication credentials and then contacting victims over Telegram to demand ransom payments. The CanisterWorm takes this a step further. Unlike typical ransomware, it doesn’t encrypt files for extortion—it wipes them clean. The worm scans for systems configured with Iran’s local timezone or set to Farsi as the default language, then deletes data without warning. Researchers at [Flare](https://en.wikipedia.org/wiki/Flare_Systems), a security firm that profiled TeamPCP in January, say the group’s strategy is unique because it focuses on cloud infrastructure rather than end-user devices. Their data shows that Azure accounts for 61% of the group’s targets, while AWS accounts for 36%, leaving just 3% for other platforms. The shift reflects a broader trend in cybercrime: attackers are increasingly targeting cloud services because they offer high-value data and weaker security controls compared to traditional endpoints. What makes this campaign particularly dangerous is its timing. The attacks align with rising geopolitical tensions involving Iran, raising concerns that the group may be attempting to insert itself into the conflict for financial gain or ideological reasons. While there’s no public evidence linking TeamPCP to a state actor, their focus on Iranian-linked systems suggests they’re exploiting the current climate. Victims who’ve been hit by CanisterWorm report finding their servers rendered unusable within hours. Recovery is nearly impossible without recent backups, and even then, the psychological toll of a total wipeout is significant. The group’s use of Telegram for extortion adds another layer of urgency—victims often feel pressured to pay quickly to avoid public exposure or further damage. ## How the worm spreads and what it targets CanisterWorm doesn’t rely on phishing emails or infected attachments like traditional malware. Instead, it spreads through exposed cloud services, particularly those running outdated or misconfigured Docker APIs and Kubernetes clusters. These control planes are often left open by companies that prioritize convenience over security, giving attackers an easy entry point. Once inside, the worm uses the React2Shell vulnerability to execute commands remotely, allowing it to spread to other connected systems. The malware then checks the victim’s system locale—if it detects Iran’s timezone or Farsi as the default language, it triggers the wiper payload. The destruction is immediate and irreversible. Files are overwritten, databases are corrupted, and backups stored on the same network are often compromised too. The attackers behind CanisterWorm aren’t just wiping data—they’re also stealing credentials. Before the wipe, the worm collects authentication tokens and sensitive files, which are then used for extortion. Victims receive messages on Telegram demanding payment in cryptocurrency, typically Bitcoin or Monero, in exchange for not leaking the stolen data or restoring their systems. ## Why cloud services are the new battleground Cloud infrastructure has become a prime target for cybercriminals because it’s where the most valuable data lives. Companies store customer records, financial transactions, intellectual property, and even critical infrastructure controls in the cloud. When these systems are exposed, attackers can move quickly to exploit them, often undetected for months. TeamPCP’s focus on Azure and AWS reflects this reality. Both platforms are widely used, but their sheer size means security teams often struggle to keep up with patches and misconfigurations. A single exposed Kubernetes dashboard or unsecured Redis instance can provide a foothold for an entire attack chain. The CanisterWorm campaign highlights a growing problem: the blurring lines between cybercrime and geopolitics. While TeamPCP’s motives aren’t fully clear, their targeting of Iranian-linked systems suggests they’re capitalizing on the current climate. Whether they’re driven by money, ideology, or a mix of both, their attacks are causing real damage—and they’re likely to keep evolving as cloud adoption grows. ## What happens next and how to protect yourself If you’re running cloud services, especially on Azure or AWS, now’s the time to audit your security posture. Check for exposed APIs, misconfigured clusters, and unpatched vulnerabilities like React2Shell. Limit access to control planes, enforce multi-factor authentication, and monitor for unusual activity. For end users, the risk is lower but not zero. Avoid downloading files from untrusted sources, and ensure your devices are updated with the latest security patches. If your organization relies on cloud services, consider hiring a third-party firm to perform a penetration test. The CanisterWorm campaign is a reminder that cyberattacks aren’t just about stealing data—they’re about destroying it too. And in today’s digital world, that can be just as devastating.

<!--more-->


## What You Need to Know

- **Source:** [Krebs on Security](https://krebsonsecurity.com/2026/03/canisterworm-springs-wiper-attack-targeting-iran/)
- **Published:** March 23, 2026 at 15:43 UTC
- **Category:** Security
- **Topics:** #krebs · #security · #cybersecurity · #vulnerability · #canister · #worm

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Krebs on Security →](https://krebsonsecurity.com/2026/03/canisterworm-springs-wiper-attack-targeting-iran/)**

*All reporting rights belong to the respective author(s) at **Krebs on Security**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · March 23, 2026*


---

## 🇧🇷 Resumo em Português

Um novo malware, batizado de *CanisterWorm*, está causando estragos no Irã, destruindo dados em sistemas e servidores em nuvem por meio de APIs expostas do Docker e clusters Kubernetes. A operação, atribuída ao grupo *TeamPCP*, evidencia uma tendência crescente de ciberataques com foco em infraestruturas críticas, algo que já preocupa especialistas brasileiros.

No Brasil, onde a digitalização de serviços públicos e privados avança rapidamente, o incidente serve como um alerta sobre a vulnerabilidade de ambientes semelhantes. APIs e clusters mal configurados são portas de entrada para criminosos cibernéticos, que podem explorar falhas para disseminar worms destrutivos ou roubar informações sensíveis. A semelhança com ataques recentes contra instituições brasileiras reforça a necessidade de auditorias rigorosas e adoção de boas práticas de cibersegurança.

A expectativa é que, com o avanço da investigação, mais detalhes sobre as motivações e o alcance do *CanisterWorm* sejam revelados — e, possivelmente, novas vítimas sejam identificadas.
