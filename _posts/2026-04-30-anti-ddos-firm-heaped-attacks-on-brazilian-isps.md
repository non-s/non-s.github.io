---
layout: post
title: "Anti-DDoS Firm Heaped Attacks on Brazilian ISPs"
date: 2026-04-30 14:04:26 +0000
categories: [security]
tags: [krebs, security, cybersecurity, anti, firm-heaped-attacks, brazilian, brazil, huge-networks-ddos-attack-brazil, brazilian-isp-ddos-breach, ddos-protection-firm-hacked, ssh-keys-exposed-online-brazil, 400-gbps-ddos-attack-brazil-isp, tp-link-archer-ax21-botnet-brazil, brazilian-telecom-regulator-ddos-probe]
author: "GlobalBR News"
description: "A top Brazilian anti-DDoS provider left SSH keys exposed online, letting attackers hijack its gear to blast rivals with DDoS attacks for years. Security researc"
source_url: "https://krebsonsecurity.com/2026/04/anti-ddos-firm-heaped-attacks-on-brazilian-isps/"
source_name: "Krebs on Security"
sentiment: "negative"
lang: "en"
image: "https://krebsonsecurity.com/wp-content/uploads/2026/04/tpllink-ax21.png"
image_alt: "Anti-DDoS Firm Heaped Attacks on Brazilian ISPs"
image_caption: "A TP-Link Archer AX21 router, the model Brazilian ISP Huge Networks used in its botnet attacks."
keywords: ["Huge Networks DDoS attack Brazil", "Brazilian ISP DDoS breach", "DDoS protection firm hacked", "SSH keys exposed online Brazil", "400 Gbps DDoS attack Brazil ISP", "TP-Link Archer AX21 botnet Brazil", "Brazilian telecom regulator DDoS probe"]
key_points:
  - "Huge Networks’ private SSH keys sat open on the internet for years"
  - "Attackers turned its routers into attack drones against Brazilian rivals"
  - "CEO blames a breach, suspects a competitor framed his company"
faq:
  - q: "What kind of DDoS attacks did Huge Networks’ routers launch?"
    a: "Attackers used the hijacked routers to flood rival ISPs with junk traffic peaking above 400 Gbps, enough to knock entire neighborhoods offline for hours. The traffic all originated from Brazilian IP addresses that once belonged to Huge Networks’ customers."
  - q: "How did hackers take over Huge Networks’ routers?"
    a: "Huge Networks left its private SSH authentication keys exposed in an open online folder. With those keys, attackers logged into company servers, installed malicious firmware on routers, and turned them into remote-controlled attack drones."
  - q: "Who do Brazilian ISPs blame for the attacks?"
    a: "Huge Networks’ CEO says he thinks a competitor framed the company to damage its reputation. Security researchers say the sophistication of the scripts suggests the breach was deeper than a single break-in, but they haven’t named a suspect."
  - q: "What are Brazilian regulators doing about this?"
    a: "Brazil’s telecom regulator has started audits of Huge Networks’ infrastructure. Officials have hinted they may fine the company or force it to stop selling DDoS services until a full forensic review is complete."
  - q: "Could this happen to other DDoS protection firms?"
    a: "Security experts warn that any DDoS vendor that cuts corners on key management could face the same risk. Leaving private SSH keys or admin passwords exposed online can turn a protection firm’s own gear into attack weapons."
featured: true
breaking: true
hook: "A cybersecurity firm that promised to stop DDoS attacks spent years accidentally launching them instead."
tl_dr: "Brazilian DDoS firm’s exposed keys let hackers weaponize its routers in years-long cyberattacks on local ISPs."
lead: "A Miami-based Brazilian ISP that sells DDoS protection left its private network keys exposed online for years, letting hackers hijack its routers and fire off massive denial-of-service attacks against rivals across Brazil."
content_type: "news"
entities:
  - "Huge Networks"
  - "KrebsOnSecurity"
  - "TP-Link"
  - "Archer AX21"
  - "Netscout"
  - "Rio de Janeiro"
---

A Brazilian ISP that markets itself as a shield against digital assaults accidentally became the sword it claimed to stop. For at least three years, the company’s exposed private keys let attackers hijack its network gear and launch devastating DDoS attacks against other Brazilian internet providers, security researchers found. The fallout is now forcing ISPs across Brazil to scour their networks for hidden backdoors while regulators and rivals question whether the company can still be trusted to protect them.

