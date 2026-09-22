A girl asks an AI: *"Which dress should I wear tonight: the red or the black?"*

A friend would take two seconds to answer.  
A traditional AI agent, however, spirals into a 30-second existential crisis:

- Pings Doppler radar to check ambient barometric humidity.
- Parses 150 chat logs to model her date’s aesthetic preferences.
- Queries her banking API to verify card limits in case of a red wine spill.
Burns $2.00 in GPU compute, only to confidently hallucinate:  
*"You should wear both dresses at the same time."*

---

We’ve all seen this architectural anti-pattern: **Stuffing 50 tools into a single mega-prompt.**

The inevitable fallout?  
**Context pollution** and **tool hallucination** — agonizingly slow, shockingly expensive, and unpredictably unhinged.

The production-grade fix is decoupling the agent into **two distinct architectural layers**:

1. **The Decision Layer (Instinct / Reflex):**  
   Glances at the user's intent and locks in *which skill is actually needed* in single-digit milliseconds.

2. **The Execution Layer (The Hands):**  
   Receives *only* that designated skill, completes the task inside a pristine context window, and stops.

---

The ideal gatekeeper for the Decision Layer is **Jev** (from TypeSafe AI).

Unlike heavy LLMs designed for deliberation (System 2), Jev operates as a **System 1 model** — pure reflex. It’s the cognitive equivalent of tapping the brakes at a red light: instantaneous, calibrated, and decisive.

Wired up as a **Skill-Selection Hook**:

- The moment an incoming query hits the pipeline, Jev evaluates intent against candidate skills and filters out 49 irrelevant tools (weather endpoints, SQL executors, payment gateways).
- In exactly **180ms**, Jev fires a calibrated verdict: `Activate skill: Fashion & Wardrobe Styling`.

The downstream LLM receives only the exact context it needs, responds in under a second, slashes token costs by 90%, and never risks invoking a dangerous, out-of-scope tool.

1. Jev: <https://typesafe.ai/manifesto>
2. Skill selection hooks: <https://github.com/nghuyenthevinh2000/social-content#skill-selection-router-jev-hook>
