---
layout: post
title: "8-bit microcontroller hosts live website via serial internet trick"
date: 2026-05-17 01:25:26 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, hosting, article, comments, points, avr64dd32-web-server, slip-protocol-microcontroller, 8-bit-microcontroller-hosting-website, serial-internet-protocol-hack, dial-up-internet-on-modern-microcontroller, diy-8-bit-web-server, manchester-encoding-bypass-microcontroller]
author: "GlobalBR News"
description: "A hacker turned an AVR64DD32 microcontroller into a live web server using an old dial-up trick. Here's how it works."
source_url: "https://maurycyz.com/projects/mcusite/"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "/assets/images/posts/hosting-a-website-on-an-8-bit-microcontroller.webp"
image_alt: "8-bit microcontroller hosts live website via serial internet trick"
image_caption: "Close-up of an AVR64DD32 microcontroller wired to a USB-to-serial adapter, with a terminal window showing a live web req"
keywords: ["AVR64DD32 web server", "SLIP protocol microcontroller", "8-bit microcontroller hosting website", "serial internet protocol hack", "dial-up internet on modern microcontroller", "DIY 8-bit web server", "Manchester encoding bypass microcontroller"]
key_points:
  - "Used SLIP protocol to run TCP/IP over a USB-to-serial cable"
  - "AVR64DD32 runs at 24 MHz but tops out at 12 MHz for peripherals"
  - "Avoids Ethernet’s 10Mbps Manchester encoding bottleneck"
faq:
  - q: "What is SLIP and why does it matter for this project?"
    a: "SLIP is a 1988 protocol that turns serial data into TCP/IP packets without Ethernet overhead. It lets an 8-bit chip pretend it’s a dial-up modem, avoiding Ethernet’s speed limits and saving weeks of waiting for hardware."
  - q: "Can I host a real website on this microcontroller?"
    a: "You can host a tiny, text-only page that loads fast on old modems. A full site with images or dynamic content would need a lot more flash and RAM than the AVR64DD32 has, but the proof of concept works."
  - q: "Do I need special hardware to try this?"
    a: "No. You only need an AVR64DD32 or similar chip, a USB-to-serial adapter, and a few jumper wires. The software is open-source and runs on Linux terminals using commands like stty and slattach."
  - q: "How fast is the website compared to modern hosting?"
    a: "The page loads instantly on a modern browser, but the underlying serial link tops out at 115,200 baud—about 11 kbps. It’s slower than a 1990s dial-up connection, but fast enough for a one-page demo."
  - q: "Will this work on other 8-bit chips like the ATmega328?"
    a: "Most 8-bit AVR chips should work as long as they have a UART and enough flash. The ATmega328 runs at 16 MHz and lacks the extra peripherals of the DD32, but a minimal SLIP stack still fits in its 32k flash."
breaking: false
hook: "A $5 chip just served a live webpage using a trick from 1988."
tl_dr: "Turned a $5 microcontroller into a live web server using a 40-year-old serial internet trick."
lead: "An engineer got a $5 AVR64DD32 microcontroller to host a live website by turning a USB-to-serial cable into a 1980s-style internet connection. The trick bypassed Ethernet’s speed limits and proves even tiny chips can serve web pages today."
content_type: "feature"
entities:
  - "AVR64DD32"
  - "Serial Line Internet Protocol"
  - "SLIP"
  - "RFC 1055"
  - "USB-to-serial adapter"
  - "AVR microcontrollers"
---

A hobbyist just yanked off a stunt that feels like a magic trick: he got a $5 microcontroller to serve a real, live website over the internet. The target wasn’t some overpowered Raspberry Pi or ESP32 dev board—it was an AVR64DD32, a chip that costs about five bucks and runs at 24 MHz. The trick wasn’t brute force; it was a 1980s networking hack called Serial Line Internet Protocol, or SLIP. By wrapping plain TCP/IP packets inside serial data, the chip fools the internet into thinking it’s talking to a 1990s dial-up modem. The result is a live web server you can ping from anywhere, all running on a chip that would get laughed off a bench today.


The hardware side is dirt simple: an AVR64DD32, a USB-to-serial adapter, and a couple of wires. The software side is even simpler once you remember SLIP’s three rules. Every packet starts and ends with a 0xC0 byte. If the packet itself contains a 0xC0, you swap it with 0xDB 0xDC. And if it already has a 0xDB, you swap that for 0xDB 0xDD. That’s it. No checksums, no encryption, no state machines—just raw bytes flying down a wire at 115,200 baud. The AVR’s UART handles the framing, and the internet handles the rest. It’s the digital equivalent of writing a letter, stuffing it in an envelope, and hoping the post office sorts it out.


