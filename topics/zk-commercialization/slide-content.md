# Slide Deck: Exploring ZK Commercialization: Perspectives & Realities
**Sub-heading:** Grounded Lessons from Vietnam: Deconstructing Enterprise & GovTech Hypotheses to Open New Heuristics  
**Speaker:** Ex-Senior Product Owner @ 1Matrix (Vietnam Blockchain Service Network - VBSN), worked on ZK lobbying to Government Cipher Committee (*Ban Cơ yếu Chính phủ*)

---

## Slide 1: Title & Framing
- **Slide Type:** Title & Perspective Hook
- **Header:** Commercializing Zero-Knowledge: Realities from the Field & Perspectives for the Future
- **Sub-header:** Unpacking initial expectations vs. on-the-ground reality in Vietnam to discover practical heuristics for ZK adoption.
- **Presenter Profile:**
  - Ex-Senior Product Owner, 1Matrix
  - Vietnam Blockchain Service Network (VBSN) initiative
  - Direct engagement with the Government Cipher Committee (*Ban Cơ yếu Chính phủ*) on ZK feasibility

> **Speaker Notes:**  
> "Welcome everyone. When we talk about Zero-Knowledge cryptography, the conversation is often dominated by two extremes: academic theory or Web3 rollup hype. A couple of years ago, while working at 1Matrix on the Vietnam Blockchain Service Network and exploring ZK feasibility with the Government Cipher Committee, we tried to take ZK into the messy real world of enterprises and public administration. Today, I don’t want to hand down rigid rules or proclaim that ZK can't work in enterprise. Instead, I want to transparently share our initial hypotheses, what we actually discovered on the ground, and open up an exploratory conversation about what heuristics and problem spaces we should be looking at next."

---

## Slide 2: Context & Overview — Pushing ZK in Vietnam
- **Slide Type:** Background & Context
- **Headline:** The Theoretical Promise vs. Primary Hurdles in the Field
- **Layout:** Two Contrasting Panels (The Promise vs. The Hurdles Discovered)

### The Promise (Initial Appeal):
- **Core Capability:** ZK technology fundamentally allows proving a statement without revealing the underlying data.
- **The Need in Vietnam:** Data laws prevent companies from sharing full client information, while citizens must reveal certificates to get notarized copies.
- **The Initial Hypothesis:** ZK seemed like a natural fit to eliminate repeated verification and protect personal information without transferring raw data.

### The Ground Reality (Primary Hurdles Discovered):
- **1. Database Fragmentation (The Biggest Hurdle):** Across both corporate groups and local government entities, underlying databases were so fragmented that unifying them or establishing a baseline was cost-prohibitive.
- **2. Government Sector Approval:** ZK is a new proving scheme requiring national approval from the Government Cipher Committee (*Ban Cơ yếu Chính phủ*), demanding multiple rounds of effect studies before deployment.

> **Speaker Notes:**  
> "To set the context: this talk is based on my real experience trying to push ZK technology in Vietnam. Initially, ZK seemed like an ideal fit because its core promise is proving without revealing—which fits right into data privacy laws and certificate verification needs. But as we explored real use cases, we encountered two massive hurdles: first, database fragmentation, which turned out to be the biggest hurdle of all; and second, the need for national cryptographic approval from the Government Cipher Committee for any public sector use. Let's walk through the actual use cases we explored."

---

## Slide 3: Case Study 1 — Unified Verification in a Mother Group
- **Slide Type:** Case Study (Enterprise)
- **Headline:** Can Verification Data at One Company Be Used for All Others?
- **Layout:** Two Contrasting Panels (Expectation vs. Reality)

### Initial Expectation:
- **The Legal Barrier:** Different companies in the same mother group in Vietnam cannot share full information of a client to one another due to data law.
- **The User Friction:** Users have to perform re-verification every time to different companies in the group.
- **The Core Question & ZK Fit:**
  - *Can verification data at one company be used for all others without revealing data?*
  - Initially, ZK seems like a good fit as it can prove without revealing.

