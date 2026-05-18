---
layout: post
title: "Researchers crack AMD SEV-SNP with Infinity Fabric misconfig attack"
date: 2026-05-17 22:23:30 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, fabricked, break, article, comments, points, amd-sev-snp-vulnerability, infinity-fabric-attack, confidential-computing-hack, amd-epyc-security-flaw, cloud-vm-isolation-bypass, how-to-exploit-amd-sev-snp, secure-virtual-machine-attack, hypervisor-memory-routing-trick, usenix-security-2026-amd-attack]
author: "GlobalBR News"
description: "Security researchers bypass AMD's SEV-SNP encryption on confidential VMs by tricking the chip's Infinity Fabric into misrouting memory. Here's how it works."
source_url: "https://xca-attacks.github.io/fabricked/"
source_name: "Hacker News"
sentiment: "negative"
lang: "en"
image: "https://xca-attacks.github.io/preview.png?123456"
image_alt: "Researchers crack AMD SEV-SNP with Infinity Fabric misconfig attack"
image_caption: "AMD EPYC server CPU with Infinity Fabric highlighted, representing the chip's internal data highway targeted by the Fabr"
keywords: ["AMD SEV-SNP vulnerability", "Infinity Fabric attack", "confidential computing hack", "AMD EPYC security flaw", "cloud VM isolation bypass", "how to exploit AMD SEV SNP", "secure virtual machine attack", "hypervisor memory routing trick"]
key_points:
  - "Misconfigured Infinity Fabric lets attackers redirect memory inside AMD CVMs"
  - "Attack abuses PSP initialization to gain arbitrary read/write access"
  - "SEV-SNP promises hardware-enforced memory isolation for cloud VMs"
faq:
  - q: "What exactly is AMD SEV-SNP?"
    a: "AMD Secure Encrypted Virtualization with Secure Nested Paging encrypts a virtual machine's memory while it's running. It's designed to stop cloud administrators or hypervisors from seeing or altering the VM's data while it's active."
  - q: "How does the Fabricked attack bypass SEV-SNP?"
    a: "The attack tricks the CPU's Infinity Fabric into misrouting memory transactions so they bypass SEV-SNP's encryption checks. The secure co-processor never gets the right signals to activate protection, letting the attacker read or write memory inside the supposedly secure VM."
  - q: "Who can perform this attack?"
    a: "Only someone with hypervisor-level access can manipulate the fabric settings. In cloud environments, that typically means the cloud provider or a malicious admin with sufficient privileges—not an external attacker without insider access."
  - q: "Is my cloud data at risk right now?"
    a: "Most customers aren't immediately exposed. The attack requires specific conditions and deep technical knowledge. Check with your cloud provider to see if they've updated fabric controls or added monitoring to block this technique."
  - q: "What should cloud providers do to stop this?"
    a: "Providers should audit hypervisor controls over Infinity Fabric settings, add runtime monitoring for unexpected memory routing changes, and work with AMD on potential microcode updates. Customers should demand details on these mitigations for sensitive workloads."
featured: true
breaking: true
hook: "AMD's strongest cloud encryption just got cracked—and it only took a tweak to the chip's internal wiring."
tl_dr: "Malicious cloud admins can bypass AMD SEV-SNP isolation using a memory routing trick on Infinity Fabric."
lead: "AMD's SEV-SNP encryption for confidential virtual machines can be broken by tricking the CPU's Infinity Fabric into misrouting memory, researchers found. The attack lets a malicious hypervisor read or write data inside an otherwise secure VM."
content_type: "breaking"
entities:
  - "AMD SEV-SNP"
  - "Infinity Fabric"
  - "AMD EPYC"
  - "Platform Security Processor"
  - "USENIX Security 2026"
---

A team of security researchers just proved AMD's SEV-SNP, the gold standard for encrypting live workloads in the cloud, isn't as airtight as promised. They call the attack Fabricked and it works by abusing how AMD's Infinity Fabric moves data around inside the chip. When a malicious hypervisor messes with the memory routing, it can trick the Platform Security Processor into thinking the system is in a normal state—even when SEV-SNP should be active. That tiny misdirection lets the attacker peek at or alter data inside a Confidential Virtual Machine that's supposed to be locked down.

AMD [SEV-SNP](https://en.wikipedia.org/wiki/AMD_Secure_Encrypted_Virtualization) is what keeps your encrypted VM safe while it's running in a cloud provider's data center. The hypervisor controls the VM's memory, but SEV-SNP is supposed to make sure the cloud admin can't see or touch what's inside. The chip's Infinity Fabric is the high-speed data highway connecting CPU cores, memory controllers, and other parts. It's supposed to keep everything in order, but the researchers found a way to reroute memory transactions so the secure co-processor never gets the right signals.

## How the attack actually works

The trick starts with the hypervisor manipulating the fabric's address mapping. Normally the Infinity Fabric routes memory requests to the right location without the hypervisor getting involved. But when an attacker tweaks those settings, memory that should land in encrypted SEV-SNP space ends up in plain, unprotected memory instead. The PSP, which initializes the security environment, gets fooled into thinking the system is in a clean state. It never realizes SEV-SNP isn't active, so it doesn't enforce the encryption barriers. Once the PSP is tricked, the attacker gains full read and write access inside the victim VM's address space.

The researchers tested Fabricked on AMD EPYC CPUs running SEV-SNP-enabled virtual machines. They showed it's possible to extract sensitive data like encryption keys or customer information without triggering any SEV-SNP alerts. The attack doesn't require physical access or even a reboot—just the ability to tweak hypervisor-level fabric settings, which some cloud environments allow.

## Why this matters for cloud security

Confidential computing is supposed to protect your data while it's being processed, not just when it's stored or in transit. Companies moved workloads to cloud CVMs to prevent cloud admins, malicious insiders, or even governments from snooping on live computations. SEV-SNP is the main defense for AMD-based clouds, powering everything from banks to government services. If a hypervisor can bypass it, the entire trust model falls apart. Customers assumed their data was safe inside the VM—this attack proves that assumption can be wrong.

AMD hasn't commented publicly yet, but the researchers already shared their findings with the company before the [USENIX Security 2026](https://www.usenix.org/conference/usenixsecurity26) presentation. Cloud providers running AMD EPYC servers will need to audit their fabric configurations and patch hypervisor controls. Users relying on SEV-SNP for sensitive workloads should ask providers how they're mitigating this risk. The attack isn't a simple script anyone can run—it requires deep knowledge of chip internals and privileged access—but the fact it's possible at all changes the security calculus for confidential computing.

What's next isn't clear yet. AMD could issue microcode updates to tighten fabric controls. Cloud providers might add extra monitoring for unexpected memory routing changes. Customers may start demanding more transparency about how their CVMs are configured. One thing is certain: this proof-of-concept just made the invisible threat of hypervisor-level attacks a lot more real for anyone running sensitive workloads in the cloud.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://xca-attacks.github.io/fabricked/)
- **Published:** May 17, 2026 at 22:23 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://xca-attacks.github.io/fabricked/)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Samsung’s weather app sparks storm of controversy by handing territory to North Korea](/technology/2026/05/18/samsungs-weather-app-sparks-storm-of-controversy-by-handing-territory-to-north-k/)
- [6 in 10 Americans don’t trust AI or its managers — poll 2025](/technology/2026/05/18/most-americans-dont-trust-ai-or-the-people-in-charge-of-it-2025/)
