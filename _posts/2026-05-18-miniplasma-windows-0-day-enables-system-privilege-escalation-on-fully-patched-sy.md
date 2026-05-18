---
layout: post
title: "MiniPlasma Windows 0-Day Enables SYSTEM Privilege Escalation on Fully Patched Systems"
date: 2026-05-18 08:57:34 +0000
categories: [security]
tags: [hackernews, security, vulnerabilities, vulnerability, mini, plasma-windows, day-enables, privilege-escalation, fully-patched-systems, windows-zero-day-exploit, miniplasma-vulnerability, chaotic-eclipse-security-flaw, windows-system-privilege-escalation, cldfltsys-exploit, windows-cloud-files-mini-filter-driver-bug, how-to-protect-from-miniplasma, windows-privilege-escalation-zero-day, fully-patched-windows-vulnerable, emergency-windows-patch-guide]
author: "GlobalBR News"
description: "A new Windows zero-day flaw called MiniPlasma lets attackers gain full SYSTEM privileges on fully patched PCs. Here's what we know so far."
source_url: "https://thehackernews.com/2026/05/miniplasma-windows-0-day-enables-system.html"
source_name: "The Hacker News"
sentiment: "positive"
lang: "en"
last_updated: "2026-05-18"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjvmx8dRRiQKx4cT0aT1-zTuzdjfThwxmlbzb2ikeeqIXUXGdcJhRrq4BykcdBB572URpoAHQhSTSyahR3M7TyvOsLSCekQGCUFM8sTcdsxkrpRFrT41wF8EqKA5LjzYHpzUtro2136Iy55cKQ_wixFUSsFDnilkUNCvrDvJbHBKK3k_IelHt9lOmbW01_u/s1600/windows-exploits.jpg"
image_alt: "MiniPlasma Windows 0-Day Enables SYSTEM Privilege Escalation on Fully Patched Systems"
image_caption: "A stylized Windows 10 desktop with a glowing red SYSTEM icon over the taskbar, symbolizing the MiniPlasma zero-day privi"
keywords: ["Windows zero-day exploit", "MiniPlasma vulnerability", "Chaotic Eclipse security flaw", "Windows SYSTEM privilege escalation", "cldflt.sys exploit", "Windows Cloud Files Mini Filter Driver bug", "how to protect from MiniPlasma", "Windows privilege escalation zero-day"]
key_points:
  - "MiniPlasma zero-day gives attackers SYSTEM privileges on patched Windows PCs"
  - "Bug lives in Windows Cloud Files Mini Filter Driver (cldflt.sys)"
  - "Proof-of-concept code released by researcher Chaotic Eclipse"
faq:
  - q: "What is MiniPlasma and how does it work?"
    a: "MiniPlasma is a zero-day Windows flaw that lets attackers escalate from basic user rights to SYSTEM privileges. It abuses the Cloud Files Mini Filter Driver (cldflt.sys) by tricking Windows into running malicious code during file sync operations. The exploit doesn’t require admin rights to start and works on fully patched systems."
  - q: "Which Windows versions are affected by MiniPlasma?"
    a: "MiniPlasma affects fully patched Windows 10 and 11 systems. The bug lives in the Cloud Files Mini Filter Driver, which is a core component in modern Windows versions that handle cloud file syncing like OneDrive and SharePoint."
  - q: "Has MiniPlasma been seen in real-world attacks?"
    a: "As of now, there’s no confirmed evidence of MiniPlasma being exploited in the wild. However, the PoC is public, so attackers could reverse-engineer it and craft their own exploits quickly. Security teams recommend treating it as a critical risk until patched."
  - q: "Can I disable the Cloud Files Mini Filter Driver to protect myself?"
    a: "Disabling the Cloud Files Mini Filter Driver isn’t recommended—it breaks cloud sync features like OneDrive. Instead, keep an eye out for an emergency Microsoft patch. In the meantime, restrict driver installations and monitor for unusual file sync activity."
  - q: "What should I do right now if I’m worried about MiniPlasma?"
    a: "Apply Windows updates as soon as they’re available, especially any emergency patches Microsoft releases. Keep your antivirus updated, avoid downloading untrusted files, and enable features like Credential Guard to reduce the risk of privilege escalation."
