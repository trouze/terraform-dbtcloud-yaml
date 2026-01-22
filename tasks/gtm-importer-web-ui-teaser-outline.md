# GTM Presentation Outline: Importer Web UI (Teaser)

## 1. Title & Executive Summary
- **Title:** dbt Cloud Importer Web UI — Confident, Low-Risk Migrations in Minutes
- **Summary:** The Importer Web UI replaces brittle, expert-only migration scripts with a guided workflow that **helps reduce time to activation** (Onboard → Activation) and **mitigates risk exposure** by keeping migrations inside dbt's business logic. It also **accelerates time to value** by letting teams adopt existing infrastructure into Terraform, with jobs-as-code as a lightweight optional path.
- **Length:** 3–5 minutes

## 2. Agenda (3–5 min)
1. Problem & urgency (40s)
2. Complexity & edge cases (40s)
3. What the Importer Web UI delivers (60s)
4. Licensing model & PS alignment (40s)
5. Quick UI tour (60–90s)
6. Wrap + seller takeaway (30s)

## 3. Slide-by-Slide Outline

**Slide 1 — "Why migrations fail today"**
- **Key Message:** Existing migration methods are brittle because they operate outside dbt Cloud's business logic.
- **Content Bullets:**
  - Manual scripts and native imports are **expert dependent**
  - Dependencies across jobs/environments/connections are easy to miss
  - Failures create rework, delays, and risk exposure
  - Inconsistent migrations slow adoption and expansion
- **Value Driver Mapping:** Improve Data Quality & Trust
- **Talk Track:** "Today, dbt account migration is a high-risk, expert-only motion. You're stitching together manual scripts, native DB migrations, and Terraform importers that often sit **outside the dbt platform logic**, which **reduces manual rework** only when everything lines up perfectly."

**Slide 2 — "Complexity you can't ignore"**
- **Key Message:** dbt Platform's object model is deeply interconnected.
- **Content Bullets:**
  - Show Fivetran dbt Platform provider ERD graphic
  - Projects → Environments → Jobs → Connections dependencies
  - One change often ripples across multiple objects
- **Value Driver Mapping:** Improve Data Quality & Trust
- **Talk Track:** "This ERD makes the risk real. A single project liniks to environments that link to jobs, connections, repos, tokens—miss one, and the deploy breaks. That's why you need platform-aware logic to **mitigate risk**."

**Slide 3 — "Introducing dbt Magellan"**
- **Key Message:** A migration-ready tooling experience plus adoption into infrastructure as code.
- **Content Bullets:**
  - Scales migrations inside Professional Services
  - Removes dependency on deep Terraform/dbt Cloud internals expertise
  - Enables Hyperscaler, region, ST → MT moves
  - **Adopt existing infrastructure into Terraform**

- **Value Driver Mapping:** Improve Data Quality & Trust; Drive Efficiency & Reduce Cost
- **Talk Track:** "dbt Magellan is a clean migration unlock and an adoption path into infrastructure as code. It lets Professional Services scale migrations by reducing the need for deep CLI/Terraform expertise, shifting the work to project management and external dependencies while standardizing migration scope and reducing drift risk."

**Slide 4 — "The real magic: guided expert workflow"**
- **Key Message:** Guided steps cover edge cases while keeping sensible defaults.
- **Content Bullets:**
  - Fetch → Explore → Map → Target → Deploy
  - Expert-grade edge case handling
  - Sensible defaults + assumptions to get to done
  - Full account or subset moves with dependencies intact
- **Value Driver Mapping:** Improve Data Quality & Trust; Drive Efficiency & Reduce Cost
- **Talk Track:** "The real magic is the guided workflow: it covers many edge cases and nuances common to complex customers, but still **accelerates time to value** with sensible defaults and advanced logic. That's how we **help reduce time to activation** without needing a migration expert on every engagement."

**Slide 5 — "Licensing model & PS alignment"**
- **Key Message:** We can run anywhere, but advanced migration is licensed to protect expertise and value.
- **Content Bullets:**
  - Docker image can run anywhere
  - **Account explorer may be unlicensed**
  - Migration/normalize/deploy gated by license key
  - Supports PS-led engagements; flexibility later
