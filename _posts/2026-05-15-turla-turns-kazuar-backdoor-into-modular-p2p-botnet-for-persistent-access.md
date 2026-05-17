---
layout: post
title: "Russian hackers turn Kazuar backdoor into a sneaky P2P botnet"
date: 2026-05-15 17:10:25 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, cybersecurity, turla-turns-kazuar, backdoor-into-modular, botnet, russian, turla, turla-kazuar-p2p-botnet, russian-hackers-kazuar-malware, cisa-kazuarp2p-warning, fsb-linked-turla-hacking-group, kazuar-backdoor-upgrade, peer-to-peer-malware-stealth, how-kazuarp2p-spreads, turla-espionage-tools-2024]
author: "GlobalBR News"
description: "Russian FSB-linked hackers now use a revamped Kazuar backdoor to power a stealthy P2P botnet for long-term access. New details reveal how Turla upgraded its old"
source_url: "https://thehackernews.com/2026/05/turla-turns-kazuar-backdoor-into.html"
source_name: "The Hacker News"
sentiment: "neutral"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEg8BT1AOScncZQM_A-0WBdCzTDAHGHSey48_Mywhij-TJupCdzP3s3o-MIImRtMZcoV2OqX3RjRV4COpVqkB1mrH3d_zjwvSTwCEXOq_2m80HgDo-xwAZ1KpR1h8eN9dAHGcKN_PpcE0cBsnv67FcthDycHLBJMYs8NkPszWNiQqdbhyL0YIlwVJn4NtgaR/s1600/code.jpg"
image_alt: "Russian hackers turn Kazuar backdoor into a sneaky P2P botnet"
image_caption: "Diagram of a peer-to-peer network with nodes representing infected machines, overlaid with a Russian hacker silhouette a"
keywords: ["Turla Kazuar P2P botnet", "Russian hackers Kazuar malware", "CISA Kazuar.P2P warning", "FSB linked Turla hacking group", "Kazuar backdoor upgrade", "peer-to-peer malware stealth", "how Kazuar.P2P spreads", "Turla espionage tools 2024"]
key_points:
  - "Turla hackers linked to Russia’s FSB upgraded Kazuar backdoor"
  - "New version runs as a modular P2P botnet for stealth access"
  - "CISA warns the botnet targets government and private networks"
faq:
  - q: "What is Kazuar and why is it dangerous?"
    a: "Kazuar is a backdoor malware family used by Russia’s Turla hackers since 2017. It lets attackers steal data, spy on victims, and drop more malware. The new P2P version is dangerous because it spreads like a self-healing network, making it much harder to detect and remove."
  - q: "How does the Kazuar.P2P botnet spread?"
    a: "It starts with stolen VPN credentials or a zero-day exploit. Then it moves laterally across a network, infecting servers that become 'seed nodes.' These nodes spread the infection to other machines, turning them into part of a hidden P2P network that’s hard to dismantle."
  - q: "Who is behind the Kazuar.P2P botnet?"
    a: "The Russian hacking group Turla, which U.S. officials link to Center 16 of Russia’s FSB. The group has used Kazuar for years in espionage campaigns targeting governments, military contractors, and journalists."
  - q: "Why is the P2P design such a big deal?"
    a: "Old malware relies on command-and-control servers, which defenders can block or seize. The P2P design removes that single point of failure. Infected machines talk to each other, making the botnet resilient and nearly impossible to shut down by taking out one server."
  - q: "How can organizations protect against Kazuar.P2P?"
    a: "CISA recommends auditing VPN logs, enforcing multi-factor authentication, segmenting networks, and patching all Windows servers immediately. Detection rules from firms like Kaspersky can help, but the malware’s stealth makes it tough to spot early."
breaking: false
hook: "Russia’s Turla just built a botnet that fights back—and it’s already lurking in networks near you."
tl_dr: "Turla turned Kazuar into a P2P botnet for stealthy, persistent control of hacked devices."
lead: "Russia’s Turla hackers, tied to the FSB, repurposed their Kazuar backdoor into a modular P2P botnet that silently spreads and stays on infected machines for months. CISA flagged the shift in a new alert."
content_type: "news"
entities:
  - "Turla (hacking group)"
  - "Kazuar (malware)"
  - "CISA (U.S. Cybersecurity and Infrastructure Security Agency)"
  - "FSB (Federal Security Service)"
  - "Kaspersky (cybersecurity firm)"
  - "Center 16 (FSB unit)"
  - "VPN (Virtual Private Network)"
---

