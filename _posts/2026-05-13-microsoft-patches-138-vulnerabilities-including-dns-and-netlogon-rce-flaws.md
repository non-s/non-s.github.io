---
layout: post
title: "Microsoft Patches 138 Vulnerabilities, Including DNS and Netlogon RCE Flaws"
date: 2026-05-13 10:36:10 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, microsoft-patches, including, netlogon, flaws-microsoft, microsoft-patch-tuesday-july-2024, windows-dns-vulnerability-cve-2024-38080, netlogon-rce-flaw-cve-2024-38021, microsoft-security-updates-july-2024, windows-server-vulnerabilities-july-2024, remote-code-execution-in-dns, netlogon-authentication-bypass, how-to-patch-windows-july-2024]
author: "GlobalBR News"
description: "Microsoft’s Patch Tuesday drops fixes for 138 vulnerabilities, including two dangerous remote code execution flaws in DNS and Netlogon."
source_url: "https://thehackernews.com/2026/05/microsoft-patches-138-vulnerabilities.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjk3m3CoTiKH2QVXSFAOVKKnTl-Ybt1FDE4M7BGK_ujskSYNQ8pOlcvZfyNv8CW2EJIVdMQaORcCE0H-_ufTvD6hR-LOOZ64GZPS_9bH7YrE4i0r4LrGCn7vXmG0GjpFk8aNlRR_4_GjrM-jhXBS1NzIbYiRydcmiNSXIV2eUczvgjGmp34_gNz3M5kt-Jf/s1600/windows-patch-update.jpg"
image_alt: "Microsoft Patches 138 Vulnerabilities, Including DNS and Netlogon RCE Flaws"
image_caption: "A close-up of a laptop screen showing the Windows Update settings with the Patch Tuesday notification visible in the sys"
keywords: ["Microsoft Patch Tuesday July 2024", "Windows DNS vulnerability CVE-2024-38080", "Netlogon RCE flaw CVE-2024-38021", "Microsoft security updates July 2024", "Windows Server vulnerabilities July 2024", "remote code execution in DNS", "Netlogon authentication bypass", "how to patch Windows July 2024"]
key_points:
  - "Microsoft fixes 138 vulnerabilities in monthly Patch Tuesday update"
  - "Two critical flaws allow remote code execution in DNS and Netlogon"
  - "No active attacks reported, but patching is still urgent"
faq:
  - q: "What are the most dangerous bugs in Microsoft’s latest Patch Tuesday update?"
    a: "The two critical remote code execution flaws are the biggest risks. One is in Windows DNS (CVE-2024-38080) and the other in Netlogon (CVE-2024-38021). Both let attackers run code without user interaction and have a severity score of 9.8 out of 10. Microsoft calls them 'Exploit More Likely,' meaning hackers could weaponize them soon."
  - q: "Do any of these vulnerabilities have active exploits in the wild?"
    a: "No. Microsoft says none of the 138 flaws are known to be exploited yet. But the company’s threat modeling labels the DNS and Netlogon bugs as 'Exploit More Likely,' which usually means attackers will figure them out within days or weeks after the patches drop."
  - q: "Which Windows versions are affected by the DNS and Netlogon flaws?"
    a: "The DNS flaw (CVE-2024-38080) affects all supported Windows Server versions from 2012 R2 onward. The Netlogon bug (CVE-2024-38021) impacts Windows Server 2008 R2 and newer. Home users running Windows 10 or 11 are only at risk if they’ve manually enabled the vulnerable Netlogon service."
  - q: "How quickly should I install these patches?"
    a: "Patch these updates immediately, especially if you run a domain controller or a server with DNS enabled. Both critical flaws let hackers take over systems without any user interaction, and Microsoft warns they could spread fast in corporate networks. For most users, Windows Update will roll this out automatically within a few days."
  - q: "Are there any known issues with these patches?"
    a: "Microsoft notes potential problems with the DNS patch on some domain controllers running older builds of Windows Server 2012 R2. Check the known issues list before deploying if your domain controllers are still on that version. Some admins also report issues with .NET Framework updates and third-party security tools after recent Patch Tuesdays."
breaking: false
hook: "Microsoft just dropped 138 fixes, two of which could let hackers take over your servers without you even knowing."
tl_dr: "Microsoft patches 138 flaws this month, including two critical remote code execution bugs in DNS and Netlogon services."
lead: "Microsoft just pushed out fixes for 138 security flaws across its products, including two critical remote code execution vulnerabilities in DNS and Netlogon services. None of the bugs are known to be exploited yet, but admins should patch quickly."
content_type: "news"
entities:
  - "Microsoft"
  - "Windows"
  - "Windows Server"
  - "Windows DNS"
  - "Netlogon"
  - "CVE-2024-38080"
  - "CVE-2024-38021"
  - "Patch Tuesday"
---

