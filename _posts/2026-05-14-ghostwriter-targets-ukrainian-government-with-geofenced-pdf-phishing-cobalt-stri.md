---
layout: post
title: "Belarus Ghostwriter group hits Ukraine with geofenced PDF phishing"
date: 2026-05-14 14:00:37 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, phishing, ghostwriter-targets-ukrainian, government-with-geofenced, belarus, ghostwriter, ghostwriter-hackers, belarus-cyberattacks-ukraine, geofenced-pdf-phishing, cobalt-strike-malware, storm-0257-ta445-hacking-group, ukraine-government-cyber-espionage, how-geofenced-phishing-works, belarus-hackers-targeting-ukraine-2024]
author: "GlobalBR News"
description: "Ghostwriter hackers from Belarus used geofenced PDF phishing to attack Ukraine’s government. Cobalt Strike deployed in latest campaign."
source_url: "https://thehackernews.com/2026/05/ghostwriter-targets-ukrainian.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhEld5BcqD9rYWVjx7o_XlV5pN_9djvilow0iIYP-LlFEzGReX8fTPZ0gKi9zMGVLTT8qddHu5FyBMaZpQroEzYFpsoPWf96hD7JeTdqsROemmavXW2pDxNwc9kjvpJdhahmXA5Ng88tN1lyO5rqzC3K6JNwPFPWBo7OzSsaiQIN8JJsXvMrGhewMfzpouF/s1600/uk.jpg"
image_alt: "Belarus Ghostwriter group hits Ukraine with geofenced PDF phishing"
image_caption: "A hacker’s laptop screen showing a fake Ukrainian tax notice PDF laced with malware."
keywords: ["Ghostwriter hackers", "Belarus cyberattacks Ukraine", "geofenced PDF phishing", "Cobalt Strike malware", "Storm-0257 TA445 hacking group", "Ukraine government cyber espionage", "how geofenced phishing works", "Belarus hackers targeting Ukraine 2024"]
key_points:
  - "Ghostwriter group from Belarus targets Ukrainian government agencies"
  - "Attackers used geofenced PDF phishing emails with malicious links"
  - "Cobalt Strike malware deployed to steal sensitive data"
faq:
  - q: "What is the Ghostwriter hacking group?"
    a: "Ghostwriter is a hacker group aligned with Belarus that has been active since at least 2016. Security firms track it under names like Storm-0257 and TA445. It’s known for cyber espionage and influence operations, especially against Ukraine."
  - q: "What attack method did Ghostwriter use in this campaign?"
    a: "Ghostwriter sent geofenced PDF phishing emails that only delivered malware if the recipient was in Ukraine. The PDFs used a now-patched Adobe Reader flaw to install Cobalt Strike, a remote access tool used for data theft."
  - q: "How does geofenced phishing work?"
    a: "Geofenced phishing checks a victim’s IP address before delivering malware. If the IP isn’t in the target country, the link leads to a harmless site. This trick reduces detection and avoids exposing the attacker’s infrastructure."
  - q: "Why is Cobalt Strike significant in this attack?"
    a: "Cobalt Strike is a legitimate penetration testing tool often abused by hackers. In this case, Ghostwriter used it to steal screenshots, log keystrokes, and exfiltrate files from infected Ukrainian government machines. It allows long-term access to networks."
  - q: "Has Ukraine’s government responded to these attacks?"
    a: "Yes. Ukraine’s cyber defense agency CERT-UA issued a public warning on May 29, 2024, urging staff to verify unexpected attachments and disable macros. Microsoft also added detection signatures to its Defender suite to block the Cobalt Strike payloads."
featured: true
breaking: true
hook: "A Belarus-backed hacker group just used fake tax notices to sneak malware into Ukraine’s government."
tl_dr: "Belarus Ghostwriter group hits Ukraine with geofenced PDF phishing and Cobalt Strike to steal data."
lead: "A Belarus-aligned hacker group, tracked as Ghostwriter, launched fresh cyberattacks against Ukrainian government agencies this month using geofenced PDF phishing lures and Cobalt Strike malware."
content_type: "news"
entities:
  - "Ghostwriter"
  - "Storm-0257"
  - "TA445"
  - "CERT-UA"
  - "Cobalt Strike"
  - "Belarus"
  - "Ukraine"
---

A hacker group aligned with Belarus, known as Ghostwriter, has restarted cyberattacks on Ukrainian government systems using a mix of geofenced PDF phishing and the Cobalt Strike toolkit. Security researchers confirmed the campaign started in late May 2024, with emails pretending to be official documents delivered to mid-level ministry staff. The lures included fake tax notices and procurement alerts, designed to look like they came from Ukraine’s Ministry of Finance or local tax offices. When recipients clicked the links, the PDFs checked the victim’s IP address. If the address was outside Ukraine, the link redirected to a benign site. Only Ukrainian IP addresses got the real payload: a malicious PDF that installed Cobalt Strike for remote access.

