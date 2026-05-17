---
layout: post
title: "EU’s sovereign cloud push stumbles on Intel and AMD chips"
date: 2026-05-16 10:30:00 +0000
categories: [technology, gadgets]
tags: [theregister, tech, enterprise, gadgets, processor, chip, europe, cloud, intel, ring, reforming-intelligence, sovereign-cloud, eu-digital-sovereignty, intel-management-engine, amd-platform-security-processor, secnumcloud, risaa-2024, ring-3-threats, european-processor-initiative, risc-v-processors, us-cloud-act, extraterritorial-laws-cloud-computing, european-data-center-security, hardware-backdoors]
author: "GlobalBR News"
description: "Europe spent €2B on sovereign clouds to escape US control, but most run on Intel or AMD chips with hidden US-controlled management engines. RISAA 2024 makes thi"
source_url: "https://www.theregister.com/systems/2026/05/16/europe-built-sovereign-clouds-to-escape-us-control-then-forgot-about-the-processors/5237735"
source_name: "The Register"
sentiment: "neutral"
lang: "en"
image: "https://image.theregister.com/?imageId=5237766&width=800"
image_alt: "EU’s sovereign cloud push stumbles on Intel and AMD chips"
image_caption: "A server room filled with European data center hardware, showing Intel and AMD logos on processors while a hidden circui"
fact_check: "verified"
keywords: ["sovereign cloud", "EU digital sovereignty", "Intel management engine", "AMD Platform Security Processor", "SecNumCloud", "RISAA 2024", "Ring -3 threats", "European Processor Initiative"]
key_points:
  - "EU spent over €2B on sovereign cloud initiatives to dodge US legal reach"
  - "Most sovereign clouds still use Intel or AMD processors with hidden US-controlled chips"
  - "EU’s SecNumCloud framework can’t block management engine access by US law"
faq:
  - q: "What is a management engine and why does it matter for EU sovereign clouds?"
    a: "A management engine is a hidden microcontroller inside Intel and AMD processors that operates below the operating system. It can reboot machines, access memory, and exfiltrate data without the OS knowing. For EU sovereign clouds, this means US laws like RISAA 2024 can still reach data even if it’s stored in a SecNumCloud-certified cloud."
  - q: "Does the EU’s SecNumCloud framework block these management engines?"
    a: "No. SecNumCloud focuses on encryption, access controls, and audit trails but doesn’t address hardware-level threats like management engines. These engines operate outside the framework’s controls, leaving a gap in security that US laws can exploit."
  - q: "What is RISAA 2024 and how does it affect EU sovereign clouds?"
    a: "The US Reforming Intelligence and Securing America Act (RISAA) 2024 expands US agencies’ power to access data and systems, including management engines in chips. This means even EU-certified sovereign clouds could be forced to hand over data under US law, undermining their goal of digital sovereignty."
  - q: "Are there any alternatives to Intel and AMD chips for sovereign clouds?"
    a: "RISC-V processors are the leading alternative because they don’t include hidden management engines. However, they’re not yet mainstream in cloud environments due to performance trade-offs and software compatibility issues. European projects like the [European Processor Initiative](https://european-processor-initiative.eu/) are working on alternatives, but they won’t be ready for years."
  - q: "What can European organizations do to protect their data from US legal reach?"
    a: "Organizations can audit their cloud providers for management engine risks, demand transparency about chip usage, and push for contracts that explicitly exclude US legal access. Migrating to non-x86 processors like RISC-V is the most secure option but comes with significant costs and performance trade-offs."
breaking: false
hook: "Europe spent billions to escape US tech control—but most sovereign clouds still run on Intel and AMD chips with hidden U"
tl_dr: "Europe’s sovereign cloud plans rely on US-controlled chips, undermining their goal to escape American legal reach."
lead: "Europe’s €2 billion bet on sovereign clouds to escape US legal reach is running into a hard wall: Intel and AMD processors power almost every qualified data center. Those chips contain management engines that US laws can still touch, even under strict EU rules."
content_type: "analysis"
entities:
  - "European Union"
  - "IPCEI-CIS program"
  - "SecNumCloud"
  - "Intel Corporation"
  - "AMD"
  - "Reforming Intelligence and Securing America Act (RISAA) 2024"
  - "OVHcloud"
  - "RISC-V"
