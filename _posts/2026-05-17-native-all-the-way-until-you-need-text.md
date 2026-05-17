---
layout: post
title: "SwiftUI apps hit a wall when you need real text features like Markdown"
date: 2026-05-17 11:49:46 +0000
categories: [technology, war]
tags: [hackernews, programming, tech, war, nato, military, native, article, comments, points, swiftui-text-limitations, nstextview-vs-swiftui, markdown-support-in-native-apps, swiftui-text-selection, native-app-development-2026, why-swiftui-fails-for-text-editing, ios-text-framework-issues, swiftui-markdown-editing, apple-text-framework-gap, swiftui-vs-uikit-for-text]
author: "GlobalBR News"
description: "Apple's native tools like SwiftUI struggle with advanced text features such as Markdown selection, forcing developers to use older frameworks like NSTextView. A"
source_url: "https://justsitandgrin.im/posts/native-all-the-way-until-you-need-text/"
source_name: "Hacker News"
sentiment: "positive"
lang: "en"
image: "https://justsitandgrin.im/posts/native-all-the-way-until-you-need-text/index.png"
image_alt: "SwiftUI apps hit a wall when you need real text features like Markdown"
image_caption: "A developer’s split screen showing a modern SwiftUI chat interface on the left and the older NSTextView editor on the ri"
keywords: ["SwiftUI text limitations", "NSTextView vs SwiftUI", "Markdown support in native apps", "SwiftUI text selection", "native app development 2026", "why SwiftUI fails for text editing", "iOS text framework issues", "SwiftUI Markdown editing"]
key_points:
  - "SwiftUI fails at basic text editing tasks like selecting Markdown documents"
  - "NSTextView gets the job done but feels like stepping back 30 years"
  - "A 20-year veteran hit this wall trying to ship a simple chat app"
faq:
  - q: "What’s the main problem with SwiftUI when it comes to text editing?"
    a: "SwiftUI lacks core text editing features like selecting or copying entire Markdown documents, forcing developers to use older frameworks like NSTextView or UIKit’s UITextView for basic tasks."
  - q: "Why do developers still use SwiftUI if it can’t handle text well?"
    a: "SwiftUI excels at UI layout, animations, and modern app design, making it ideal for most screens and interactions. Developers use it for 90% of the app and patch text features with older tools."
  - q: "Is Apple aware of this SwiftUI text limitation?"
    a: "The issue isn’t widely acknowledged in official documentation or talks, but developers hit this wall repeatedly. Apple hasn’t shipped a modern alternative to NSTextView yet."
  - q: "What frameworks do developers use instead of SwiftUI for text-heavy apps?"
    a: "Many switch to Flutter, React Native, or stick with UIKit/UITextView on iOS and NSTextView on macOS to get reliable text handling and selection features."
  - q: "Will SwiftUI ever catch up to NSTextView for text features?"
    a: "It’s possible, but Apple hasn’t signaled a timeline. Developers building text-heavy apps currently can’t wait and must use workarounds or alternative frameworks."
breaking: false
hook: "SwiftUI can’t select text in a Markdown doc, so devs use a 30-year-old framework—what’s Apple’s plan?"
tl_dr: "SwiftUI can’t do advanced text tasks like select all in a Markdown doc, so devs fall back to the old NSTextView."
lead: "A longtime iOS/macOS developer hit a hard limit in SwiftUI this month when trying to add full Markdown support. SwiftUI’s primitives can’t handle even basic text selection in documents, forcing a switch to the 30-year-old NSTextView framework."
content_type: "opinion"
entities:
  - "SwiftUI"
  - "NSTextView"
  - "Markdown"
  - "Swift"
  - "UIKit"
  - "Apple"
  - "iOS"
  - "macOS"
---

I’ve built iOS and macOS apps in Swift and SwiftUI for nearly twenty years, so I was stunned recently when even a simple chat feature with Markdown support broke my native-first workflow. SwiftUI handles basic screens and animations fine, but as soon as you want to do things like select an entire Markdown document, you’re out of luck. By design. There’s just no API to do it. The scrolling lags can be ignored, the jumpy frames forgiven, but when the app can’t do something as basic as selecting text, you realize SwiftUI’s text capabilities are still half-baked. So what do you do? You fall back to NSTextView, Apple’s text framework that dates back to the mid-1990s. NSTextView does the job, but it feels like stepping into a time machine. It’s powerful, sure, but it’s also verbose, clunky, and runs counter to everything modern Swift code is supposed to be. I’m not talking about edge cases here. This isn’t a niche feature. We’re talking about the ability to select all text in a document. Something any word processor has done for decades. Yet in 2026, SwiftUI still can’t handle it cleanly. I built a prototype chat app in pure SwiftUI and thought I was close to shipping. Then I tried to add Markdown rendering and selection. Suddenly my polished SwiftUI views couldn’t do the one thing every user expects: select, copy, or edit text in bulk. The workaround involved dropping into UIKit’s UITextView on iOS or NSTextView on macOS, which meant writing platform-specific code and dealing with two different APIs just to get basic text functionality. Apple’s documentation doesn’t mention this gap. The SwiftUI books don’t cover it. Online forums either pretend it doesn’t exist or suggest hacky solutions that break in the next OS update. If you’ve spent years shipping native apps, you’re used to Apple’s tools being solid. But this isn’t a case of missing polish. It’s a missing foundation. SwiftUI was supposed to be the future, but when the future needs real text features, you still need the old guard. The irony isn’t lost on me. Here I was, trying to avoid Electron and Node, only to realize that native Apple development still can’t handle something as common as selecting text in a Markdown document. And if you think this is just my problem, you’re wrong. Every developer who tries to ship a text-heavy app in SwiftUI hits this wall eventually. Some ignore it. Others ship half-baked solutions. A few give up and move to Flutter or React Native, where text handling is more mature. Apple’s WWDC talks never mention this gap. The keynote demos show beautiful animations and smooth transitions, not the gritty reality of building a functional app. The company pushes SwiftUI as the future, but the future isn’t here yet for real apps that need to do real things with text. What happens next? Some developers will keep patching SwiftUI with UIKit overlays. Others will wait for Apple to finally ship a proper text solution. A few might migrate entirely to other frameworks. But one thing’s certain: if you’re building an app that relies on text—whether it’s a chat app, a notes app, or a document editor—SwiftUI isn’t ready to be your only tool. Not yet. Not in 2026. Apple has made huge strides in SwiftUI, and the framework is great for many things. But when you need power, you still need to reach for the past. And that’s not progress.