- **Value Driver Mapping:** Drive Efficiency & Reduce Cost
- **Talk Track:** "We can ship the Docker image to run anywhere we want it to, but migration actions are **license-gated**. That protects the expert workflow as a paid PS engagement, while still allowing GTM employees to use exploratory features to scope the migration in advance."

**Slide 6 — "Quick UI tour (what it looks like)"**
- **Key Message:** The UI makes complex migrations feel simple and safe.
- **Content Bullets:**
  - Wizard steps with progress and persistence
  - Explore views: summary, report, entity table, charts
  - Map step: select scope + handle dependencies
  - Deploy: plan/apply with real-time logs
- **Value Driver Mapping:** Drive Efficiency & Reduce Cost
- **Talk Track:** "This is the 'cool factor' slide: clear steps, filtering, charts, and a path from selection to deployment. The workflow **eliminates manual rework**."

**Slide 7 — "Objection handling"**
- **Key Message:** Handle common objections with platform-aware differentiation.
- **Content Bullets:**
  - "Isn't this just a Terraform wrapper?"
  - "We already have migration scripts."
  - "Why is it licensed?"
- **Value Driver Mapping:** Improve Data Quality & Trust; Drive Efficiency & Reduce Cost
- **Talk Track:** "We handle the three predictable objections head-on: platform-aware dependency logic, reduction in expert-only risk, and licensed access to protect the expert workflow for PS-led engagements."

**Slide 8 — "Seller takeaway"**
- **Key Message:** A concrete migration story that closes risk objections.
- **Content Bullets:**
  - **Mitigate risk exposure** with controlled dependency handling
  - **Reduce time to activation** for account moves
  - Scales PS migrations by reducing expert-only bottlenecks
  - Shortens Onboard → Activation, sets up faster Adoption
  - Adoption path into Terraform with an optional jobs-as-code path
- **Value Driver Mapping:** Improve Data Quality & Trust; Drive Efficiency & Reduce Cost
- **Talk Track:** "For Sellers, this is both a migration wedge and a governance wedge. It **supports compliance readiness** while creating a more repeatable path to scale."

## 4. Product Demo Flow (60–90s)

**Demo Section 1 — "Start & Fetch"**
- **Setup/Prerequisites:** Sample account creds; show existing output dir
- **Step-by-Step Flow:**
  1. Open UI on Home → Start New Migration
  2. Enter source creds → Fetch
  3. Show streaming logs
- **Value Callouts:** Reduce time to activation; eliminate manual rework
- **Proof Points:** "Fetch completes in minutes; same pipeline as CLI."
- **Transition to Next Section:** "Now explore and confirm scope."

**Demo Section 2 — "Explore & Map"**
- **Setup/Prerequisites:** Fetched data loaded
- **Step-by-Step Flow:**
  1. Summary/report tabs
  2. Entity table filter
  3. Select subset (env + jobs)
- **Value Callouts:** Mitigate risk exposure; enable self-service
- **Proof Points:** "Selection persists and enforces dependency awareness."
- **Transition to Next Section:** "Now target and deploy."

**Demo Section 3 — "Target & Deploy (teaser)"**
- **Setup/Prerequisites:** Target creds stubbed
- **Step-by-Step Flow:**
  1. Target creds + provider config
  2. Show Generate Files / Plan buttons
  3. Mention import flow for adopting existing infra
- **Value Callouts:** Standardize migration scope; reduce manual rework
- **Proof Points:** "Same workflow across hyperscalers; adopt existing infra into Terraform."
- **Transition to Next Section:** "That's the full end-to-end path."

## 5. Close & Next Steps
- **Summary:** Guided, platform-aware migrations that **accelerate time to value**, **help reduce time to activation**, and enable adoption into Terraform—with licensed control of advanced actions.
- **CTA:** "Use this to position migrations as safe, fast, and PS-backed."
- **Resources:** PRDs, demo recording, importer README
