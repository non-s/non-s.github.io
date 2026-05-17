---
layout: post
title: "New TrickMo Variant Uses TON C2 and SOCKS5 to Create Android Network Pivots"
date: 2026-05-12 12:50:00 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, cybersecurity, variant-uses, create-android-network, pivots-cybersecurity, trick, android, trickmo-android-trojan, ton-blockchain-malware, socks5-proxy-trojan, android-banking-trojan-2026, mobile-malware-c2, the-open-network-malware, sms-phishing-android, crypto-wallet-trojan]
author: "GlobalBR News"
description: "A new TrickMo Android banking trojan variant uses The Open Network blockchain for C2 and SOCKS5 proxies to steal money from European banking and crypto users. R"
source_url: "https://thehackernews.com/2026/05/new-trickmo-variant-uses-ton-c2-and.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjbBy7H5qvorFUmJqREACqqxVC0ogVq88dP8wLyKyUPF9fCowpUSkb7foEsEPDALt0ccCpcJc6PXCJjFmQo0oX3furU-cYPULBa0-pjpiLGV04JD6kr4G0VIrvFoJo54WmgjU1YocsquA15N3hxDmwt4i82QpYdil7F4fI0SMFVv9YCkbqqGKjIi-dEmcIx/s1600/tricks.jpg"
image_alt: "New TrickMo Variant Uses TON C2 and SOCKS5 to Create Android Network Pivots"
image_caption: "A smartphone displaying a fake banking app interface, with a shadowy figure in the background representing the TrickMo t"
keywords: ["TrickMo Android trojan", "TON blockchain malware", "SOCKS5 proxy trojan", "Android banking trojan 2026", "mobile malware C2", "The Open Network malware", "sms phishing android", "crypto wallet trojan"]
key_points:
  - "New TrickMo trojan uses TON blockchain for stealth C2 communication"
  - "Variant loads malicious code at runtime from a dex.module APK"
  - "SOCKS5 proxies let hackers route traffic through victims’ devices"
faq:
  - q: "What is The Open Network (TON) and why are hackers using it for malware C2?"
    a: "The Open Network is a decentralized blockchain platform originally developed by Telegram. Hackers use it for malware command-and-control because transactions are cheap, hard to block, and nearly untraceable compared to traditional servers."
  - q: "How does the new TrickMo variant spread to Android devices?"
    a: "The trojan spreads via smishing texts that trick users into downloading a fake banking or crypto app. Once installed, it loads malicious code at runtime and requests dangerous permissions like accessibility services to steal data."
  - q: "Which countries are currently targeted by this TrickMo variant?"
    a: "The campaign is hitting banking and cryptocurrency users specifically in France, Italy, and Austria between January and February 2026, according to ThreatFabric’s findings."
  - q: "What makes this TrickMo variant more dangerous than older versions?"
    a: "It uses TON blockchain for C2 and SOCKS5 proxies to route hacker traffic through infected devices, making it harder to detect and trace. It also loads code at runtime to avoid leaving forensic traces."
  - q: "How can Android users protect themselves from this trojan?"
    a: "Avoid clicking links in unexpected texts, only download apps from the Play Store, and install a mobile security app. If you suspect an infection, revoke suspicious permissions and run a malware scan immediately."
breaking: false
hook: "A new Android trojan turns your phone into a hacker’s relay—and it’s using blockchain to stay hidden."
tl_dr: "New TrickMo trojan uses TON blockchain C2 and SOCKS5 proxies to steal from European banking and crypto users."
lead: "Security researchers spotted a new TrickMo Android banking trojan variant that hijacks victims’ network connections using The Open Network (TON) blockchain for command-and-control (C2) and SOCKS5 proxies. The attack, active between January and February 2026, specifically hit banking and cryptocurrency wallet users in France, Italy, and Austria."
content_type: "news"
entities:
  - "TrickMo"
  - "The Open Network (TON)"
  - "ThreatFabric"
  - "Android"
  - "The Hacker News"
---

