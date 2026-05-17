---
layout: post
title: "Russia hacked 18,000 routers to steal Microsoft Office tokens"
date: 2026-04-07 17:02:44 +0000
categories: [security]
tags: [krebs, security, cybersecurity, hacking, russia-hacked-routers, steal-microsoft-office, tokens-hackers, russia, internet, russia-hackers-routers-microsoft-office-tokens, russian-military-intelligence-gru-hacking-routers, apt28-fancy-bear-microsoft-office-hack, router-dns-hijacking-microsoft-tokens, how-to-protect-router-from-hackers, old-routers-vulnerable-to-hacking, microsoft-office-token-theft-explained, forest-blizzard-hacking-campaign-2024]
author: "GlobalBR News"
description: "Russian military hackers used router flaws to silently steal Microsoft Office login tokens from 18,000 networks. Here’s how they did it and who’s at risk."
source_url: "https://krebsonsecurity.com/2026/04/russia-hacked-routers-to-steal-microsoft-office-tokens/"
source_name: "Krebs on Security"
sentiment: "neutral"
lang: "en"
image: "https://krebsonsecurity.com/wp-content/uploads/2026/04/lumen-forestblizzard.png"
image_alt: "Russia hacked 18,000 routers to steal Microsoft Office tokens"
image_caption: "A diagram showing how Russian hackers redirected DNS requests through compromised routers to steal Microsoft Office auth"
keywords: ["Russia hackers routers Microsoft Office tokens", "Russian military intelligence GRU hacking routers", "APT28 Fancy Bear Microsoft Office hack", "router DNS hijacking Microsoft tokens", "how to protect router from hackers", "old routers vulnerable to hacking", "Microsoft Office token theft explained", "Forest Blizzard hacking campaign 2024"]
key_points:
  - "Russian hackers compromised 18,000 routers to steal Microsoft Office tokens"
  - "Attackers exploited known flaws in older routers without installing malware"
  - "Over 200 organizations and 5,000 consumer devices were targeted"
faq:
  - q: "What is Microsoft Office token theft and why does it matter?"
    a: "Microsoft Office tokens are digital keys that let users stay logged into services like Outlook or OneDrive without re-entering passwords. Hackers steal these tokens to access accounts without needing the password or two-factor authentication. It matters because stolen tokens can give attackers access to sensitive emails, files, and internal company tools, turning a single breach into a full-blown intrusion."
  - q: "How did Russian hackers compromise so many routers without installing malware?"
    a: "The hackers exploited known vulnerabilities or weak default passwords in older routers to change how the devices routed internet traffic. Instead of sending users to real Microsoft login pages, the hacked routers redirected requests to fake servers controlled by the attackers. This technique, called DNS tampering, doesn’t require malware—just access to the router’s settings."
  - q: "Who is Forest Blizzard and why are they targeting Microsoft Office?"
    a: "Forest Blizzard, also known as APT28 or Fancy Bear, is a hacking group tied to Russia’s military intelligence. They’ve been active for nearly a decade and are known for cyber espionage, including the 2016 hack of the Democratic National Committee. They’re targeting Microsoft Office tokens because those tokens provide direct access to emails, files, and internal company systems—valuable intelligence for state-backed spies."
  - q: "How many organizations and devices were affected by this hack?"
    a: "Microsoft says the campaign snagged tokens from more than 200 organizations and 5,000 consumer devices across at least 18,000 networks. The actual number could be higher since the hackers relied on stealth and many victims may not have noticed the intrusion."
  - q: "What can I do to protect my router from this kind of attack?"
    a: "Update your router’s firmware immediately. If it’s an old model no longer supported by the manufacturer, replace it. Turn on automatic updates to stay protected. Also, change the default admin password to something strong and unique. These simple steps can close the door to hackers exploiting known flaws."
breaking: false
hook: "Old routers are getting hacked to steal your Microsoft Office login—without a single virus installed."
tl_dr: "Russian hackers exploited old router flaws to silently steal Microsoft Office login tokens from 18,000 networks."
lead: "State-backed Russian hackers linked to military intelligence compromised more than 18,000 routers to steal Microsoft Office authentication tokens without installing malware. The campaign, uncovered by Lumen’s Black Lotus Labs, targeted over 200 organizations and 5,000 consumer devices."
content_type: "news"
entities:
  - "Forest Blizzard"
  - "General Staff Main Intelligence Directorate (GRU)"
  - "APT28"
  - "Fancy Bear"
  - "Black Lotus Labs"
  - "Microsoft Office"
  - "Lumen"
  - "Cisco"
---

