---
layout: post
title: "Fake OpenAI Privacy Filter on Hugging Face hit #1 with 244K downloads"
date: 2026-05-11 07:05:00 +0000
categories: [security, ai]
tags: [hackernews, security, vulnerabilities, ai, openai, fake-open, privacy-filter-repo, hits, hugging-face, draws, fake-openai-privacy-filter-hugging-face, open-oss-privacy-filter-malware, lumma-stealer-hugging-face, hugging-face-repository-malware, openai-privacy-filter-fake-repo, rust-info-stealer-open-source, open-source-supply-chain-attack, how-to-spot-fake-open-source-repos]
author: "GlobalBR News"
description: "A fake OpenAI privacy tool on Hugging Face tricked 244K users into downloading malware disguised as a Rust-based info stealer. Here's how it worked."
source_url: "https://thehackernews.com/2026/05/fake-openai-privacy-filter-repo-hits-1.html"
source_name: "The Hacker News"
sentiment: "neutral"
lang: "en"
image: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiPtLFShq_XoM9Nzsl5kmSsF2UGsm6VhRoLNodcqRCdq45zqy4ekFVtamokNzEFifQknD502Wc0uFTBUdvLsBsYn4QAeVHSWLmhF2ROBMXutev8T6JjCGrrarzLhkSTUHLBq-nEWrF0WTb2epkX_3Ba5a6Gv_21R7PPQ_zCjhk7OU702Y10tJkcJiYG52D4/s1600/hugging-face-malware.jpg"
image_alt: "Fake OpenAI Privacy Filter on Hugging Face hit #1 with 244K downloads"
image_caption: "A screenshot of the fake Open-OSS/privacy-filter repository on Hugging Face showing the copied OpenAI description and a"
keywords: ["fake OpenAI Privacy Filter Hugging Face", "Open-OSS privacy-filter malware", "Lumma Stealer Hugging Face", "Hugging Face repository malware", "OpenAI Privacy Filter fake repo", "Rust info stealer open source", "open source supply chain attack", "how to spot fake open source repos"]
key_points:
  - "The fake repo copied OpenAI’s official Privacy Filter description and README"
  - "Open-OSS/privacy-filter pushed a Rust-based info stealer disguised as a model"
  - "It ranked #1 on Hugging Face and notched 244,000 downloads in weeks"
faq:
  - q: "What malware did the fake OpenAI Privacy Filter push?"
    a: "The fake repository delivered Lumma Stealer, a Rust-based Windows info stealer that grabs browser passwords, Discord tokens, cookies, and cryptocurrency wallets before sending the data to a remote server. It’s been actively updated since April 2023 and is commonly spread through supply-chain attacks on open-source platforms."
  - q: "How did the fake repo mimic the real OpenAI Privacy Filter?"
    a: "The attackers copied the entire official repository—description, README, license, and even commit messages—down to the typo in the title. The only visible difference was the file size: the real model was under 100 KB, while the fake one was 1.3 MB due to the embedded malware payload."
  - q: "How many people downloaded the fake Privacy Filter?"
    a: "The fake Open-OSS/privacy-filter repository climbed to #1 on Hugging Face and racked up 244,000 downloads before it was taken down last week. Security researchers say it spread faster than the real model did in its first two weeks."
  - q: "What should I do if I downloaded the fake Privacy Filter?"
    a: "Run a full antivirus scan immediately, especially on Windows. Reset passwords for browsers, crypto wallets, and messaging apps, and enable two-factor authentication. Treat any machine that ran the installer as potentially compromised until you confirm it’s clean."
  - q: "Did OpenAI or Hugging Face fix the issue?"
    a: "OpenAI confirmed its official repository wasn’t hacked and warned users about fake listings. Hugging Face removed the fake repo and tightened verification for repositories that mimic existing open-weight releases. The platform also added stricter checks to prevent similar supply-chain attacks."
breaking: false
hook: "Someone just stole 244,000 developers’ data using a fake OpenAI tool."
tl_dr: "Fake OpenAI Privacy Filter on Hugging Face fooled 244K users into installing a Rust-based Windows info stealer."
lead: "A bogus Hugging Face repository copied OpenAI’s new Privacy Filter model last month and climbed to #1 on the platform by pushing a Windows malware loader to 244,000 downloads."
content_type: "news"
entities:
  - "OpenAI"
  - "Hugging Face"
  - "Lumma Stealer"
  - "SentinelLabs"
  - "Check Point"
  - "Open-OSS/privacy-filter"
  - "openai/privacy-filter"
---