A fresh twist on the TrickMo Android banking trojan is giving cybercriminals a stealthier way to drain bank accounts and cryptocurrency wallets. First spotted by [ThreatFabric](https://www.threatfabric.com) between January and February 2026, this new variant ditches traditional C2 servers for The Open Network (TON) blockchain, making it harder to track and shut down. The trojan’s operators also weaponized SOCKS5 proxies, letting them route traffic through infected devices to mask their location.

This isn’t just a minor update. The malware loads a malicious APK component at runtime—called dex.module—directly into memory, leaving little forensic evidence on the device. Once it’s in, TrickMo sets up shop on the victim’s phone, intercepting SMS messages, keylogging, and even taking screenshots to steal one-time passwords and crypto wallet seeds. Its focus on banking and crypto users in France, Italy, and Austria suggests it’s a targeted campaign, possibly linked to regional cybercrime groups.

## How the attack works: stealth mode on steroids
The trojan’s use of TON blockchain is the standout feature. Instead of phoning home to a server, it transmits encrypted commands via TON’s decentralized network. That makes it nearly impossible to block at the DNS level. The SOCKS5 proxy twist is even sneakier: hackers can reroute their own traffic through infected phones, making it look like the attacks originate from inside Europe. This fools fraud detection systems that often flag logins from unfamiliar locations.

ThreatFabric’s analysis shows the malware spreads through smishing (SMS phishing) messages disguised as banking alerts or delivery notifications. Clicking the link downloads a fake app—often mimicking legitimate banking or crypto wallet interfaces—which installs the trojan in the background. Once active, it requests dangerous permissions like accessibility services, which let it mimic user actions and bypass two-factor authentication.

## Why this matters beyond Europe
While the campaign is currently limited to three countries, security experts warn this could be a testing ground for broader attacks. The TON blockchain’s decentralized nature means law enforcement can’t easily seize C2 infrastructure, and the SOCKS5 proxy trick makes attribution nearly impossible. Banks and crypto platforms in other regions should brace for similar campaigns, especially if this variant proves profitable for the attackers.

TrickMo isn’t new—it’s been around since at least 2019—but this update shows how quickly banking trojans evolve. Older versions relied on overlay attacks and fake login screens, but this TON-based version is more advanced. It’s also cheaper to operate: TON transactions are cheap, and SOCKS5 proxies are easy to rent on dark web markets. That lowers the barrier for cybercriminals who want to dip their toes into mobile banking fraud.

## What’s next for victims and defenders
If you’re in France, Italy, or Austria and got an odd SMS about a bank transfer or package delivery, don’t click the link. Check the sender’s number and verify any urgent requests directly with your bank. Android users should also stick to the Play Store and avoid sideloading apps unless absolutely necessary. Installing a reputable mobile security app can catch these trojans before they do damage.

For security teams, this is a wake-up call. Traditional network defenses won’t catch TON-based C2 traffic, so they’ll need to update their monitoring tools. Behavioral analysis—like spotting unusual SMS forwarding or screen interactions—might be the only way to flag these attacks early. The cat-and-mouse game just got harder, and it’s up to defenders to keep up.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/new-trickmo-variant-uses-ton-c2-and.html)
- **Published:** May 12, 2026 at 12:50 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #cybersecurity · #variant-uses · #create-android-network

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/new-trickmo-variant-uses-ton-c2-and.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 12, 2026*


---

## 🇧🇷 Resumo em Português

O Brasil, que já sofre com os altos índices de fraudes digitais no mundo mobile, agora precisa redobrar a atenção: uma nova variante do TrickMo, um dos trojans bancários mais temidos para Android, acaba de ganhar um recurso inédito para roubar dinheiro de vítimas não só na Europa, como também potencialmente no exterior. A descoberta, feita por pesquisadores de segurança, revela que os criminosos passaram a usar a rede The Open Network (TON) — a mesma blockchain por trás do token Toncoin — para esconder seus servidores de comando e controle (C2), além de criar proxies SOCKS5 que transformam dispositivos infectados em verdadeiras pontes para ataques direcionados.

O contexto é especialmente preocupante para o Brasil, onde o uso de aplicativos bancários no celular é massivo e o TrickMo já circulava em versões anteriores, adaptadas para roubar dados de instituições financeiras locais. A novidade está justamente na infraestrutura: ao explorar a TON, os atacantes dificultam a rastreabilidade das comunicações, enquanto os proxies SOCKS5 permitem que o trojan use os próprios smartphones das vítimas como intermediários para acessar bancos ou trocas de criptomoedas — inclusive de outras vítimas em diferentes países. Especialistas alertam que, com essa evolução, o Brasil pode se tornar um alvo ainda mais atraente, já que a maioria dos usuários não costuma desconfiar de transferências ou acessos suspeitos quando o dispositivo parece "normal".

A próxima etapa, segundo analistas, deve envolver a adaptação desse novo vetor para golpes em plataformas de pagamento instantâneo e fintechs brasileiras, exigindo que instituições e usuários reforcem medidas como autenticação multifator e monitoramento de tráfego suspeito.