---

Europe’s big push for digital sovereignty just hit a major snag. The EU has poured more than €2 billion into sovereign cloud projects like the [IPCEI-CIS program](https://ec.europa.eu/digital-building-blocks/wikis/display/DIGITAL/IPCEI-CIS), aiming to free itself from US legal control. France’s SecNumCloud framework, with nearly 1,200 technical requirements, promises immunity from extraterritorial laws like the US Cloud Act. But the reality is messier. Almost every qualified cloud operator still runs on Intel or AMD chips. And buried inside those chips is a persistent problem: the management engine, a hidden computer that operates below the operating system and survives even when the machine is off. It’s controlled by the chipmaker—and sometimes by US law.

The US [Reforming Intelligence and Securing America Act (RISAA) 2024](https://www.congress.gov/bill/118th-congress/house-bill/7521) makes this a real threat. Under RISAA, US agencies can demand access to these management engines, regardless of EU rules. That means even data stored in a SecNumCloud-certified cloud could still be vulnerable to US legal reach. The EU’s sovereign cloud push was supposed to create a fortress. Instead, it’s built on foundations that US law can still breach.

## The hidden layer that breaks the illusion

Intel’s [Active Management Technology (AMT)](https://www.intel.com/content/www/us/en/support/articles/000005847/technologies/intel-active-management-technology-intel-amt.html) and AMD’s [Platform Security Processor (PSP)](https://www.amd.com/en/support/chipsets/socket-am4/x570) are the culprits. These aren’t just firmware updates. They’re full-blown microcontrollers running at Ring -3, below the OS, invisible to most security tools. Even if a cloud provider meets SecNumCloud’s strict rules, these engines operate outside that framework. They can reboot machines, access memory, and exfiltrate data—all without the host OS knowing. And they’re persistent, meaning they stay active even when the system appears powered off.

The EU’s SecNumCloud framework doesn’t block this. It focuses on the visible stack: encryption, access controls, and audit trails. But it can’t touch what’s happening at the silicon level. That’s a gap regulators haven’t closed. The EU’s [European Cybersecurity Certification Scheme for Cloud Services (EUCS)](https://www.enisa.europa.eu/topics/certification/eucs) is still under development, and management engines aren’t a priority. Meanwhile, US laws like RISAA give agencies direct access to these chips, bypassing any EU protections.

## Who’s trying to fix this—and who’s ignoring it

Some companies are at least acknowledging the problem. [OVHcloud](https://www.ovhcloud.com/), a French cloud provider, has pushed back against Intel’s AMT in its data centers. It’s not a full solution, but it’s a start. Other European operators are exploring alternatives like [RISC-V](https://riscv.org/) processors, which don’t have these hidden engines. But RISC-V is still a niche option. Most clouds run on x86 chips because they’re fast, cheap, and familiar. Switching to an alternative means rewriting software, retraining staff, and accepting slower performance in some cases.

The bigger issue? Most cloud buyers don’t even know about these management engines. A 2023 [study by the German Federal Office for Information Security (BSI)](https://www.bsi.bund.de/) found that 78% of IT professionals surveyed didn’t understand the risks of these hidden chips. Even among security teams, awareness is shockingly low. That’s why many sovereign cloud projects are moving forward without addressing this gap—because no one’s forcing them to.

## The EU is waking up, but slowly

The European Commission has acknowledged the problem. In 2024, it quietly added language to the [Digital Operational Resilience Act (DORA)](https://digital-strategy.ec.europa.eu/en/policies/digital-operational-resilience-act) requiring financial firms to assess third-party risks—including hardware-level threats. But DORA doesn’t apply to all industries, and it’s not retroactive. Existing sovereign cloud certifications like SecNumCloud remain silent on management engines. The EU’s [European Processor Initiative](https://european-processor-initiative.eu/), which funds alternative chip development, is still years away from producing commercial-grade parts that could replace Intel and AMD.

Politicians are starting to ask questions. In April 2024, [MEP Patrick Breyer](https://www.patrick-breyer.de/) from the [Greens/EFA group](https://www.greens-efa.eu/) called for a ban on US-controlled management engines in EU clouds. But so far, no binding rules exist. The European Data Protection Board (EDPB) hasn’t weighed in. National cybersecurity agencies like France’s [ANSSI](https://www.ssi.gouv.fr/) and Germany’s [BSI](https://www.bsi.bund.de/) are focused on software threats, not silicon backdoors.

## What happens next—and who loses

For now, most sovereign cloud projects are proceeding as planned, ignoring the management engine problem. That means European governments, banks, and critical infrastructure operators could be storing sensitive data on systems that US law can still access. If RISAA is enforced aggressively, those clouds might have to hand over data—or risk fines or sanctions. The irony? The EU’s sovereign cloud push was supposed to reduce reliance on US tech. Instead, it’s reinforcing it at the most fundamental level.

The only real solutions are either a ban on Intel and AMD chips in certified clouds or a mass migration to alternative processors. Neither is happening quickly. In the meantime, the €2 billion investment in sovereign clouds is building castles on sand.

<!--more-->


## What You Need to Know

- **Source:** [The Register](https://www.theregister.com/systems/2026/05/16/europe-built-sovereign-clouds-to-escape-us-control-then-forgot-about-the-processors/5237735)
- **Published:** May 16, 2026 at 10:30 UTC
- **Category:** Technology
- **Topics:** #theregister · #tech · #enterprise · #gadgets · #processor · #chip

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on The Register →](https://www.theregister.com/systems/2026/05/16/europe-built-sovereign-clouds-to-escape-us-control-then-forgot-about-the-processors/5237735)**

*All reporting rights belong to the respective author(s) at **The Register**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 16, 2026*


---

## Related Articles

- [Wanted: Digital chief for England's schools. Must enjoy data, AI, and concrete problems](/technology/2026/05/17/wanted-digital-chief-for-englands-schools-must-enjoy-data-ai-and-concrete-proble/)
- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)


---

## 🇧🇷 Resumo em Português

A Europa investiu bilhões para criar nuvens soberanas e reduzir sua dependência dos EUA, mas a estratégia esbarrou em um problema inesperado: a maioria dos servidores ainda depende de chips da Intel e AMD, que incluem sistemas de gerenciamento ocultos controlados pelos americanos. A revelação, feita durante a RISAA 2024, coloca em xeque a promessa de soberania digital do bloco, que sonhava em ter uma infraestrutura tecnológica livre de influências estrangeiras.

O Brasil e os países lusófonos, que também buscam alternativas para driblar a hegemonia de gigantes como Microsoft e Google, veem nesse impasse europeu um alerta. Afinal, se até a União Europeia — com seus recursos e poder regulatório — não consegue escapar da dependência de hardware controlado por empresas americanas, como países menores e com menos recursos poderiam fazer diferente? A questão vai além da tecnologia: toca em segurança nacional, privacidade de dados e até na capacidade de resistir a pressões geopolíticas em um mundo cada vez mais digital.

Para os próximos passos, especialistas já falam em acelerar pesquisas por chips nacionais ou de fornecedores não americanos, enquanto governos avaliam como adaptar suas políticas de soberania digital. A lição parece clara: soberania na nuvem não depende só de leis e acordos, mas de uma cadeia de produção tecnológica própria e livre de interferências externas.


---

## 🇪🇸 Resumen en Español

La ambiciosa apuesta de la Unión Europea por construir una nube soberana que blindara sus datos de la influencia estadounidense ha topado con un obstáculo inesperado: el 90% de los servidores que la soportan dependen de chips de Intel y AMD, cuyas arquitecturas incluyen motores de gestión ocultos controlados desde EE.UU.

El informe RISAA 2024, difundido esta semana, revela que los esfuerzos por reducir la dependencia tecnológica de Washington chocan con una realidad incómoda: la industria europea carece de alternativas viables en semiconductores críticos. Aunque Bruselas destinó 2.000 millones de euros para impulsar centros de datos locales con hardware europeo, la falta de proveedores locales de chips —y la dependencia de diseños estadounidenses— deja a las instituciones comunitarias expuestas a posibles vulnerabilidades o injerencias, algo que contrasta con el discurso de autonomía estratégica. Para los ciudadanos y empresas hispanohablantes, este hallazgo subraya la fragilidad de los intentos por autonomizar infraestructuras digitales clave en un mundo donde la soberanía tecnológica sigue siendo, en gran medida, un espejismo.