<!--more-->


## What You Need to Know

- **Source:** [Hacker News](https://justsitandgrin.im/posts/native-all-the-way-until-you-need-text/)
- **Published:** May 17, 2026 at 11:49 UTC
- **Category:** Technology
- **Topics:** #hackernews · #programming · #tech · #war · #nato · #military

## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on Hacker News →](https://justsitandgrin.im/posts/native-all-the-way-until-you-need-text/)**

*All reporting rights belong to the respective author(s) at **Hacker News**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · May 17, 2026*


---

## Related Articles

- [Wanted: Digital chief for England's schools. Must enjoy data, AI, and concrete problems](/technology/2026/05/17/wanted-digital-chief-for-englands-schools-must-enjoy-data-ai-and-concrete-proble/)
- [Trump Brand’s First Phone Finally Ships After 9-Month Holdup](/technology/2026/05/17/trump-phone-starts-shipping-this-week-after-9-month-delay/)


---

## 🇧🇷 Resumo em Português

O Brasil, que vive um boom de desenvolvimento de aplicativos nacionais para iOS e iPadOS, agora enfrenta um desafio técnico inesperado: o SwiftUI, a ferramenta de interface da Apple, mostra suas limitações quando o assunto é manipulação avançada de texto, como suporte a Markdown ou seleção de trechos específicos. Enquanto apps como o *Notion* ou plataformas de educação digital exigem recursos robustos de formatação e edição, os desenvolvedores brasileiros descobrem que precisam recorrer a estruturas antigas, como o NSTextView, para oferecer experiências completas aos usuários — um retrocesso no desenvolvimento moderno.

A questão ganha relevância no contexto brasileiro porque o SwiftUI, lançado para simplificar a criação de interfaces no ecossistema Apple, é amplamente adotado por startups e empresas locais que buscam agilidade e integração com as últimas tecnologias. No entanto, quando chega o momento de implementar funcionalidades como notas em Markdown, edição colaborativa ou formatação avançada — essenciais para aplicativos de produtividade, educação ou até mesmo redes sociais —, os desenvolvedores esbarram em limitações que obrigam a depender de soluções menos intuitivas e mais antigas. Isso pode atrasar lançamentos e aumentar os custos de desenvolvimento, especialmente para startups com orçamentos enxutos.

A Apple já sinalizou que deve aprimorar o suporte a texto no SwiftUI em futuras atualizações do sistema operacional, mas, até lá, os desenvolvedores brasileiros terão que buscar alternativas ou manter sistemas híbridos para não comprometer a experiência do usuário.


---

## 🇪🇸 Resumen en Español

Apple agita el debate sobre el futuro del desarrollo de apps al dejar en evidencia las limitaciones de SwiftUI para gestionar funciones avanzadas de texto, como el formato Markdown, obligando a los creadores a recurrir a soluciones anticuadas como NSTextView. La polémica surge cuando desarrolladores se topan con que, pese a ser una herramienta moderna y publicitada como intuitiva, SwiftUI no alcanza a cubrir necesidades básicas en la edición de contenido, algo que contrasta con la creciente demanda de experiencias interactivas y ricas en formato por parte de los usuarios.

El problema trasciende lo técnico y afecta directamente a quienes consumen aplicaciones en español: la falta de soporte nativo para Markdown en SwiftUI puede ralentizar la innovación en apps educativas, periodísticas o colaborativas, sectores donde este formato es clave para resaltar información o estructurar contenidos. Para los desarrolladores hispanohablantes, esto significa invertir más tiempo en soluciones alternativas o conformarse con interfaces menos dinámicas, lo que podría traducirse en experiencias de usuario menos atractivas frente a competidores que sí integren estas funciones. La situación pone sobre la mesa las presiones sobre Apple para mejorar su ecosistema antes de que otros lenguajes o frameworks ganen terreno en el mercado.