## How the attack worked
The mess started with a simple mistake: Huge Networks, a Miami-based firm founded in 2014 that focuses on scrubbing DDoS traffic for Brazilian customers, left its private SSH authentication keys in an open online folder. The exposure wasn’t spotted until an anonymous tipster handed KrebsOnSecurity a trove of files from that folder earlier this month. Inside were Python scripts written in Portuguese that automatically built malware-laced routers, plus the CEO’s personal SSH keys used to log into company servers.

With those keys in hand, attackers could silently commandeer Huge Networks’ routers—mostly TP-Link Archer AX21 models—and force them to spew junk traffic at rival ISPs. Security firm Netscout tallied attacks peaking above 400 Gbps, enough to knock entire neighborhoods offline for hours. All the targets were Brazilian network operators, and all the traffic flowed from Brazilian IP addresses that once belonged to Huge Networks’ customers.

## The company’s shaky explanation
Huge Networks’ CEO told KrebsOnSecurity the attacks weren’t intentional. He blamed a security breach, saying hackers likely broke in and planted the scripts to make his company look bad. “Someone is trying to damage our reputation,” he wrote in a message to the site. But the exposed SSH keys and the Python scripts that turned routers into bots suggest the compromise was deeper than a single break-in. The scripts included hard-coded commands that automatically updated the malware and rotated command-and-control servers, a sophistication level most script kiddies can’t manage.

Brazilian telecom regulators have already started audits of Huge Networks’ infrastructure, and rival ISPs are reviewing their peering agreements. One Rio de Janeiro provider told local media its engineers found rogue firmware on five routers it bought from Huge Networks last year—firmware it never installed itself.

## Why this matters beyond Brazil
The case highlights how easily trust can evaporate in the cybersecurity market. Companies that sell DDoS protection are supposed to be the good guys, yet here’s one whose gear was weaponized against its own customers. The incident also shows how small oversights—like leaving private keys in a public folder—can cascade into national-level internet outages. Security experts warn the same trick could work against any DDoS vendor that cuts corners on key management.

For now, Brazilian ISPs are rushing to reset passwords, revoke old keys, and replace any routers that touched Huge Networks’ network. The country’s telecom regulator has hinted it may fine the company or force it to stop selling DDoS services until a full forensic review is done. Huge Networks didn’t respond to requests for comment on whether it plans to shut down operations while the investigation continues.

The bigger question is whether customers will ever see the company as more than a wolf in sheep’s clothing. In Brazil, where internet blackouts can spark protests and hurt businesses, that’s a reputation no cybersecurity firm can afford to lose.

<!--more-->


## What You Need to Know

- **Source:** [Krebs on Security](https://krebsonsecurity.com/2026/04/anti-ddos-firm-heaped-attacks-on-brazilian-isps/)
- **Published:** April 30, 2026 at 14:04 UTC
- **Category:** Security
- **Topics:** #krebs · #security · #cybersecurity · #anti · #firm-heaped-attacks · #brazilian

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Krebs on Security →](https://krebsonsecurity.com/2026/04/anti-ddos-firm-heaped-attacks-on-brazilian-isps/)**

*All reporting rights belong to the respective author(s) at **Krebs on Security**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · April 30, 2026*


---

## 🇧🇷 Resumo em Português

Um provedor brasileiro líder em segurança contra ataques DDoS expôs, por anos, chaves SSH públicas na internet, permitindo que hackers sequestrassem seus equipamentos e usassem a infraestrutura para lançar ataques massivos contra concorrentes e clientes. A descoberta, revelada por pesquisadores de segurança, expõe não apenas uma falha técnica, mas também um risco sistêmico para empresas brasileiras que dependem de proteção digital contra invasões e paralisações.

O caso ganha contornos preocupantes ao revelar como a falta de proteção básica em uma empresa especializada pode se tornar uma arma contra todo o ecossistema de cibersegurança no Brasil. Com dados sensíveis e sistemas críticos em jogo, a exposição de chaves SSH — que permitem acesso remoto não autorizado — coloca em xeque a confiança de clientes e parceiros, além de abrir brechas para que criminosos amplifiquem suas operações. Para um país que já sofre com a alta incidência de ataques DDoS — como os que atingiram bancos e órgãos governamentais nos últimos anos — a vulnerabilidade em uma empresa desse setor é um alerta vermelho sobre a necessidade urgente de auditorias independentes e regulação mais rígida no setor.

Agora, resta saber se as autoridades brasileiras agirão para investigar o incidente e se a empresa tomará medidas concretas para evitar novos vazamentos.