Microsoft rolled out its monthly security patch bundle on Tuesday, fixing 138 vulnerabilities across Windows, Office, Azure and other products. The update includes two critical remote code execution flaws that could let hackers take over servers without any user interaction. One bug lives in the Windows DNS service, the other in the Netlogon protocol used by Windows domains to authenticate machines and users. Neither flaw is known to be exploited in the wild yet, but both have a severity rating of 9.8 out of 10, the highest possible score. That means if you run a domain controller or a server with DNS enabled, this update should be at the top of your to-do list. Microsoft labels these bugs as "Exploit More Likely" in its threat modeling, which is usually a strong signal that someone will weaponize them soon. The DNS flaw (CVE-2024-38080) lets an attacker send a malformed query to a vulnerable server and run their own code on it. The Netlogon issue (CVE-2024-38021) involves how the protocol handles cryptographic operations, letting an unauthenticated attacker gain domain admin rights if they can connect to a domain controller. Even if you don’t run a domain, patch your DNS servers. The other 136 fixes cover everything from privilege escalation in Windows kernel drivers to spoofing in Outlook and memory leaks in Azure Functions. Only three bugs are rated Moderate and one Low, but the sheer volume of privilege escalation flaws—61 in total—means attackers could chain several together to move from a low-level user to full system control. Microsoft didn’t mark any of these as publicly known before the patch, which is unusual. Usually at least one bug gets leaked or picked up by threat researchers before the update drops. That silence might mean the flaws are fresh discoveries or that attackers haven’t started probing them yet. Still, history shows that when Microsoft issues a bundle this big, someone will reverse-engineer the fixes within days and craft exploits. The company’s own advisory warns that the DNS and Netlogon flaws should be prioritized because they don’t require user interaction and could spread fast in corporate networks. The DNS bug affects all supported Windows Server versions from 2012 R2 onward, while the Netlogon issue impacts Windows Server 2008 R2 and newer. Home users running Windows 10 or 11 are only at risk if they’ve manually enabled the vulnerable Netlogon service, which is rare. For most people, the biggest risk comes from phishing emails that push malicious Office files exploiting the other 136 bugs. The update also includes fixes for two zero-days that were reported privately: one in the Windows Kernel (CVE-2024-38100) that could let attackers bypass security features, and another in the Windows Ancillary Function Driver (CVE-2024-38101) that could crash systems or run code. Neither is marked as under active attack, but both have a high severity score and should be patched promptly. If you manage servers, test the update in a non-production environment first. Some admins report issues with .NET Framework updates and certain third-party security tools after recent Patch Tuesdays. Microsoft’s release notes mention known problems with the DNS patch on some domain controllers running older builds. If your domain controllers are still on Windows Server 2012 R2, check the known issues list before deploying. For everyone else, Windows Update should roll this out automatically, but don’t let it sit for weeks. The DNS flaw alone could let an attacker take over a server and then move laterally across a network, stealing data or deploying ransomware. The Netlogon bug is even scarier because it hands over the keys to the kingdom—the domain admin account—with a single packet if the domain controller isn’t patched. Patch now, verify later, and keep an eye on threat intel feeds over the next few days. Someone will figure out how to weaponize these within a week.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/microsoft-patches-138-vulnerabilities.html)
- **Published:** May 13, 2026 at 10:36 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #microsoft-patches · #including · #netlogon

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/microsoft-patches-138-vulnerabilities.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 13, 2026*


---

## 🇧🇷 Resumo em Português

**Cibercriminosos podem ter uma segunda-feira agitada — e você também, se não atualizar seus sistemas agora.**

A gigante de tecnologia Microsoft encerrou a semana com um alerta importante para usuários e empresas brasileiras: nesta terça-feira, a empresa liberou atualizações para corrigir 138 vulnerabilidades em seus sistemas, duas delas críticas e capazes de permitir a execução remota de código (RCE). Entre os pontos mais preocupantes estão falhas no DNS, que afeta servidores de nomes de domínios, e no Netlogon, protocolo usado em redes corporativas para autenticação de usuários. No Brasil, onde a digitalização acelerou — especialmente em empresas e órgãos públicos — e o número de ataques cibernéticos cresce a cada ano, a demora em aplicar esses patches pode abrir portas para invasões, sequestro de dados ou até mesmo espionagem industrial.

A gravidade das vulnerabilidades exige atenção imediata, sobretudo porque o DNS e o Netlogon são componentes essenciais para a operação de muitos sistemas. Especialistas alertam que criminosos digitais já exploram falhas semelhantes em outras plataformas, e o cenário atual é propício para ciberataques em larga escala. Para o Brasil, que recentemente sofreu com casos emblemáticos como o sequestro de dados do Superior Tribunal de Justiça (STJ) e vazamentos em empresas de energia, a atualização dos sistemas não é apenas uma boa prática, mas uma necessidade urgente para evitar prejuízos milionários e danos à segurança nacional.

A Microsoft recomenda que usuários domésticos e corporativos instalem as atualizações o mais rápido possível, enquanto órgãos de segurança monitoram possíveis explorações nos próximos dias.