### Ground Reality Discovered:
- **Database Fragmentation:** Even in the same mother group, different companies have different database structures.
- **The Unification Burden:** Cleaning and unifying them all requires far too much effort.
- **The Bottom Line:** The cost is not justified just for saving user time.

> **Speaker Notes:**  
> "Here was our experience with the mother group. In Vietnam, data laws prevent companies in the same mother group from sharing full client information with each other. Because of this, users have to re-verify every time they go to a different company in the group. We asked: can verification data at one company be used for all others without revealing data? Initially, ZK seemed like a great fit because it can prove without revealing. But when we dug in, even in the same mother group, different companies have different database structures. Cleaning and unifying them all required far too much effort. In the end, the cost simply wasn't justified just for saving user time."

---

## Slide 4: Case Study 2 — ZK for Public Notary & Citizen Certificates
- **Slide Type:** Case Study (GovTech)
- **Headline:** Proving Certificate Validity Without Revealing Personal Information
- **Layout:** Two Contrasting Panels (Expectation vs. Reality)

### Initial Expectation:
- **The Status Quo:** A person has to reveal certificate information to get notarized copies by the authority.
- **The ZK Idea:** If that person has a registry for all certificates, he can prove to companies without revealing personal information.
- **The Key Prerequisite:** This is only viable if there is a government entity with all the citizen certificate data first to enable a ZK layer on top.

### Ground Reality Discovered:
- **The Investigation:** Exploring where citizen certificate data actually resided across local government entities.
- **The Ground Reality:** Databases in local government entities were so fragmented, that no one has all of it.
- **The Structural Barrier:** Without a government entity possessing complete citizen certificate data, there is no foundational baseline to enable a ZK layer on top.

> **Speaker Notes:**  
> "Our second use case was public notary. Today, a person has to reveal certificate information to get notarized copies by the authority. If that person had a registry for all certificates, he could prove to companies without revealing personal information. But this is only viable if there is a government entity with all the citizen certificate data first to enable a ZK layer on top. Eventually, we found out that databases in local government entities were so fragmented, that no one has all of it. Without that base data in one place, you simply cannot enable a ZK layer on top."

---

## Slide 5: The Institutional Barrier — Novel Cryptography vs. National Security
- **Slide Type:** Regulatory & Governance Perspective
- **Headline:** Navigating the Government Cipher Committee (*Ban Cơ yếu Chính phủ*)
- **The Institutional Landscape:**
  - In Vietnam, cryptographic algorithms used across public administration, critical national infrastructure, and high-security enterprise systems are strictly governed by the Government Cipher Committee (*Ban Cơ yếu Chính phủ*).
- **The Fundamental Tension:**
  - **Novelty vs. Certifiability:** ZK proving systems (Groth16, PLONK, Halo2, STARKs) are bleeding-edge cryptography involving novel elliptic curves, pairing assumptions, and complex polynomial commitments.
  - **The Vetting Process:** To approve a new proving scheme for national infrastructure, the committee requires extensive multi-round effect studies, vulnerability analysis, and formal academic proofs.
  - **Timeline Asymmetry:**
    - Startup/pilot innovation cycles: *Weeks to months.*
    - National cryptographic evaluation & certification: *Multiple years.*
- **Takeaway:** In regulated GovTech, institutional trust and official cryptographic clearance matter far more than theoretical mathematical elegance.

> **Speaker Notes:**  
> "Even if we assume the database issue could be solved, we hit a third, insurmountable hurdle: regulatory and cryptographic accreditation. When pushing cutting-edge tech in Vietnam's public or semi-public sector, you work closely with the Government Cipher Committee (Ban Cơ yếu Chính phủ). Their mandate is national cryptographic security. ZK is not just an API; it is an entirely new proving scheme relying on novel curves and mathematical assumptions. 
> 
> The Cipher Committee cannot simply 'greenlight' a new scheme because it is popular in Web3. It requires formal evaluation, vulnerability modeling, and multi-year effect studies. Startups and commercial pilots operate on quarter-to-quarter runways; sovereign cryptography operates on multi-year validation cycles. Navigating this asymmetry is a critical reality anyone planning enterprise ZK must account for."

