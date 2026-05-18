---
layout: post
title: "⚡ Weekly Recap: Linux Rootkit, macOS Crypto Stealer, WebSocket Skimmers and More"
date: 2026-05-11 12:36:00 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, weekly-recap, linux-rootkit, crypto-stealer, socket-skimmers, more-rough-monday, linux-rootkit-2024, macos-crypto-stealer, websocket-skimmers, e-commerce-security-threats, cloud-misconfiguration-breaches, how-to-protect-linux-servers-from-rootkits, macos-malware-2024, real-time-payment-skimming]
author: "GlobalBR News"
description: "Linux rootkits, macOS crypto stealers, and WebSocket skimmers topped this week’s security threats. Here’s what happened and why it matters."
source_url: "https://thehackernews.com/2026/05/weekly-recap-linux-rootkit-macos-crypto.html"
source_name: "The Hacker News"
sentiment: "negative"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiD4a3gzeAEAv4Bs5FqWbHG1cRyNqIOjygeSxxpNoChwyyMUWlbZHzkG0n8ysGpoAYuKqklfMtTKRct0OeYktaKLhdXpRH5pKH94tVaMX7iPeNDf7vZjFky3myBkFPJPl1xIdsWDlIYP30IeR7IZGhQZ5p82yHRdRO1OGkpAtTWgZcQSG3zXqh9tLbSSrgP/s1600/cyber-recap.jpg"
image_alt: "⚡ Weekly Recap: Linux Rootkit, macOS Crypto Stealer, WebSocket Skimmers and More"
image_caption: "A stylized illustration of a Linux terminal with a skull-and-crossbones symbol overlaying a server rack, representing th"
keywords: ["Linux rootkit 2024", "macOS crypto stealer", "WebSocket skimmers", "e-commerce security threats", "cloud misconfiguration breaches", "how to protect Linux servers from rootkits", "macOS malware 2024", "real-time payment skimming"]
key_points:
  - "Linux rootkit spread after someone gained root access by accident"
  - "macOS malware stole crypto wallets by spoofing legitimate apps"
  - "WebSocket skimmers compromised 200+ e-commerce sites"
faq:
  - q: "What is a Linux rootkit and how does it work?"
    a: "A Linux rootkit is malware that gives attackers full control over a system after gaining root access. In this case, the attacker exploited a misconfigured SSH port, installed the rootkit, and turned the machine into a botnet node. Rootkits hide in the operating system to avoid detection, making them hard to remove."
  - q: "How did the macOS crypto stealer bypass Apple’s security checks?"
    a: "The malware, called MacStealer, mimicked popular apps like Notion and Tor Browser. It had valid developer signatures, which tricked Apple’s Gatekeeper system into allowing the fake apps. Victims downloaded them from third-party sites, thinking they were legitimate, and the malware stole private keys to empty crypto wallets."
  - q: "What are WebSocket skimmers and how do they steal payment data?"
    a: "WebSocket skimmers are malicious JavaScript injected into e-commerce sites. They abuse unsecured WebSocket connections to copy payment card data in real time. Attackers target sites using WebSockets for live chat but don’t secure the endpoints, letting them siphon data to remote servers without raising alarms."
  - q: "Why are old bugs like the 2017 Telerik flaw still causing breaches in 2024?"
    a: "Thousands of servers still run unpatched software because admins ignore updates. The 2017 Telerik flaw lets attackers hijack .NET apps to drop ransomware. Despite patches being available for seven years, scans still find 12,000+ vulnerable servers, proving old bugs never die if ignored."
  - q: "What’s the easiest way for cloud teams to prevent breaches?"
    a: "Cloud breaches often start with misconfigurations like public S3 buckets or exposed API keys. Teams should use built-in tools like AWS Config, Azure Policy, or GCP’s Security Command Center to scan for leaks. The fix? Lock down permissions, enable logging, and review configs weekly—before attackers do."
breaking: false
hook: "Someone got root access by accident—and turned Linux servers into malware hubs."
tl_dr: "Linux rootkits, macOS crypto stealers, and WebSocket skimmers hit hard this week."
lead: "Someone accidentally got root access on Linux, kept it, and turned servers into playgrounds. Meanwhile, a macOS crypto stealer slipped through Apple’s defenses, and WebSocket skimmers hit 200+ e-commerce sites. It’s been a messy week."
content_type: "news"
entities:
  - "Linux"
  - "macOS"
  - "WebSocket"
  - "Telerik UI"
  - "Gatekeeper"
  - "SSH"
  - "S3 bucket"
---

A security report this week showed how someone tripped over root access on a Linux server and just stayed there. They turned the machine into a botnet node, using it to spread malware. The access path? A misconfigured SSH port that should’ve been firewalled years ago. It’s the kind of hole that makes sysadmins groan—easy to fix, easy to overlook, and now being exploited in the wild. [Linux](https://en.wikipedia.org/wiki/Linux) systems running outdated kernels are the main targets, and the rootkit’s still spreading because admins haven’t patched since 2020. ## macOS users lost $1.2M to fake crypto apps this week. A new malware family called *MacStealer* snuck past Apple’s notarization checks by mimicking popular apps like *Notion* and *Tor Browser*. Victims downloaded the fake apps from third-party sites, and once installed, the malware emptied wallets by copying private keys. Apple’s [Gatekeeper](https://support.apple.com/en-us/HT202491) system didn’t flag it because the apps had valid developer signatures—just not from the apps they claimed to be. The scam’s simple: trick users into downloading what looks real, then steal everything. ## WebSocket skimmers hit 200+ stores in one weekend. Attackers injected malicious JavaScript into 200+ e-commerce sites by abusing unsecured WebSocket connections. The skimmers copied payment card data in real time, sending it to servers controlled by the criminals. The trick? Sites used WebSockets for live chat but left the endpoints exposed. Some stores didn’t even notice until customers reported fraud. The attack started Friday and peaked Sunday, showing how weekend traffic makes it easier to hide. ## Old bugs never die. A 2017 flaw in [Telerik UI](https://www.telerik.com/) components is still letting attackers into corporate networks. Microsoft’s [Patch Tuesday](https://learn.microsoft.com/en-us/security-updates/securitybulletins/2024/ms24-035) this week warned that unpatched servers are being hijacked to drop ransomware. The bug’s in a .NET library used by thousands of apps, and the fix’s been out for seven years. Yet, scans still find 12,000+ vulnerable servers online. ## Cloud misconfigs are still the biggest door opener. A new report found that 68% of cloud breaches start with a simple config mistake—like leaving an S3 bucket public or an API key exposed. Most teams fix it after it’s too late. AWS, Azure, and GCP all have tools to spot these leaks, but users keep ignoring the warnings. The worst part? The breaches don’t stop at data leaks. Often, attackers use the access to spin up crypto miners or ransomware droppers. ## What’s next? Security teams are scrambling to patch old holes, but attackers are moving faster. Linux admins need to audit SSH configs. macOS users should only download apps from the App Store or trusted developers. E-commerce sites must lock down WebSocket endpoints. And cloud teams? Stop leaving the doors unlocked. The pattern’s the same every week: the same old holes, the same lazy access paths, and the same ‘how is this still happening’ feeling.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/weekly-recap-linux-rootkit-macos-crypto.html)
- **Published:** May 11, 2026 at 12:36 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #weekly-recap · #linux-rootkit · #crypto-stealer

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/weekly-recap-linux-rootkit-macos-crypto.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 11, 2026*
