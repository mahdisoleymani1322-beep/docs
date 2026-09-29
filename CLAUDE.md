# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository nature

This is a documentation-only repository: no code, build, lint, or test tooling. It holds three Persian (Farsi, RTL) Markdown playbooks. The files have **no `.md` extension** and Persian filenames:

| File | Guide for |
|---|---|
| `پرپوزال` | Writing a B2B sales/consulting proposal or RFP response |
| `کاتالوگ` | Building a product/service catalog (10-page SaaS/services structure) |
| `پیچ` | Building a pitch deck (investment / sales / partnership; 14-slide structure) |

Each is a standalone "executive guide" written for a downstream AI or human writer. Content is in Persian; keep new text in Persian with the existing terminology, and keep Latin script for URLs, emails, codes and English acronyms (TAM, ARR, CAC, RFP, etc.).

## Shared structure across the three guides

The guides deliberately follow the same skeleton, so edits to one usually need to be mirrored in the others:

1. Intro stating the output of the guide and that page counts, word budgets and rubric are *editorial suggestions*, not standards. Includes a "sources reviewed on" date (۱۱ سپتامبر ۲۰۲۶).
2. Document-type / decision-stage table (why this document and not a neighbor document).
3. Mandatory client input form (fenced `text` block; "unknown" is valid but needs an owner and due date).
4. Research and evidence-ledger process (ID-keyed table: `P-xx`, `C-xx`, `E-xx`).
5. Section-by-section (or slide/page-by-page) architecture. Every unit uses the same seven fields: **هدف، سؤال، داده لازم، قالب، نمونه خوب، خطای رایج، قبولی**.
6. Critical analysis of supplied sample documents (Arkan template, Bina Experts, ApplyScore) and real-world examples, always stating the limits of what can be transferred.
7. Persian writing rules, design/accessibility rules (WCAG contrast 4.5:1 / 3:1, PDF reading order).
8. Multi-stage review process and final checklist.
9. 100-point weighted rubric (score 0–4 per row, `weight × score ÷ 4`; ship threshold 85, no row under 2; instant-reject list).
10. Fill-in output template (fenced `text` block).
11. Self-contained "mother prompt" (fenced `text` block) — the operational prompt that encodes all of the above. Changes to rules in the body must be reflected here and in the rubric weights.
12. Numbered sources list, cited in-text as `[۱]`, `[۲]`, ….

## Conventions to preserve

- **Epistemic honesty is the core rule**: never turn a target, assumption or demo into a fact. Claims are labeled واقعی / محاسبه / فرض / هدف. Do not invent customers, numbers, prices, quotes or sources; sample numbers are illustrative only.
- **LeadBridge AI** is the running example product. It is only described as: lead discovery, analysis, scoring, message drafting handed to a human for approval. SaaS readiness, live CRM connection, revenue, multi-tenancy, SLAs and business results must not be claimed without evidence. Proposal pricing is distinct from the "no pricing in outreach messages" rule of the product. It is cited as source `[۸]` (proposal, catalog) / `[۱۰]` (pitch) pointing to the product's own CLAUDE.md/README on a local machine; those paths are not available here.
- Citation numbers are per-file and in-text markers must match the file's own source list; if you add/remove a source, renumber consistently within that file only.
- Some sources are private local files (Windows paths) and are labeled as such with unknown publication dates; keep that labeling rather than presenting them as public.
- If the rubric weights change, update both the rubric table (sums to ۱۰۰) and the mother prompt's rubric line in the same file.
- Persian typography: Persian digits in prose, ZWNJ (نیم‌فاصله), Persian ی/ک only.