---

## Slide 6: Discussion 1 — Applying Functional Analysis to ZK
- **Slide Type:** Methodological Inquiry / First-Principles Discussion
- **Headline:** Question 1: What Are We Actually Selling When We Strip Away the Hype?
- **Methodology — Functional Analysis:**
  - In systems engineering and product architecture, when a technology struggles to find adoption, we run **Functional Analysis**: deconstructing the system down to its irreducible, elementary functions (independent of branding, narratives, or specific implementations).
- **The Single Function We Bet On:**
  - **Function: Input Concealment (Zero-Knowledge Masking)**
    - *Definition:* Proving a witness $w$ satisfies predicate $P(x, w) = \text{true}$ without revealing $w$.
    - *Our Pilot Bet:* Privacy, selective disclosure, and compliance under Decree 13.
    - *The Ground Reality:* Input Concealment strictly requires standardized, authoritative data inputs—and collided directly with fragmented legacy databases.
- **The Open Question for the Room:**
  - We bet 100% of our enterprise roadmap on this single function (Input Concealment).
  - *What are the OTHER basic, atomic functions of ZK?* (Even if they seem obvious or well-known to you!)
  - When we strip away marketing, what fundamental capabilities does ZK have that we completely overlooked?

> **Speaker Notes:**  
> "When our pilots stalled, we turned to a systems engineering tool: **Functional Analysis**. Whenever a technology hits adoption roadblocks, product designers step back and ask: what does this system actually do at its most elementary, atomic level—free from marketing hype and jargon?
> 
> Looking back at our pilots, our entire commercial strategy was anchored on just ONE single function: **Input Concealment**—proving a statement without revealing the underlying data. And that single choice led us straight into the buzzsaw of dirty, fragmented enterprise databases.
> 
> I don't want to list the other functions on this slide, because I want to hear from you. When you run functional analysis on ZK from first principles, what are the OTHER basic, atomic functions of ZK? Even if they seem elementary or well-known to you—what other fundamental capabilities does ZK have that we overlooked?"

---

## Slide 7: Open Discussion — Perspectives, Heuristics & Field Problems
- **Slide Type:** Interactive Discussion & Open Floor
- **Headline:** Opening the Floor: Questions for Builders & Practitioners
- **The Perspective-Heuristics Method:**
  - In complex problem-solving, breakthroughs happen by shifting our **Perspective** (how we frame the problem space) and developing practical **Heuristics** (rules of thumb for evaluating solutions).
  - Having deconstructed ZK's functions, we use this method to explore where real commercial value actually lives.
- **Open Questions to Explore Together:**
  1. **Heuristics for Fit:** What mental filters or rules of thumb do you use to evaluate whether a problem actually warrants ZK, rather than traditional databases and APIs?
  2. **Field Problems & Perspectives:** Beyond classic identity (DID) and notary tropes, what real-world problems in your domain can be cleanly solved by ZK's basic functions?
- **Open Q&A & Collective Discussion**
- **Speaker Contact / Connect:** [Speaker Contact / LinkedIn / Telegram]

> **Speaker Notes:**  
> "I want to open up the floor to everyone in this room. To guide our discussion, I like to use the **Perspective-Heuristics method**. When a powerful technology hits adoption roadblocks, it usually means our initial perspective was too narrow, or our heuristics for picking use cases were flawed. A perspective is how we represent the problem space, while heuristics are the practical rules of thumb we use to search for solutions. 
> 
> Rather than handing down rigid answers, I want to leave you with two simple questions:
> First, what heuristics do you use to evaluate whether an idea genuinely warrants ZK versus traditional architectures? 
> And second, from your perspective, what field problems in your own industries could be cleanly solved by ZK's basic functions without falling into database fragmentation traps? 
> Let's open it up for your perspectives."