Why go through all this when Ethernet is right there? Because Ethernet at 10 Mbps uses Manchester encoding, which turns every bit into two signal transitions. That doubles the wire speed to 20 megabaud, and the AVR’s peripherals top out at 12 MHz. Even at the slowest UART speed, serial lines have no such encoding. The microcontroller can churn out bytes as fast as its crystal allows, which in this case was 115,200—plenty for a text-only web page. The hack also avoids waiting weeks for a dedicated Ethernet PHY chip to arrive from DigiKey, a real problem if your weekend project depends on next-day shipping.


SLIP isn’t new. It dates back to RFC 1055 from 1988, when 1200-baud modems were high speed and SLIP was how you got online from a Unix shell. The protocol was designed for serial links, not Ethernet, so it has no MAC addresses, no ARP, and no DHCP. You either hard-code an IP address or run a tiny DHCP client on the AVR side. In practice, the engineer used a static address (192.168.1.100) and pointed a spare router port at it. From the outside world, the microcontroller looks like any other device on the LAN—except it’s serving a page that says “Hello from an 8-bit microcontroller.”


The web page itself is the smallest possible demonstration: a single HTML file that fits in 512 bytes. It loads in under a second on a 1990s 33.6k modem, so a modern browser shows it instantly. The trick isn’t performance; it’s proof that the internet’s plumbing is still compatible with artifacts from a time when “online” meant listening to a screeching modem. The same serial port that once let you telnet into a BBS now lets a 64k microcontroller host a website.


What’s next? The engineer didn’t stop at hosting a page. He added a button that flips an LED and a sensor that reads a temperature value, all served over the same serial link. The next step is probably to shove a JPEG into the 64k flash and serve a tiny image, just to prove it’s possible. After that, someone will doubtless try to run a minimal web framework on it, or add TLS via a software library that fits in the remaining 16k of program space. The ceiling is surprisingly high for a chip that costs less than a cup of coffee.


The real takeaway isn’t that you should host your next startup on an AVR. It’s that the internet’s lowest layers are still just wires and bytes. If you can get the bits to the edge of the network, the rest will follow. That’s a lesson that still matters in an age of 5G and AI accelerators.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://maurycyz.com/projects/mcusite/)
- **Published:** May 17, 2026 at 01:25 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://maurycyz.com/projects/mcusite/)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)
- [NYT Connections Sports Edition Answers & Hints for May 17, #601](/technology/2026/05/17/todays-nyt-connections-sports-edition-hints-and-answers-for-may-17-601/)
- [Tesla quietly shelves Solar Roof, bet big on cheap panels](/technology/2026/05/17/tesla-solar-roof-is-on-life-support-as-it-pivot-to-panels/)


---

## 🇧🇷 Resumo em Português

Um microcontrolador de 8 bits, capaz de rodar um site completo ao vivo e acessível pela internet, parece coisa de ficção científica, mas um hacker conseguiu transformar um simples AVR64DD32 em um servidor web funcional usando um truque que lembra os primórdios da internet discada. A façanha não só desafia os limites do hardware modesto, como também reacende discussões sobre o potencial da computação minimalista em plena era de nuvens e supercomputadores.

O feito, documentado recentemente, mostra como é possível explorar protocolos antigos, como o SLIP (Serial Line Internet Protocol), para dar vida a dispositivos de baixo custo e consumo energético, algo especialmente relevante para o Brasil. Em um país onde a conectividade ainda é um desafio em muitas regiões, soluções como essa podem inspirar projetos de internet das coisas (IoT) mais acessíveis ou até mesmo iniciativas de inclusão digital em comunidades remotas. Além disso, a façanha evidencia a criatividade da comunidade de makers e hackers brasileiros, que frequentemente adaptam tecnologias para resolver problemas locais com orçamentos enxutos.

Ainda não se sabe se essa técnica será amplamente adotada, mas uma coisa é certa: o experimento prova que, às vezes, menos pode ser muito mais quando se trata de inovação.


---

## 🇪🇸 Resumen en Español

El pasado mes de julio, un desarrollador demostró cómo un simple microcontrolador de 8 bits puede albergar un sitio web en directo, desafiando los límites de la tecnología minimalista.

Este logro, conseguido mediante un "truco" de internet en serie típico de la era del dial-up, subraya cómo incluso los dispositivos más básicos pueden adaptarse a las necesidades modernas de conectividad. El hacker reprogramó un AVR64DD32 —un chip de bajo consumo— para que actuara como servidor web, sirviendo páginas HTML estáticas a través de una conexión serial. Aunque la velocidad es limitada y la experiencia dista mucho de los servidores tradicionales, el experimento resalta la creatividad y el ingenio en el ámbito del hardware modesto, un campo donde los desarrolladores hispanohablantes también tienen un peso significativo, especialmente en proyectos de IoT y electrónica de bajo coste.