featured: true
breaking: true
hook: "Windows zero-day MiniPlasma lets hackers take full control—even on patched PCs."
tl_dr: "MiniPlasma zero-day lets attackers grab full SYSTEM rights on patched Windows PCs — patch now if available."
lead: "Security researcher Chaotic Eclipse released a proof-of-concept for MiniPlasma, a Windows zero-day flaw that lets attackers escalate privileges to SYSTEM on fully patched systems. The bug lives in the Cloud Files Mini Filter Driver, a core Windows component."
content_type: "breaking"
entities:
  - "Chaotic Eclipse"
  - "Windows Cloud Files Mini Filter Driver"
  - "Microsoft"
  - "cldflt.sys"
  - "The Hacker News"
---

> 📰 **Continuing coverage:** [Windows Zero-Days Expose BitLocker Bypasses And CTFMON Privilege Escalation](/security/2026/05/14/windows-zero-days-expose-bitlocker-bypasses-and-ctfmon-privilege-escalation/)

A fresh Windows zero-day is out, and it’s bad. Security researcher Chaotic Eclipse—who recently exposed the YellowKey and GreenPlasma flaws—has dropped a proof-of-concept (PoC) for MiniPlasma, a privilege escalation bug that hands attackers full SYSTEM rights on fully patched Windows machines. The flaw lives in cldflt.sys, the Windows Cloud Files Mini Filter Driver, a core component that handles syncing files to the cloud. That makes it a juicy target—attackers don’t need a phishing email or a dodgy app to exploit it. Just a vulnerable system and the right exploit code, and they’re in deep.

## What’s MiniPlasma and why does it matter?

MiniPlasma (CVE still pending) isn’t just another bug. It’s a zero-day, meaning Microsoft didn’t know about it until it was weaponized. Even fully patched Windows 10 and 11 systems are vulnerable right now. The PoC shows how an attacker with basic user rights can escalate those rights to SYSTEM—Windows’ highest privilege level. That’s the kind of access that lets hackers install malware, disable security tools, or steal every password on the machine. And because it’s in a Microsoft driver, it’s not something you can just uninstall or block with a firewall.

The timing stings. Chaotic Eclipse dropped this PoC just weeks after Microsoft’s June Patch Tuesday, which fixed a record 140+ vulnerabilities. That means MiniPlasma slipped through Microsoft’s usual screening process, likely because it abuses a legitimate driver function in an unexpected way. Researchers say it leverages the driver’s built-in file syncing features to trick Windows into running malicious code at SYSTEM level. No admin rights needed for the initial breach—just the right exploit string.

## Who’s at risk and how bad is this?

Right now, anyone running a fully patched Windows 10 or 11 system is at risk—unless Microsoft pushes an emergency patch. Home users, businesses, and even cloud services that rely on Windows file syncing could be targeted. The PoC is public, so skilled attackers can reverse-engineer it and craft their own exploits. Even script kiddies could get a hold of it if it’s leaked into underground forums.

Security teams are already sounding the alarm. The [Cloud Files Mini Filter Driver](https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/cloud-files-mini-filter-driver) is a critical part of Windows’ file system, and disabling it isn’t an option—it breaks OneDrive, SharePoint, and other cloud sync features. That leaves admins with a tough choice: patch fast or disable cloud sync entirely to reduce the attack surface. But disabling sync isn’t practical for most users, so patching is the only real solution.

## What’s next? Microsoft’s response and workarounds

Microsoft hasn’t commented yet, but they’re likely scrambling right now. Zero-days usually get a patch within days if they’re actively exploited in the wild. Until then, users should treat this like any other critical vulnerability: assume it’s being exploited, minimize risk, and keep an eye out for an emergency update. Chaotic Eclipse told The Hacker News they’ll share more details after Microsoft fixes it, but for now, the PoC is out there for anyone to use.

In the meantime, admins can tighten defenses by restricting who can install drivers, enabling Credential Guard, and monitoring for unusual file sync activity. Home users should avoid downloading untrusted files and keep their antivirus updated. If Microsoft drags its feet, expect a third-party patch or a workaround from security vendors. But don’t wait too long—this one’s serious.

This isn’t just another bug. It’s a reminder that even fully patched systems can be vulnerable when attackers find clever ways to abuse legitimate features. And with the PoC already public, the clock is ticking for Microsoft to act.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/miniplasma-windows-0-day-enables-system.html)
- **Published:** May 18, 2026 at 08:57 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #vulnerability · #mini · #plasma-windows

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/miniplasma-windows-0-day-enables-system.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 18, 2026*