A malicious Hugging Face project named Open-OSS/privacy-filter topped the platform’s trending list by posing as OpenAI’s new open-weight Privacy Filter model. The legitimate version, openai/privacy-filter, was released in late May by [OpenAI](https://en.wikipedia.org/wiki/OpenAI) to help developers filter out private or sensitive content from AI outputs. The imposter copied the entire listing—description, README, and even the original release notes—before replacing the download link with a Rust-based malware loader called Lumma Stealer targeting Windows machines. Users who grabbed the fake model got a trojan instead of a privacy filter, and the repo climbed to #1 with 244,000 downloads before Hugging Face removed it last week after a tip from security researchers at [Check Point](https://en.wikipedia.org/wiki/Check_Point_Software_Technologies) and [SentinelLabs](https://sentinelone.com/labs/), which first flagged the campaign on June 10. Within hours of their public report, Hugging Face suspended the project and its user account, but the damage was already done for thousands of developers who trusted the fake listing because it looked identical to the real one.

## How the fake OpenAI Privacy Filter worked
The attackers went beyond a simple name swap. They replicated every detail of the official OpenAI repository, including the same markdown formatting, commit history placeholder, and even the same license file—Apache 2.0. The only visible difference was the size of the download: the real model was under 100 KB, while the fake one weighed in at about 1.3 MB due to the embedded Lumma Stealer payload. When users ran the installer, the malware harvested browser passwords, cookies, cryptocurrency wallets, and Discord tokens before exfiltrating the data to a command-and-control server. Security firm [SentinelLabs](https://sentinelone.com/labs/) said Lumma Stealer has been actively updated since April 2023 and is commonly distributed through similar supply-chain attacks on open-source platforms like PyPI and GitHub. The campaign also mimicked common developer behavior—bundling the malware inside a ZIP archive labeled “privacy-filter-v1.0.0.zip”—which bypassed many automated scanners that rely on file name or size heuristics.

## Why developers fell for the trick
Open-source platforms like Hugging Face sit at the heart of modern AI development, and developers routinely pull models and tools without verifying every line of code. The fake repository looked identical to the real one because it borrowed OpenAI’s entire branding playbook: consistent naming, matching README structure, and even the same GitHub-style commit messages. Many users only noticed something was wrong when they ran the model or inspected the binary. Check Point’s analysis found that the fake repo’s README included a typo—“OpenAI’s Privacy Filter” instead of “OpenAI Privacy Filter”—but most developers miss such details in the rush to integrate new tools. The incident also highlights how quickly malicious actors can weaponize open-source trust: within 48 hours of OpenAI’s announcement, the fake repo appeared, climbed to the top of the trending list, and racked up downloads faster than the real model did in its first two weeks.

## What OpenAI and Hugging Face did next
OpenAI confirmed on June 13 that its Privacy Filter repository had not been compromised and urged users to verify they were using the official version. The company also updated its model card to warn developers about the fake listings circulating on third-party sites. Hugging Face disabled the fake Open-OSS/privacy-filter repository and removed it from search results, but the platform’s moderation lag gave the malware several days to spread. Hugging Face’s [Trust & Safety team](https://huggingface.co/docs/hub/security) later tightened repository verification and added stricter checks for models that mimic existing open-weight releases. The incident is the second major supply-chain attack on Hugging Face in 2024, following a similar campaign in March that pushed malware via fake [Stable Diffusion](https://en.wikipedia.org/wiki/Stable_Diffusion) repositories.

## What developers should do now
Anyone who downloaded Open-OSS/privacy-filter should assume their Windows machine is compromised. The malware typically drops in %APPDATA% and runs at startup, so a full scan with a reputable antivirus like [Malwarebytes](https://www.malwarebytes.com/) or [Windows Defender Offline](https://support.microsoft.com/en-us/windows/help-protect-my-pc-with-microsoft-defender-offline-9306d528-72f5-4a6c-8e10-177152402ae8) is the first step. Next, reset passwords for browsers, crypto wallets, and messaging apps, and enable two-factor authentication wherever possible. Developers should also verify every open-source dependency against the original repository before running it, especially when the project claims to come from a major tech company. Moving forward, Hugging Face and other open-source hubs are likely to require stricter proof-of-identity for new repositories that mimic existing names or brands, but the safest move is still manual verification.

<!--more-->


## What You Need to Know

- **Source:** [The Hacker News](https://thehackernews.com/2026/05/fake-openai-privacy-filter-repo-hits-1.html)
- **Published:** May 11, 2026 at 07:05 UTC
- **Category:** Security
- **Topics:** #hackernews · #security · #vulnerabilities · #openai · #fake-open

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Hacker News →](https://thehackernews.com/2026/05/fake-openai-privacy-filter-repo-hits-1.html)**

*All reporting rights belong to the respective author(s) at **The Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 11, 2026*
