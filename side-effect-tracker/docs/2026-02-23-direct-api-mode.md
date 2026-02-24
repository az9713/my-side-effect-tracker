# Direct ClinicalTrials API Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the app work out of the box by calling ClinicalTrials.gov directly, with Arcade MCP as an optional upgrade.

**Architecture:** Extract the API logic from `server.py` into a standalone `clinical_trials.py` module. Add a `/search` route that calls it directly. Keep the `/query` agent route but gate it behind API key checks. UI defaults to the simple search.

**Tech Stack:** Flask, SQLAlchemy, requests, ClinicalTrials.gov API v2

---

### Task 1: Create `clinical_trials.py` module

**Files:**
- Create: `agent_app/clinical_trials.py`

Extract the ClinicalTrials.gov API logic from `side_effects_mcp/src/side_effects_mcp/server.py` into a standalone function.

### Task 2: Add `requests` to agent_app dependencies

**Files:**
- Modify: `agent_app/pyproject.toml`

### Task 3: Refactor `main.py` — direct search + optional agent

**Files:**
- Modify: `agent_app/main.py`

Add `/search` POST route that calls `clinical_trials.py` directly and stores results in DB. Gate agent setup behind API key checks so the app starts without any keys.

### Task 4: Refactor `agent.py` — make MCP tools optional

**Files:**
- Modify: `agent_app/agent.py`

Move `GATEWAY_URL` to env var. Guard `get_mcp_tools()` so it doesn't crash without Arcade keys.

### Task 5: Update `.env` template

**Files:**
- Modify: `agent_app/.env`

### Task 6: Update `index.html` — dual-mode UI

**Files:**
- Modify: `agent_app/templates/index.html`

Default: simple drug name search box calling `/search`. Optional: agent query box (shown when agent mode available). Pass `agent_enabled` flag from Flask.

### Task 7: Verify

Run `python main.py` with empty `.env` — app should start and search should work.