Ghostwriter isn’t new. Active since at least 2016, the group has a long history of targeting Ukraine with both cyber espionage and influence operations. Microsoft tracks the group as Storm-0257, while Recorded Future calls it TA445 and Cisco Talos lists it as UAC‑0057. The aliases reflect how different security firms label the same set of operators. Ghostwriter has previously used fake news sites and leaked emails to sway public opinion in Eastern Europe, but this latest campaign focuses on classic cyber espionage.

## How the attack worked

The emails carried subjects like "Updated tax rates for Q2 2024" or "Urgent: Payment delay notice." The PDFs themselves were weaponized using a technique called geofencing: they only delivered the malicious payload if the victim’s device was on a Ukrainian network. This trick helps attackers avoid detection by security tools that scan from outside the country and reduces the chance of exposing their infrastructure to researchers. Once the PDF was opened, it exploited a now-patched Adobe Reader vulnerability, tracked as CVE-2023-26369, to run a PowerShell script. That script pulled Cobalt Strike from a compromised Ukrainian website and installed it on the victim’s machine.

Cobalt Strike is a commercial penetration testing tool that’s frequently repurposed by hackers. In this case, the attackers configured it to collect screenshots, log keystrokes, and exfiltrate files back to command-and-control servers hosted on bulletproof hosting providers in Russia. The goal appears to be long-term access to government networks, not a quick data grab. Researchers at ESET, who spotted the campaign, say the attackers spent weeks setting up infrastructure that mimics legitimate Ukrainian domains to trick staff.

## Who’s behind Ghostwriter

Ghostwriter’s links to Belarus come from multiple sources. Cybersecurity firms point to Belarusian IP addresses used during attacks, shared malware samples with Belarusian-language strings, and ties to known Belarusian hacktivist groups. Belarus has repeatedly denied involvement in cyber operations against Ukraine, but the country’s proximity and political alignment make it a natural staging ground. The group has also targeted Lithuania, Poland, and Germany in the past, usually around politically sensitive events like elections or NATO summits.

Ukraine’s cyber defense agency, CERT-UA, issued a warning about Ghostwriter’s latest tactics on May 29, 2024. CERT-UA urged government employees to verify unexpected attachments and disable macros in Office files. Microsoft added detection signatures for the Cobalt Strike payloads to its Defender suite the same week. Still, some analysts worry the group’s use of geofenced PDFs means many attacks still slip through undetected.

## What’s next

Experts expect Ghostwriter to keep refining its techniques. The group has already shifted from phishing emails to compromised websites and fake log-in pages in past campaigns. Security teams in Ukraine and NATO countries are sharing indicators of compromise and running tabletop exercises to prepare for further intrusions. The broader trend shows state-aligned hackers increasingly blending cyber espionage with disinformation, making it harder to separate data theft from influence operations. For Ukrainian officials, the lesson is clear: verify every unexpected document, even if it looks official, and assume attackers will keep adapting.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/ghostwriter-targets-ukrainian.html)
- **Published:** May 14, 2026 at 14:00 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #phishing · #ghostwriter-targets-ukrainian · #government-with-geofenced

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/ghostwriter-targets-ukrainian.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 14, 2026*


---

## 🇧🇷 Resumo em Português

O grupo de hackers pró-Rússia *Ghostwriter*, com base na Bielorrússia, inovou em suas táticas de ciberespionagem ao usar *phishing* com PDFs geolocalizados para atingir órgãos governamentais da Ucrânia, segundo revelou uma análise recente de segurança. A estratégia, que envolve o envio de arquivos maliciosos atrelados a coordenadas geográficas específicas, marca uma evolução nos ataques digitais durante a guerra, demonstrando como grupos cibercriminosos adaptam suas ferramentas para maximizar o impacto em conflitos geopolíticos.

No Brasil, a notícia ganha relevância pelo crescente número de ciberataques contra instituições públicas e privadas no país, especialmente em um cenário de polarização política e tensões internacionais. O uso de técnicas como *phishing* e *Cobalt Strike* — ferramenta de *penetration testing* comumente explorada por hackers — reforça a necessidade de o Brasil fortalecer suas defesas digitais, sobretudo em um ano eleitoral crucial. Especialistas alertam que grupos estrangeiros, como o *Ghostwriter*, podem mirar em alvos brasileiros se o país se envolver em disputas geopolíticas indiretas, exigindo vigilância redobrada em setores estratégicos.

O episódio serve como alerta: o Brasil precisa investir não apenas em tecnologias de defesa, mas também em treinamento de profissionais e cooperação internacional para evitar que se torne um novo campo de batalha virtual.