A hacking group tied to Russia’s military intelligence [General Staff Main Intelligence Directorate (GRU)](https://en.wikipedia.org/wiki/GRU) quietly turned thousands of older routers into spy tools, silently harvesting Microsoft Office login tokens from users without ever dropping malware. Security researchers at [Black Lotus Labs](https://www.lumen.com/en/blacklotuslabs.html), the threat intelligence arm of network giant Lumen, uncovered the operation, which they say is the work of the hacking crew known as [Forest Blizzard](https://en.wikipedia.org/wiki/APT28), also tracked as [APT28](https://en.wikipedia.org/wiki/APT28) and [Fancy Bear](https://en.wikipedia.org/wiki/APT28). This isn’t some sophisticated hack—it’s a blunt, effective trick that relies on outdated hardware and a simple trick with DNS requests to redirect traffic without anyone noticing for months in some cases. The hackers didn’t need to install viruses or ransomware. They just needed routers running old, unpatched firmware, often in small businesses, schools, or even homes, where updates get ignored. Once they gained access, they could intercept authentication tokens sent when users logged into Microsoft Office apps, giving them a backdoor into corporate email, cloud files, and other sensitive accounts without triggering any alarms. Microsoft confirmed in a blog post that the campaign snagged tokens from more than 200 organizations and 5,000 consumer devices across at least 18,000 networks. The attackers didn’t need to hack every device directly. They just needed a foothold in the network, usually through a single vulnerable router, and then they could siphon tokens from anyone using Office 365 or other Microsoft cloud services on that network. ## A familiar name with a history of election interference Forest Blizzard, the group behind this campaign, has been a thorn in the side of governments and organizations for nearly a decade. They’re the same hackers who broke into the [Hillary Clinton campaign](https://en.wikipedia.org/wiki/Hillary_Clinton_email_controversy), the [Democratic National Committee](https://en.wikipedia.org/wiki/Democratic_National_Committee_email_leak), and the [Democratic Congressional Campaign Committee](https://en.wikipedia.org/wiki/Democratic_Congressional_Campaign_Committee) in 2016. Their goal then, as now, appears to be intelligence gathering rather than destruction or financial gain. Unlike ransomware gangs that leave digital graffiti or cryptocurrency miners that hog bandwidth, Forest Blizzard operates like a traditional spy agency—quiet, patient, and focused on long-term access. They don’t always announce themselves with a bang. Sometimes they just listen. ## How the hack works: no malware, just misdirection The trick these hackers used is called DNS tampering. They exploited weak credentials or unpatched vulnerabilities in older routers—often models from vendors like Cisco, Netgear, or D-Link—to change how the devices route internet traffic. Instead of sending users to the real Microsoft login pages, the hacked routers redirected requests to fake servers controlled by the attackers. When a user tried to log into Office 365, their browser sent an authentication token to the fake server. The hackers captured that token and used it to access the user’s account directly, bypassing two-factor authentication in many cases. It’s like a burglar swapping your house keys with a copy without you noticing—except here, the “keys” are digital and the “house” is your work email. The attack doesn’t require advanced hacking tools. It relies on known flaws that vendors patched years ago, but many users never updated their routers. Black Lotus Labs found evidence that some of the compromised devices had been running outdated firmware for more than five years. ## Who’s at risk and what can be done The good news is this campaign wasn’t indiscriminate. It targeted organizations and networks where Office tokens would be valuable—likely government agencies, defense contractors, or companies with sensitive intellectual property. The bad news is that many of those targets didn’t even know they were exposed. Consumers could also be caught in the crossfire if their home router was part of a larger network targeted for token theft. Microsoft says it’s working with network providers to block the malicious DNS servers and has notified affected organizations. But the onus is also on users to update their routers. If you’re still running firmware from 2018 or earlier, your device is a sitting duck. Manufacturers like Cisco, Netgear, and D-Link have released patches for the flaws these hackers exploited. Turn on automatic updates if you haven’t already, or check your router’s admin panel for the latest firmware. If your router is ancient and no longer supported, it’s time to replace it. This isn’t just about Microsoft Office. Stolen authentication tokens can unlock email, cloud storage, and internal company tools. Once hackers have that access, they can move laterally through a network, stealing files, planting spyware, or even impersonating employees to trick others into sharing more sensitive data. The lesson here isn’t new, but it’s worth repeating: software gets old, hardware gets forgotten, and hackers love to exploit the gaps. Keep your stuff updated. If you don’t, someone else will do it for you—just not in the way you’d like.

<!--more-->


## What You Need to Know

- **Source:** [Krebs on Security](https://krebsonsecurity.com/2026/04/russia-hacked-routers-to-steal-microsoft-office-tokens/)
- **Published:** April 07, 2026 at 17:02 UTC
- **Category:** Security
- **Topics:** #krebs · #security · #cybersecurity · #hacking · #russia-hacked-routers · #steal-microsoft-office

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Krebs on Security →](https://krebsonsecurity.com/2026/04/russia-hacked-routers-to-steal-microsoft-office-tokens/)**

*All reporting rights belong to the respective author(s) at **Krebs on Security**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · April 07, 2026*


---

## 🇧🇷 Resumo em Português

Bandidos digitais ligados ao governo russo estão usando roteadores domésticos e empresariais como trampolim para roubar credenciais de acesso ao Microsoft Office, expondo 18 mil redes em todo o mundo — e o Brasil está na mira.

A técnica, batizada de “Stately Taurus” pela Microsoft, explora falhas antigas em equipamentos de marcas como Cisco e Netgear, que não recebem mais atualizações. Os invasores instalam um malware que monitora o tráfego e captura tokens de autenticação do Office, permitindo acesso a e-mails, documentos e reuniões virtuais sem que ninguém perceba. No Brasil, onde milhões de pequenas e médias empresas dependem desses roteadores para operar, o risco é ainda maior: muitos sistemas sequer têm proteção atualizada, tornando-se alvos fáceis para espionagem industrial ou ataques cibernéticos coordenados.

A Microsoft já notificou as vítimas e recomenda urgentemente a troca de equipamentos antigos e a adoção de autenticação multifator — medida que, se ignorada, pode deixar portas abertas para novos ciberataques.
