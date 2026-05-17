---
layout: post
title: "Amiga runs Atari ST music without wasting CPU cycles"
date: 2026-05-17 08:00:04 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, playing-atari, music, amiga, zero, article, amiga-ym2149-emulator, atari-st-music-on-amiga, zero-cpu-music-hack, paula-chip-sound-trick, amiga-demo-scene-records, 68000-graphics-with-music, arnaud-carre-amiga-hack, sin-dots-demo-2026]
author: "GlobalBR News"
description: "A new hack lets the Amiga play Atari ST music while running graphics demos. Zero CPU used thanks to clever hardware tricks."
source_url: "https://arnaud-carre.github.io/2026-05-15-ym-fast-emu/"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "https://arnaud-carre.github.io/assets/img/ymemu/fastym_title.jpg"
image_alt: "Amiga runs Atari ST music without wasting CPU cycles"
image_caption: "Arnaud Carré’s 2026 demo running on an Amiga 500, showing 6405 sin-dots with Atari ST music playing in the background."
keywords: ["Amiga YM2149 emulator", "Atari ST music on Amiga", "zero CPU music hack", "PAULA chip sound trick", "Amiga demo scene records", "68000 graphics with music", "Arnaud Carré Amiga hack", "sin-dots demo 2026"]
key_points:
  - "Developer built Atari YM2149 emulator with zero CPU usage on Amiga"
  - "PAULA chip handles music while 68000 runs graphics effects"
  - "New demo beats sin-dots record while playing Atari ST music"
faq:
  - q: "What is the YM2149 chip and why does it matter?"
    a: "The YM2149 is Atari ST’s sound chip, famous for its dirty, lo-fi chiptune sound. It’s the reason ST music has a distinct texture compared to Amiga’s cleaner PAULA chip. This hack lets Amiga hardware reproduce that sound accurately without a CPU."
  - q: "How does this emulator use zero CPU?"
    a: "The emulator tricks the Amiga’s PAULA sound chip into behaving like an Atari YM2149. PAULA handles the music in hardware while the 68000 CPU focuses entirely on graphics, leaving both chips working efficiently."
  - q: "Who is Hannibal and why did he inspire this project?"
    a: "Hannibal is a legendary Amiga demo coder who released the 3D Demo 3 in 2024, breaking the sin-dots record. He left a playful jab at Arnaud Carré, calling him an 'Atari programmer,' which pushed Carré to respond with this technical flex."
  - q: "Can this technique run modern Atari ST music?"
    a: "Yes, but with caveats. The emulator handles the YM2149’s core functions, but advanced effects like SID voices or Digidrums require extra hardware tricks. Carré’s demo focuses on classic ST music, which works perfectly."
  - q: "Where can I see this demo in action?"
    a: "Arnaud Carré’s write-up and code are on GitHub, with a video demo linked in his blog. The Amiga scene community is already sharing builds and tweaks, so expect forks and improvements soon."
breaking: false
hook: "The Amiga just ate Atari ST music for breakfast—without wasting a single CPU cycle."
tl_dr: "Amiga now plays Atari ST music without touching its CPU, breaking demo scene records."
lead: "A French developer just proved the Amiga can play Atari ST music while running graphics demos at full speed. The trick uses no CPU, leaving the Motorola 68000 free for effects."
content_type: "news"
entities:
  - "Arnaud Carré"
  - "Hannibal (demo coder)"
  - "Amiga 500"
  - "Motorola 68000"
  - "Atari ST"
  - "YM2149"
  - "PAULA (Amiga sound chip)"
---

Arnaud Carré just dropped a technical marvel that chip music fans and demo scene historians will geek out over. His new YM2149 emulator for the Amiga runs Atari ST music with zero CPU load, meaning the Motorola 68000 stays free to render graphics at full speed. The trick? Letting the Amiga’s own PAULA sound chip do the heavy lifting instead of the CPU. This isn’t just a cool demo—it’s a real-world solution to a problem that’s dogged Amiga musicians and programmers for decades.

Carré’s breakthrough came together over two years, starting with a playful nudge from demo scene legend Hannibal. After Hannibal’s 3D Demo 3 crushed Carré’s old sin-dots record, he left a cheeky message: “you optimized your dots well for an Atari programmer.” That jab stuck, and Carré decided to hit back—not just by breaking the record again, but by playing Atari music during the attempt. The catch? Accurate Atari music emulation normally hogs 50% of the CPU, which would kill any chance of running graphics effects smoothly.