Russian state-backed hackers known as [Turla](https://en.wikipedia.org/wiki/Turla_(hacking_group)) have quietly rebuilt their custom Kazuar backdoor into something far more dangerous: a modular peer-to-peer (P2P) botnet. The upgrade lets the group spread the malware faster, hide its tracks better, and keep infected machines under their control for much longer than before. U.S. Cybersecurity and Infrastructure Security Agency (CISA) [confirmed the change](https://www.cisa.gov/) in a joint advisory with the FBI and international partners on Tuesday, warning that the revamped tool now targets government and private networks in the U.S. and Europe.

Kazuar isn’t new. Turla has used it since at least 2017 to break into Windows computers, steal data, and drop other malware. But the old version relied on direct command-and-control (C2) servers—easy for defenders to spot and block. The new P2P version ditches those servers entirely. Instead, infected machines talk to each other like a secret chat network, making it nearly impossible to shut down the botnet by taking out a single server. Each node in the network can relay orders, spread updates, and even heal itself if one machine gets cleaned up.

Security firm [Kaspersky](https://www.kaspersky.com/) first spotted the shift in early 2024 during routine threat hunting. They found Kazuar’s code had been split into smaller, swappable modules. One handles spreading to new victims via phishing emails or stolen credentials. Another siphons off files or screenshots. A third quietly installs a backdoor that survives reboots. Kaspersky’s analysts say the botnet’s design shows Turla has been testing it in real attacks since late 2023, mostly hitting organizations in Germany, France, and Ukraine.

CISA’s alert names the upgraded malware **Kazuar.P2P**, and warns it’s now a preferred tool for Turla’s espionage campaigns. The group, tied to Russia’s [Federal Security Service (FSB)](https://en.wikipedia.org/wiki/Federal_Security_Service) via Center 16, has used Kazuar to spy on diplomats, military contractors, and even journalists. The P2P upgrade makes those operations harder to detect—and nearly impossible to dismantle once it’s running.

## How the new Kazuar botnet spreads

Turla doesn’t just drop Kazuar.P2P through phishing anymore. The group has refined its playbook. First, they breach a network using stolen [VPN credentials](https://en.wikipedia.org/wiki/Virtual_private_network) or a zero-day exploit in unpatched software. Once inside, they move laterally, stealing admin passwords and planting Kazuar on key servers. From there, the malware turns those servers into “seed nodes” that infect other machines in the same network. Each new victim joins the P2P swarm, helping spread the infection even if Turla’s initial foothold gets kicked out.

The botnet’s modular design is what makes it so hard to remove. Even if defenders detect and delete Kazuar from one machine, the malware can reinstall itself from another infected node. It also avoids leaving obvious traces. The P2P traffic looks like normal network chatter, and the malware encrypts its communications. Kaspersky found that Kazuar.P2P uses a custom encryption scheme based on elliptic curves—strong enough that even law enforcement wiretaps wouldn’t crack it without the right keys.

## Why this matters now

This isn’t just another malware upgrade. Kazuar.P2P marks a shift in how state-backed hackers operate. By ditching traditional C2 servers, Turla has made its operations more resilient. Even if CISA or Europol seizes a server, the botnet keeps running. That means Turla can maintain access to compromised networks for years, quietly gathering intelligence or preparing for future attacks. The group has already used Kazuar in past campaigns to steal classified documents and monitor rival governments.

Defenders are scrambling to catch up. Kaspersky and other firms have released detection rules for Kazuar.P2P, but the malware’s stealthy design means many attacks still go unnoticed. Organizations are urged to audit VPN logs, enforce multi-factor authentication, and segment networks to limit lateral movement. CISA recommends treating any unpatched Windows server as a potential entry point for Kazuar.P2P.

Turla’s upgrade shows how quickly cyber threats evolve. The group has been active since the 1990s, and Kazuar.P2P proves they’re still refining their tools to stay ahead of defenses. For now, the botnet remains a quiet but growing threat—one that won’t be easy to shut down.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/turla-turns-kazuar-backdoor-into.html)
- **Published:** May 15, 2026 at 17:10 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #cybersecurity · #turla-turns-kazuar · #backdoor-into-modular

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/turla-turns-kazuar-backdoor-into.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 15, 2026*


---

## 🇧🇷 Resumo em Português

Agora, hackers russos com laços com o FSB transformaram a backdoor Kazuar em uma perigosa e discreta botnet P2P, capaz de driblar defesas e manter acesso prolongado a sistemas infectados. Essa evolução da ferramenta, usada há anos por grupos como o Turla, representa um salto na sofisticação dos ciberataques patrocinados pelo Estado russo, colocando em alerta governos e empresas em todo o mundo.

No Brasil, onde os ataques cibernéticos já custam bilhões aos cofres públicos e privados anualmente, a notícia reforça a urgência de reforçar a segurança digital. Especialistas brasileiros alertam que a nova versão da Kazuar, agora com arquitetura P2P, dificulta ainda mais a detecção e a neutralização, exigindo investimentos em inteligência de ameaças e colaboração internacional. A adaptação de técnicas usadas por serviços de inteligência russos a novos alvos, incluindo infraestruturas críticas, coloca o país em uma posição vulnerável, especialmente em um cenário de eleições e tensões geopolíticas.

O fechamento desta investigação, liderada por pesquisadores da SentinelLabs, deve servir como um aviso para que organizações brasileiras revisem urgentemente suas defesas, pois a Kazuar P2P já pode estar operando sob o radar — e em solo nacional.
