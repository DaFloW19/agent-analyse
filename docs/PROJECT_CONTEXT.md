# Project Context

## Product Vision

The AI Growth Automation System is a white-label agentic marketing team. It runs the full funnel for a client: traffic acquisition, lead qualification, nurturing, appointment booking, CRM hygiene, performance analysis, and optimisation feedback.

The project currently targets 7 agents:

1. Commander
2. CRM Keeper
3. Qualifier
4. Content & Conversion Strategist
5. Media Buyer
6. Closer
7. Analyst

## Development Phases

### Phase A - POC

Minimal proof that the agent works. Logic can be hardcoded, Telegram can be the first interface, and logs are append-only local JSON files.

### Phase B - Intelligence Layer

Adds LLM decisions, real data adapters, central logging, reports, alerts, and Langfuse tracing for real model calls.

### Phase C - Production-Ready

Adds multi-client and multi-industry behaviour, adaptive feedback loops, full Langfuse observability, evaluations, guardrails, and production deployment readiness.

## Analyst Role

The Analyst is the only agent whose main job is to look backward. It studies what happened, calculates the KPIs, identifies patterns, and sends optimisation signals to the Commander, Media Buyer, Content & Conversion Strategist, and Qualifier.

The Analyst does not execute operational changes directly. It does not change budgets, send messages, edit leads, or publish content. It computes, observes, reports, recommends, and logs.

## Analyst As Binome

Whenever another agent is called for a task, the Analyst should be able to accompany that agent as an observation binome.

In binome mode, the Analyst receives a structured summary of the task and returns:

- which KPIs may be affected
- which guardrails should be checked
- which data should be logged
- what risks or anomalies to watch
- whether the task is safe to continue from an analysis perspective

This observation must be side-effect free. The Analyst may recommend or flag, but the active agent and Commander remain responsible for execution.

## Canonical KPIs

All KPI calculations must eventually live in `common/metrics.py` and must not be reimplemented elsewhere.

- CPL: total ad spend / total form submissions
- CPQ: total ad spend / leads with score >= 31
- CPQL: total ad spend / leads with score >= 61
- CPBD: total ad spend / appointments successfully booked
- ROAS: total contract value of `closed_won` deals / total ad spend
- Stage conversion rate: percentage moving from one pipeline stage to the next
- Time to first contact: average minutes from form submission to first Closer message
- Response rate: percentage of first-contact messages replied to within 48 hours
- Meeting show rate: percentage of booked meetings where the lead showed up

## Source Documents

- `docs/ANALYST_AGENT_WORK_PLAN.md`: current execution plan and hardening brief.
- `docs/agent_dev_roadmap_v3.pdf`: original product roadmap and agent role definitions.