So Carré went back to the drawing board. His 2020 AmigAtari demo already proved Atari music could run on Amiga hardware, but it was too slow for graphics-heavy tasks. This time, he flipped the script: instead of emulating the Atari YM2149 in software, he made PAULA—the Amiga’s sound chip—mimic the YM2149’s behavior in hardware. The result is pure magic: Atari ST music plays in the background while the 68000 crunches numbers for graphics effects, all without breaking a sweat.

The demo itself is a thing of beauty. Carré’s setup renders 6,405 sin-dots at 50 FPS on an Amiga 500, all while a full Atari ST soundtrack plays uninterrupted. It’s a technical flex that would’ve made the old-school demo scene proud, where bragging rights often came down to who could push hardware the hardest. Hannibal’s record of 6,682 dots from 2024 still stands for now, but Carré’s work proves the Amiga’s limits are far from reached.

What makes this hack so clever isn’t just the speed—it’s the elegance. By using PAULA’s DMA channels and hardware registers, Carré bypassed the need for slow software emulation entirely. The YM2149 and PAULA chips sound different, but their core behaviors overlap enough that PAULA can fake it convincingly. It’s like teaching a violinist to play a guitar by retuning the strings—technically not the same instrument, but the notes come out right.

For chiptune musicians, this opens up new possibilities. Imagine running a full Atari ST tracker module in the background of a live graphics demo, or layering Amiga and Atari sounds in a single track without maxing out the CPU. Carré’s code, now open-source, gives others a starting point to build on. The demo scene has always thrived on this kind of one-upmanship, and this move is pure classic: a technical response to a roast, delivered with style.

The bigger picture? The Amiga’s hardware tricks are far from exhausted. Decades after its heyday, the machine’s quirks are still yielding fresh ideas. Carré’s work shows how understanding vintage hardware can lead to unexpected innovations—even when the hardware itself hasn’t changed in 40 years.

Now, the question isn’t whether someone will break this record next. It’s how soon the next trick will appear—and who’ll be the one to pull it off.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://arnaud-carre.github.io/2026-05-15-ym-fast-emu/)
- **Published:** May 17, 2026 at 08:00 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://arnaud-carre.github.io/2026-05-15-ym-fast-emu/)**

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

A música do Atari ST agora toca no Amiga sem consumir nem um ciclo de processador — uma façanha que só os puristas de retrocomputação vão entender, mas que pode redefinir o que é possível em máquinas antigas.

A façanha, batizada de "Amiga vs Atari ST Music Hack", explora um truque de hardware para contornar a limitação do Amiga em reproduzir sons do concorrente sem sobrecarregar a CPU. Isso é especialmente relevante no Brasil, onde a cena de demoscene e retrocomputação tem ganhado força nos últimos anos, com comunidades ativas que mantêm viva a cultura da programação low-level e do hardware modificado. Além disso, a iniciativa mostra como a engenhosidade de desenvolvedores independentes pode superar barreiras técnicas em sistemas legados, algo que inspira até mesmo os entusiastas de tecnologia moderna a repensarem soluções criativas para problemas antigos.

Com isso, a porta está aberta para que novos projetos explorem essa técnica em outros contextos — quem sabe, em breve, veremos demos que misturem som de Amiga e Atari em uma única máquina, sem gastar energia desnecessária.


---

## 🇪🇸 Resumen en Español

La magia de la retroinformática alcanza un nuevo hito: el Amiga logra ejecutar música del Atari ST sin consumir ni un solo ciclo de su preciado procesador.

Este avance, logrado mediante ingeniosos trucos de hardware, no solo demuestra la creatividad de la comunidad de entusiastas, sino que redefine los límites de lo que es posible con máquinas clásicas. Para los hispanohablantes amantes de la tecnología, la noticia subraya cómo la innovación no depende siempre de lo más moderno, sino de entender —y exprimir— al máximo los dispositivos que ya existen. Además, abre puertas a nuevas experiencias de retrocomputación, donde la música y los gráficos pueden correr en paralelo sin sacrificar rendimiento, algo que evoca la esencia de la era dorada de los 80 y 90.
