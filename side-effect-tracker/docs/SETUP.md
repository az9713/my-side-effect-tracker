# Medical Side Effect Tracker — Setup and Architecture Guide

Based on the [NeuralNine YouTube tutorial](https://www.youtube.com/watch?v=SA-YyejZ2Cs&t=4s). Refactored to work out of the box with zero configuration, with optional OpenAI agent mode and optional Arcade/Slack integration.

---

## Project Structure

```
side-effect-tracker/
  agent_app/                       # Flask web application
    main.py                        # Entry point, routes, agent init
    models.py                      # SQLAlchemy models (Drug, SideEffectReport)
    clinical_trials.py             # Direct ClinicalTrials.gov API client
    agent.py                       # LangChain tools + optional Arcade MCP
    templates/index.html           # Web UI
    .env                           # API keys
    pyproject.toml                 # Dependencies
  side_effects_mcp/                # Arcade MCP server (optional, deploy separately)
    src/side_effects_mcp/server.py
```

---

## Three Modes of Operation

### 1. Direct Mode (zero configuration)

```bash
pip install .
python main.py
# -> "Starting in mode: Direct API only"
```

**What happens:** You type a drug name, Flask calls ClinicalTrials.gov directly via `clinical_trials.py`, stores results in SQLite, displays them. No LLM, no API keys, no accounts.

**API keys needed:** None.

### 2. Agent Mode (OpenAI key only)

```bash
pip install ".[agent]"
# Set OPENAI_API_KEY in .env
python main.py
# -> "Agent mode: enabled (OpenAI)"
# -> "Starting in mode: Agent + Direct"
```

**What happens:** Everything from direct mode, plus an AI Agent Query box. You type natural language queries. GPT-4.1 reasons about what tools to call, fetches data, updates the DB, and returns a summary.

**API keys needed:** `OPENAI_API_KEY` only.

### 3. Arcade Mode (OpenAI + Arcade + Slack)

```bash
pip install ".[arcade]"
# Set OPENAI_API_KEY, ARCADE_API_KEY, ARCADE_USER_ID, ARCADE_GATEWAY_URL in .env
python main.py
# -> "Agent mode: enabled (OpenAI + Arcade/Slack)"
```

**What happens:** Everything from agent mode, plus Slack notifications when new side effects are found. This is the full architecture from the NeuralNine video.

**API keys needed:** `OPENAI_API_KEY`, `ARCADE_API_KEY`, `ARCADE_USER_ID`, `ARCADE_GATEWAY_URL`.

---

## Setup Steps

### Direct mode

1. `cd side-effect-tracker/agent_app`
2. `python -m venv venv && venv/Scripts/activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
3. `pip install .`
4. `python main.py`
5. Open `http://127.0.0.1:5000`

### Agent mode

1. Complete direct mode setup
2. `pip install ".[agent]"` — installs `langchain[openai]` and `langgraph`
3. Get an OpenAI API key from https://platform.openai.com/api-keys
4. Edit `.env`:
   ```
   OPENAI_API_KEY=sk-proj-...your-key...
   ```
5. `python main.py`

### Arcade mode (adds Slack)

1. Complete agent mode setup
2. `pip install ".[arcade]"` — also installs `langchain-mcp-adapters`
3. Sign up at https://arcade.dev
4. Deploy the MCP server:
   ```bash
   cd side-effect-tracker/side_effects_mcp
   pip install arcade-mcp-server
   arcade deploy -e src/side_effects_mcp/server.py
   ```
5. Create an MCP gateway in the Arcade dashboard:
   - Select tools: `get_side_effects_for_drug`, `Slack.SendMessage`, `Slack.WhoAmI`, `Slack.GetUserInfo`, `Slack.GetConversationMetadata`
   - Authentication: Headers
   - Copy the gateway URL
6. Get your Arcade API key from the dashboard
7. Edit `.env`:
   ```
   ARCADE_API_KEY=arc_...your-key...
   ARCADE_USER_ID=you@example.com
   ARCADE_GATEWAY_URL=https://api.arcade.dev/mcp/gw_...your-gateway-id...
   ```
8. `python main.py`

---

## API Keys Summary

| Key | Mode | Where to get it | Cost |
|-----|------|-----------------|------|
| *(none)* | Direct | N/A | Free (ClinicalTrials.gov is a public API) |
| `OPENAI_API_KEY` | Agent | https://platform.openai.com/api-keys | Pay-per-use |
| `ARCADE_API_KEY` | Arcade | Arcade dashboard | Free tier available |
| `ARCADE_USER_ID` | Arcade | Your Arcade account email | N/A |
| `ARCADE_GATEWAY_URL` | Arcade | Arcade dashboard > MCP Gateways | N/A |

---

## The Role of Each Technology

### ClinicalTrials.gov API (the data source)

ClinicalTrials.gov is a US government database of clinical studies. The app uses its public REST API (`https://clinicaltrials.gov/api/v2/studies`) to fetch drug trial data. No authentication or API key is required.

When queried with a drug name (e.g. "paracetamol"), the API returns up to 25 studies sorted by most recent results. Each study may contain an `adverseEventsModule` with `seriousEvents` — these are the reported serious side effects from the trial, including how many participants were affected (`numAffected`) out of how many were at risk (`numAtRisk`).

The app aggregates these across all studies: if three studies report "headache" with probabilities 5%, 3%, and 4%, the aggregated probability is the average (4%). Only side effects above 1% probability are kept.

This API is the single source of truth for all drug side effect data in the app. Every mode (direct, agent, arcade) ultimately calls the same endpoint. The difference is *how* the call is made and *what happens* with the results.

### GPT-4.1 (the brain)

GPT-4.1 is the large language model that powers the agent. It receives the user's natural language query and a list of available tools (with their names, parameters, and descriptions). It then **decides** which tools to call, in what order, and with what arguments.

For example, when you ask "Get me side effects of paracetamol", GPT-4.1:
1. Decides to call `list_drugs()` to check the database
2. Sees paracetamol isn't there, calls `create_drug("paracetamol")`
3. Calls `get_side_effects_for_drug("paracetamol")` to fetch from ClinicalTrials.gov
4. Calls `create_side_effect(...)` for each result to store them
5. Composes a natural language summary of what it found

GPT-4.1 doesn't execute any code itself. It only decides *what* to do. The actual execution is handled by LangChain.

**Without GPT-4.1:** No agent mode. Only direct search, which runs hardcoded logic (call API, store everything, display raw list). No reasoning, no summarisation, no natural language interaction.

### LangChain (the glue)

LangChain is a Python framework that connects GPT-4.1 to your tools. It provides:

- **`@tool` decorator** — wraps Python functions into a schema that GPT-4.1 can understand. The LLM sees the function name, parameter types, and docstring.
- **`create_agent`** (from `langchain.agents`) — builds a ReAct (Reason + Act) loop:
  1. Send user query + tool schemas to GPT-4.1
  2. GPT-4.1 responds with a tool call
  3. LangChain executes the tool, sends the result back to GPT-4.1
  4. Repeat until GPT-4.1 returns a final text answer

LangChain itself doesn't need an API key. It's just the orchestration layer. The API key is for OpenAI (the LLM provider).

**Without LangChain:** You'd have to write the ReAct loop yourself — parse GPT-4.1's tool call JSON, dispatch to the right Python function, format results, handle errors, and loop until done. LangChain does this in one function call.

### Arcade.dev (the infrastructure — optional)

In the original NeuralNine video, Arcade served three purposes:

1. **Hosted the MCP server** — instead of running the ClinicalTrials.gov tool locally, it was deployed to Arcade's cloud. Arcade runs it and exposes it via an HTTP gateway URL.

2. **Provided pre-built Slack tools** — `SendMessage`, `WhoAmI`, etc. with OAuth handled by Arcade. Without it, you'd need to create a Slack app, manage OAuth tokens, and write the API calls yourself.

3. **MCP gateway** — a single authenticated URL that bundles multiple tools (custom + Slack). LangChain connects to one URL and gets all tools at once via the `langchain-mcp-adapters` package.

**Without Arcade:** The app works fine. The `get_side_effects_for_drug` tool runs locally as a LangChain `@tool` that calls `clinical_trials.py` directly — same function, runs in-process, no deployment needed. You lose Slack notifications, but the core functionality (search, store, summarise) is unchanged.

### Communication Flows

**Agent mode WITHOUT Arcade (OpenAI only):**

Everything runs locally. GPT-4.1 is the only external service besides ClinicalTrials.gov.

```
 User
  |
  | "Get me side effects of paracetamol"
  v
+------------------+
|  Browser (UI)    |
+------------------+
  |  POST /query
  v
+------------------+       +------------------+
|  Flask app       |       |  OpenAI API      |
|  (main.py)       |       |  (GPT-4.1)       |
+------------------+       +------------------+
  |                              ^    |
  v                              |    | tool call decisions
+-----------------------------+  |    |
|  LangChain ReAct loop       |--+    |
|  (send tool results to LLM, |<------+
|   receive next tool call)    |
+-----------------------------+
  |           |           |
  | tool      | tool      | tool
  | calls     | calls     | calls
  v           v           v
+----------+ +----------+ +---------------------------+
| SQLite   | | SQLite   | | clinical_trials.py        |
| (read)   | | (write)  | | get_side_effects_for_drug |
|          | |          | +---------------------------+
|list_drugs| |create_   |   |
|list_side | | drug     |   | HTTP GET
| effects  | |create_   |   v
|          | | side_    | +---------------------------+
|          | | effect   | | ClinicalTrials.gov API    |
+----------+ +----------+ | /api/v2/studies           |
      |           |        | (public, no auth needed)  |
      v           v        +---------------------------+
  +----------------+
  | instance/      |
  | drugs.db       |
  +----------------+
```

The ReAct loop typically runs 5-8 rounds:
1. LangChain sends query + tool schemas to GPT-4.1
2. GPT-4.1 returns: call `list_drugs` -> LangChain executes -> sends result back
3. GPT-4.1 returns: call `create_drug("paracetamol")` -> execute -> send back
4. GPT-4.1 returns: call `get_side_effects_for_drug("paracetamol")` -> execute -> send back
5. GPT-4.1 returns: call `create_side_effect(...)` (repeated per side effect)
6. GPT-4.1 returns: final text summary -> LangChain returns to Flask -> JSON to browser


**Agent mode WITH Arcade (OpenAI + Arcade + Slack):**

Same flow, but Arcade adds remote MCP tools (Slack) alongside the local tools.

```
 User
  |
  | "Get me side effects of paracetamol"
  v
+------------------+
|  Browser (UI)    |
+------------------+
  |  POST /query
  v
+------------------+       +------------------+
|  Flask app       |       |  OpenAI API      |
|  (main.py)       |       |  (GPT-4.1)       |
+------------------+       +------------------+
  |                              ^    |
  v                              |    |
+-----------------------------+  |    |
|  LangChain ReAct loop       |--+    |
|                              |<-----+
+-----------------------------+
  |           |           |                |
  | local     | local     | local          | MCP tools
  | tools     | tools     | tool           | (via Arcade gateway)
  v           v           v                v
+----------+ +----------+ +------------+ +---------------------------+
| SQLite   | | SQLite   | | clinical_  | | Arcade MCP Gateway        |
| (read)   | | (write)  | | trials.py  | | api.arcade.dev/mcp/gw_... |
+----------+ +----------+ +------------+ +---------------------------+
                             |               |              |
                             v               v              v
                    +-----------------+ +---------+ +---------------+
                    | ClinicalTrials  | | Slack   | | Slack         |
                    | .gov API        | | Send    | | WhoAmI /      |
                    | /api/v2/studies | | Message | | GetUserInfo   |
                    +-----------------+ +---------+ +---------------+
                                          |
                                          v
                                     +-----------+
                                     | Slack     |
                                     | workspace |
                                     | #channel  |
                                     +-----------+
```

The key difference: with Arcade, GPT-4.1 has access to additional Slack tools.
After storing new side effects, it adds a step:
- Call `Slack.SendMessage` with the new findings -> routed through Arcade gateway -> Slack API

Without Arcade, the flow is identical except that final Slack step doesn't exist.
The ClinicalTrials.gov data, DB storage, and natural language summary are the same either way.

### Direct search vs agent query: what's different?

Both use the same data source (ClinicalTrials.gov API) and the same database (SQLite).

| | Direct Search | Agent Query |
|---|---|---|
| Input | Drug name only | Natural language |
| Processing | Hardcoded Python logic | GPT-4.1 decides the steps |
| Output | Raw list of all side effects >1% | Natural language summary |
| Speed | 2-5 seconds | 10-20 seconds |
| Cost | Free | OpenAI tokens (~$0.01-0.05 per query) |
| DB updates | Stores everything automatically | Agent decides what's new and stores it |
| Intelligence | None — dumps all results | Can compare, filter, reason about results |

---

## Database

SQLite stored at `agent_app/instance/drugs.db` (auto-created on first run).

**Tables:**
- `drug` — `id` (int, PK), `drug_name` (string, not null)
- `side_effect_report` — `id` (int, PK), `side_effect_name` (string), `side_effect_probability` (float), `drug_id` (FK to drug)

**To reset:** `rm instance/drugs.db` and restart the app.

---

## Troubleshooting

**"Starting in mode: Direct API only" but I set my OpenAI key**
Make sure `.env` has `OPENAI_API_KEY=sk-proj-...` with no spaces around `=`. Also run `pip install ".[agent]"`.

**"Agent mode: disabled (missing packages: ...)"**
Run `pip install ".[agent]"`.

**"Network error: Failed to fetch" on search**
Flask may have been restarting (debug auto-reload). Try again. If it persists, check the terminal for a Python traceback.

**ClinicalTrials.gov returns no results**
Try common drug names: `paracetamol`, `aspirin`, `ibuprofen`, `metformin`, `finasteride`.

**Agent response disappears**
It shouldn't — the auto-reload was removed. If you still see it disappear, hard-refresh with Ctrl+Shift+R to clear cached HTML.
