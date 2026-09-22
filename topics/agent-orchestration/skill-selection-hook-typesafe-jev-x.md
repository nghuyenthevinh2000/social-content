# Twitter / X Version: Skill Selection Hook (TypeSafe Jev)

## Option 1: Single Punchy Post (Recommended)

Ask an AI agent: *"Red dress or black dress tonight?"*

If you dumped 50 tools into its prompt, watch it spiral:
• Pings Doppler radar for humidity
• Scrapes 150 DMs to model her date's taste
• Queries bank API for wine spill limits

Burns $2 in compute to output: *"Wear both at once."*

Context pollution is quietly killing agent UX.

The fix? Jev for Decision Layer

1. **Decision Layer**  
A System 1 model (like @typesafe_ai's Jev) routes intent to the exact skill in **180ms**. Drops 49 irrelevant tools instantly.

1. **Execution Layer**  
Your LLM receives 1 clean tool, runs in a pristine context window, and answers in <1s.

The payoff:
→ 90% token reduction  
→ Sub-second latency  
→ Zero tool hallucinations  

Repo & hook implementation:  
<https://github.com/nghuyenthevinh2000/social-content#skill-selection-router-jev-hook>

---

## Option 2: 3-Tweet Thread

**1/3**  
Ask an AI agent: *"Red dress or black dress tonight?"*

If you stuffed 50 tools into its prompt, it spirals:
• Checks Doppler humidity
• Parses 150 DMs for date preferences
• Queries banking API for wine spills
Burns $2 to output: *"Wear both at once."*

Context pollution kills agent UX. Here's the fix 🧵👇

**2/3**  
Stop making your main LLM pick from 50 tools. Decouple it into 2 layers:

1. Decision (Reflex): A System 1 model (@typesafe_ai Jev) selects the exact skill in 180ms.
2. Execution (Hands): Main LLM gets *only* that tool in a pristine context window.

**3/3**  
By turning skill selection into a pre-invocation hook:
→ 90% fewer tokens
→ Sub-second responses
→ Zero tool hallucinations

Full implementation & open-source hook:  
<https://github.com/nghuyenthevinh2000/social-content#skill-selection-router-jev-hook>
