---
id: 5
title: "A stylesheet value silently beat an animated SVG attribute (leader lines never drew)"
status: open
type: open-source
skill: [studio-quality, studio-motion-system]
proposes_skill: []
target_file: []
siblings_checked: "studio: studio-quality added (Pièges list); studio-motion-system added (draw-on recipes); studio-polish-pass excluded — applies the list (assumed)"
area: "Pièges déjà rencontrés / SVG draw-on"
date: 2026-10-21
session_context: "Enoryx installations ad (videos/enoryx-installations), AR leader lines"
parked_until:
resolved:
resolution:
reference: "videos/enoryx-installations/.src/gen.py"
commands_verified: none
---

**Issue:** Leader lines had stroke-dashoffset: 100 in the stylesheet and were tweened with GSAP attr: { "stroke-dashoffset" }. The CSS property outranks the presentation attribute, so the tween ran and nothing moved; only a snapshot showed it.

**Suggested improvement:** Pitfall line: animate the same layer that sets the start state — CSS property (strokeDashoffset) when the start value lives in CSS, attr only when it lives in the attribute.

**Principle:** When one value can come from two layers, the animation must target the layer that wins, or it animates nothing without an error.
