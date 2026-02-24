# Code Changes From Original NeuralNine Repository

All changes applied to the code from the [NeuralNine YouTube tutorial](https://www.youtube.com/watch?v=SA-YyejZ2Cs&t=4s).

The original repository had 5 bugs (4 critical) and a hard dependency on Arcade.dev + OpenAI that prevented anyone from running the app without those accounts. The refactored version works out of the box with zero configuration.

---

## Part 1: Bug Fixes

### Fix 1: Response variable returned as string literal

**File:** `agent_app/main.py`
**Severity:** Critical — the `/query` endpoint always returned the literal string `"response"` instead of the agent's answer.

```python
# BEFORE (broken)
return jsonify({'response': 'response'})

# AFTER (fixed)
return jsonify({'response': response})
```

### Fix 2: Drug name allowed to be null

**File:** `agent_app/models.py`
**Severity:** Medium — allowed drugs with no name into the database.

```python
# BEFORE
drug_name = db.Column(db.String(100), nullable=True)

# AFTER
drug_name = db.Column(db.String(100), nullable=False)
```

The transcript explicitly says "not nullable".

### Fix 3: Template references nonexistent field

**File:** `agent_app/templates/index.html`
**Severity:** Critical — `report.side_effect_date` does not exist in the `SideEffectReport` model. Causes a Jinja2 `UndefinedError` crash when rendering any drug with side effects.

```html
<!-- BEFORE (broken) -->
Probability: {{ (report.side_effect_probability * 100)|round(1) }}% |
Reported: {{ report.side_effect_date }}

<!-- AFTER (fixed) -->
Probability: {{ (report.side_effect_probability * 100)|round(1) }}%
```

The host likely had a `side_effect_date` column in an earlier version and removed it without updating the template.

### Fix 4: Module name shadowed by variable

**File:** `agent_app/main.py`
**Severity:** Critical — `import agent` on line 7 is overwritten by `agent = create_agent(...)` on line 26. The `agent.flask_app = app` assignment on line 17 would break.

```python
# BEFORE (broken)
import agent
agent.flask_app = app
agent = create_agent(...)

# AFTER (fixed)
import agent as agent_module
agent_module.flask_app = app
agent_executor = create_agent(...)
```

### Fix 5: Wrong import / parameter name for agent creation

**File:** `agent_app/main.py`
**Severity:** Critical — the original code used `from langchain.agents import create_agent` which did not exist at the time the video was published. It was later added in LangChain v1.2+ as a migration from `langgraph.prebuilt.create_react_agent`.

The current code uses:
```python
from langchain.agents import create_agent
agent_executor = create_agent('openai:gpt-4.1', all_tools, system_prompt=system_prompt)
```

This is now the correct import for LangChain >= 1.2.

### Bug fix summary

| # | File | Bug | Severity |
|---|------|-----|----------|
| 1 | `main.py` | String literal `'response'` instead of variable | Critical |
| 2 | `models.py` | `nullable=True` should be `False` | Medium |
| 3 | `index.html` | References nonexistent `side_effect_date` | Critical |
| 4 | `main.py` | Module name `agent` shadowed by variable | Critical |
| 5 | `main.py` | Wrong import / parameter for agent creation | Critical |

---

## Part 2: Architectural Changes

### Why the refactor was needed

The original code could not run without:
- An Arcade.dev account (to host the MCP server and provide Slack tools)
- The host's personal Arcade gateway URL (hardcoded as `gw_39TzUVKFdP5OrtcwKVf3qJRlmbH`)
- An OpenAI API key (for GPT-4.1)

If any of these were missing, the app crashed on startup.

### What changed

#### New file: `agent_app/clinical_trials.py`

Extracted the ClinicalTrials.gov API logic from the MCP server (`side_effects_mcp/src/side_effects_mcp/server.py`) into a standalone Python module. Same logic — queries the `/api/v2/studies` endpoint, iterates over studies, aggregates serious adverse event probabilities, filters by >1% threshold.

**Why:** This allows the Flask app to call the API directly without needing an MCP server, Arcade deployment, or any external infrastructure.

The MCP server version (`server.py`) uses raw dict access (`study['hasResults']`) which crashes on missing keys. The standalone version uses `.get()` with defaults for safer handling.

#### Changed: `agent_app/agent.py`

| What | Original | Now |
|------|----------|-----|
| Arcade gateway URL | Hardcoded string | Read from `ARCADE_GATEWAY_URL` env var |
| `get_mcp_tools()` | Crashes if keys missing | Returns `[]` if keys or packages missing |
| `langchain_mcp_adapters` import | Top-level (crashes if not installed) | Inside `get_mcp_tools()` with `try/except` |
| ClinicalTrials.gov tool | Only available via Arcade MCP | Also available as local `@tool` wrapping `clinical_trials.py` |
| `local_tools` list | 4 DB tools | 5 tools (added `get_side_effects_for_drug`) |

**Why:** The agent can now call ClinicalTrials.gov directly as a local LangChain tool, without routing through Arcade's MCP gateway. Arcade MCP tools (Slack etc.) are still loaded if the keys are present.

#### Changed: `agent_app/main.py`

| What | Original | Now |
|------|----------|-----|
| Agent activation | Required both `OPENAI_API_KEY` + `ARCADE_API_KEY` | Only requires `OPENAI_API_KEY` |
| Missing packages | `ImportError` crash | `try/except` with helpful message |
| Routes | `/` (home) + `/query` (agent only) | `/` (home) + `/search` (direct) + `/query` (agent) |
| `/search` route | Did not exist | Calls `clinical_trials.py` directly, stores in DB |
| System prompt | Always includes Slack instructions | Slack step only added if Arcade Slack tools detected |
| Agent variable | `agent` (shadowed module) | `agent_executor` |

**Why:** The app now starts in two possible modes:
- **Direct API only** — when no `OPENAI_API_KEY` is set. Only the `/search` route works.
- **Agent + Direct** — when `OPENAI_API_KEY` is set and LangChain packages are installed. Both `/search` and `/query` routes work.

#### Changed: `agent_app/templates/index.html`

| What | Original | Now |
|------|----------|-----|
| Search | None — only agent query box | Drug name search box (always visible) |
| Agent query | Always shown | Only shown when `agent_enabled=True` |
| Agent response | Auto-reloaded after 2 seconds (lost the response) | Stays on screen, user refreshes manually |
| Placeholder text | "notify on Slack" | No Slack references |
| Error handling | None | Shows network errors and API errors |

**Why:** The direct search box gives everyone a working UI with zero setup. The agent query section only appears when it's actually functional.

#### Changed: `agent_app/pyproject.toml`

```toml
# BEFORE — all dependencies required
dependencies = [
    "flask", "flask-sqlalchemy", "langchain-mcp-adapters",
    "langchain[openai]", "langgraph", "python-dotenv",
]

# AFTER — base deps minimal, LangChain optional
dependencies = [
    "flask", "flask-sqlalchemy", "python-dotenv", "requests",
]

[project.optional-dependencies]
agent = ["langchain[openai]", "langgraph"]
arcade = ["langchain[openai]", "langgraph", "langchain-mcp-adapters"]
```

**Why:** `pip install .` gives you a working app (direct mode). `pip install ".[agent]"` adds LangChain for agent mode. `pip install ".[arcade]"` adds MCP adapter for Arcade/Slack integration.

#### Changed: `agent_app/.env`

```env
# BEFORE — all keys required, no guidance
OPENAI_API_KEY=
ARCADE_API_KEY=
ARCADE_USER_ID=

# AFTER — commented guidance, gateway URL added
# Required for agent mode
OPENAI_API_KEY=

# Optional — adds Arcade MCP gateway + Slack notifications
#ARCADE_API_KEY=
#ARCADE_USER_ID=
#ARCADE_GATEWAY_URL=
```

**Why:** The original `.env` had no `ARCADE_GATEWAY_URL` — the URL was hardcoded in `agent.py` pointing to NeuralNine's personal gateway. Now it's configurable, and the Arcade keys are clearly marked as optional.

### Files summary

| File | Status | Change |
|------|--------|--------|
| `clinical_trials.py` | **New** | Standalone ClinicalTrials.gov API client |
| `main.py` | **Rewritten** | Direct search route, conditional agent init, three modes |
| `agent.py` | **Rewritten** | Local API tool, optional Arcade MCP, env-based config |
| `models.py` | **Fixed** | `nullable=False` on `drug_name` |
| `index.html` | **Rewritten** | Dual-mode UI, persistent agent response, error handling |
| `pyproject.toml` | **Changed** | Split dependencies into base / agent / arcade |
| `.env` | **Changed** | Added `ARCADE_GATEWAY_URL`, documented optional keys |
| `server.py` | **Unchanged** | Arcade MCP server (still available for deployment) |
