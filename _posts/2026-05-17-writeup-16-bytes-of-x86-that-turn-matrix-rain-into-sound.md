---
layout: post
title: "16 bytes of x86 code turns Matrix rain into sound at Dutch demoparty"
date: 2026-05-17 23:10:09 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, write, bytes, matrix, article, comments, 16-bytes-x86-dos-assembly, sierpinski-triangle-x86-code, demoscene-16-byte-program, real-mode-dos-audio, vga-text-mode-fractal, x86-sound-synthesis-16-bytes, outline-demoparty-2026-ommen-netherlands, 16-byte-x86-fractal-renderer, pc-speaker-audio-hack-x86, tiny-assembly-code-demoscene]
author: "GlobalBR News"
description: "A 16-byte x86 DOS assembly program draws a Sierpinski fractal in memory and turns it into sound. How hackers push limits at the Outline Demoparty in Ommen, NL."
source_url: "https://hellmood.111mb.de//wake_up_16b_writeup.html"
source_name: "Hacker News"
sentiment: "neutral"
lang: "en"
image: "/assets/images/posts/writeup-16-bytes-of-x86-that-turn-matrix-rain-into-sound.webp"
image_alt: "16 bytes of x86 code turns Matrix rain into sound at Dutch demoparty"
image_caption: "A 40x25 text-mode screen showing a glowing Sierpinski triangle with faint color gradients, representing the 16-byte x86"
keywords: ["16 bytes x86 DOS assembly", "Sierpinski triangle x86 code", "demoscene 16 byte program", "real-mode DOS audio", "VGA text mode fractal", "x86 sound synthesis 16 bytes", "Outline Demoparty 2026 Ommen Netherlands", "16 byte x86 fractal renderer"]
key_points:
  - "16 bytes of x86 code do double duty drawing fractals and making sound"
  - "Program appeared at the Outline Demoparty in Ommen, NL in May 2026"
  - "Code uses video memory as both screen canvas and audio data source"
faq:
  - q: "What is a demoparty and why does it matter?"
    a: "A demoparty is a gathering where coders, musicians, and artists compete to create real-time visuals or music under extreme technical constraints. It matters because it pushes innovation through competition and creative pressure, often producing breakthroughs that mainstream software never attempts."
  - q: "How can 16 bytes do both graphics and sound?"
    a: "The code reuses the same memory buffer for two purposes: the text cells hold both the visible fractal pattern and the raw data stream that the PC speaker converts to audio. The speaker reads from port 0x61, which the code feeds directly from the same data it’s drawing."
  - q: "Does this work on modern PCs?"
    a: "Not easily. Real-mode DOS and VGA text mode are long gone from modern operating systems. You’d need DOSBox, an emulator, or an old machine with a real ISA bus and a PC speaker to run this code today."
  - q: "Who wrote this 16-byte program?"
    a: "The author posted it under the handle hellmood on the Hacker News thread and on their personal site hellmood.111mb.de. They’re known in the demoscene for pushing algorithmic density in tiny code sizes."
  - q: "What is a Sierpinski triangle and why use it here?"
    a: "A Sierpinski triangle is a fractal made by recursively removing triangles from a larger triangle. It’s perfect for demoscene visuals because it’s easy to compute, visually striking, and scales infinitely—ideal for fitting into a tight memory footprint."
breaking: false
hook: "Sixteen bytes. One screen. A fractal that sings. That’s all it took to win cheers in a Dutch warehouse full of hackers."
tl_dr: "16 bytes of x86 code draw a Sierpinski fractal and turn it into sound in real time."
lead: "A 16-byte x86 real-mode DOS assembly program debuted at the May 2026 Outline Demoparty in Ommen, Netherlands, that draws an infinite Sierpinski fractal on screen while converting the same math into audio."
content_type: "feature"
entities:
  - "Outline Demoparty"
  - "Ommen Netherlands"
  - "hellmood"
  - "Sierpinski triangle"
  - "VGA text mode"
  - "x86 real-mode DOS"
  - "PC speaker audio"
---

A 16-byte x86 assembly program written for real-mode DOS just dropped jaws at the Outline Demoparty in Ommen, Netherlands, last May. It doesn’t just draw a Sierpinski triangle on your screen—it uses the same raw math to push audio out the PC speaker at the same time. The hack fits inside 16 bytes of code, runs in 40x25 text mode, and needs nothing but the BIOS to work. That’s not just clever. It’s the kind of trick that makes old-school demoscene coders grin like they just found a backdoor in the universe.

The code starts with the usual BIOS interrupt—int 10h—to drop the display into Video Mode 0. That clears the screen and sets up 2,000 character cells at 0xB800:0000, where every cell holds two bytes—a space character (0x20) and a light-gray-on-black color byte (0x07). The BIOS leaves every slot identical: 0x20 0x07 repeated across the whole grid. It looks empty, but it’s actually a grid of predictable data ripe for reuse.

The next six bytes load the Data Segment with 0xB800, so the code can read and write directly to the video memory. From there, the loop begins. lodsb grabs the next byte from the string into AL, then subtracts 57 (0x39) from the source index SI. That tiny offset jump forces the code to walk backward through memory in steps of 16 bytes. Each step lands on the color attribute byte of every 8th character cell—exactly where the fractal’s geometry will emerge.

Inside that narrow slice of memory, the code flips bits with a single xor [si], al. Each bit flip alters the color byte, which subtly changes how the text appears. Over thousands of iterations, the pattern solidifies into a Sierpinski triangle—a fractal that keeps repeating itself at smaller scales. The same data that forms the shape also feeds into the PC speaker via out 61h, al, turning the visual structure into a quiet, rhythmic tone. The jmp short L closes the loop, and the fractal grows and sings forever.

What makes this stunt impressive isn’t just the visual or the sound—it’s the density. Sixteen bytes is smaller than a tweet. It’s smaller than most function prologues in modern code. Yet inside those 16 bytes live an infinite fractal generator, a memory walker, and a real-time audio synth. No floating point. No external libraries. Just raw x86 real-mode assembly poking hardware directly. The demoscene thrives on constraints like this. When you force yourself to fit ideas into impossibly small spaces, creativity often explodes.

The proof-of-concept debuted at the Outline Demoparty, part of the larger demoscene tradition that prizes technical skill and aesthetic impact. Demoparties like this one—held in warehouses, basements, and sometimes castles—give coders, musicians, and graphic artists a weekend to push hardware to its limits. The rules are simple: make something cool, and do it fast. The judges don’t care about lines of code. They care about what you leave behind in sixteen bytes.

This isn’t just a party trick. It’s a reminder that the most powerful ideas sometimes come from the smallest packages. In an era where software bloat is the norm, a 16-byte program that draws, computes, and sings is a quiet rebellion. It shows that elegance still matters—even when the hardware is three decades old and the screen is only 40 columns wide.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://hellmood.111mb.de//wake_up_16b_writeup.html)
- **Published:** May 17, 2026 at 23:10 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://hellmood.111mb.de//wake_up_16b_writeup.html)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Samsung’s weather app sparks storm of controversy by handing territory to North Korea](/technology/2026/05/18/samsungs-weather-app-sparks-storm-of-controversy-by-handing-territory-to-north-k/)
- [6 in 10 Americans don’t trust AI or its managers — poll 2025](/technology/2026/05/18/most-americans-dont-trust-ai-or-the-people-in-charge-of-it-2025/)
