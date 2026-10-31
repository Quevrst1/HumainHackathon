# Kurrasa (كراسة): AI Tender Agent

HUMAIN Hackathon, Challenge 3 (Autonomous Enterprise).

A department sends Procurement a short request (department, need, budget). Kurrasa interviews them until the need is clear, checks the request against the company's procurement rules and Saudi data-protection law, flags problems and agrees fixes with the requester, then writes the Arabic tender booklet (كراسة الشروط والمواصفات) as a PDF.

The test company, Sahab, is fictional, but its rules come from real sources.

## Data

| Source | Used for | How we got it |
|---|---|---|
| 312 Etimad tender listings | purchase types and timelines in the scenarios | Apify, `scripts/fetch_etimad.py`, cleaned by `scripts/clean_etimad.py` |
| MoF standard services booklet | the tender template | `scripts/fetch_sources.py` |
| A Saudi listed company's published procurement policy (not named) | purchasing methods and approval limits | saved privately, available on request |
| PDPL and the SDAIA data-transfer regulation | rules on personal data | downloaded by hand from SDAIA |
| NCA Essential Cybersecurity Controls (ECC-2:2024) | rules for cloud providers | `scripts/fetch_sources.py` |

URLs, dates and SHA-256 hashes for the downloaded files are in `data/research/sources_manifest.json`. Sahab's profile and the test scenarios were written for this project, following those rules.

## Setup

```bash
conda env create -f environment.yaml
conda activate humain-env
cp .env.example .env    # add GEMINI_API_KEY, plus DEEPSEEK_API_KEY and OPENROUTER_API_KEY for the judges
```

## Run

```bash
streamlit run app.py                          # the UI
python main.py --scenario laptops_brand_locked # one scenario with a simulated requester
python main.py --human                         # answer Kurrasa's questions yourself
python evaluate.py                             # every scenario, scored by the judges
python -m pytest                               # tests
```

## How it works

Kurrasa is a tool-calling agent (Gemma 4 26B through the Gemini API) that works in three stages and only gets the tools for the current one:

| Stage | Tools |
|---|---|
| Interview | `ask_requester`, `record_requirement` |
| Checks | `purchase_route`, `raise_issue`, `resolve_issue` (it can still ask the requester) |
| Draft | `write_section`, `finish` |

The purchasing method comes from the company thresholds in code, not from the model, and the budget never appears in the tender. In the UI, Finance and Legal are simulated steps around the agent.

## Evaluation

Ten scenarios in five pairs: each purchase has a version with one planted problem and a clean version without it. An LLM plays the requester and only reveals hidden requirements when asked. Three judges from different model families (DeepSeek, Llama 3.3 70B, Gemini Flash-Lite) score each tender against an answer key the agent never sees, by majority vote. One pair is held out and only run at the end.

We measure whether the planted problem was recorded, false alarms on clean requests, and how many hidden requirements made it into the tender.

## Layout

```
src/kurrasa/
  agents/     the agent loop, tools and requesters
  config/     models, LLM factory, prompts
  pipeline/   running scenarios and scoring them
  services/   company rules, events, PDF
  ui/         Streamlit helpers
data/company/   facts.yaml (Sahab's rules) and the tender template
data/research/  Etimad listings and the source manifest
scenarios/      test scenarios and answer keys
scripts/        data fetching and scenario checks
```
