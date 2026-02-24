# Medical Side Effect Tracker

A web application that tracks serious side effects of medical drugs using data from ClinicalTrials.gov. Search for any drug and get aggregated adverse event probabilities from recent clinical trials, stored in a local database for tracking over time.

https://github.com/user-attachments/assets/d58e03ad-67dd-4fae-bed4-8c2e2578f721

> **Acknowledgement:** This is a modified version of the original repository [NeuralNine/youtube-tutorials/Side Effects Tracker](https://github.com/NeuralNine/youtube-tutorials/tree/main/Side%20Effects%20Tracker), inspired by the YouTube video ["Building A Medical Side Effect Tracker in Python"](https://www.youtube.com/watch?v=SA-YyejZ2Cs&t=4s). All credits go to the original developer and host of the video. See [docs/bugfixes.md](docs/bugfixes.md) for a full list of changes from the original.

---

## Features

- Search any drug by name and fetch serious side effects from ClinicalTrials.gov
- Aggregates adverse event probabilities across multiple clinical studies
- Stores results in a local SQLite database for tracking over time
- Optional AI agent mode (GPT-4.1) for natural language queries and summarisation
- Optional Arcade/Slack integration for notifications when new side effects are found

## Quick Start

**Requirements:** Python 3.12+

```bash
cd side-effect-tracker/agent_app
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install .
python main.py
```

Open http://127.0.0.1:5000 and search for a drug (e.g. paracetamol, aspirin, ibuprofen).

No API keys or accounts needed for basic usage.

## Agent Mode (optional)

Adds an AI-powered query box that uses GPT-4.1 to reason about drug side effects, compare against the database, and return natural language summaries.

```bash
pip install ".[agent]"
```

Set your OpenAI key in `.env`:

```
OPENAI_API_KEY=sk-proj-...
```

Then restart the app. See [docs/SETUP.md](docs/SETUP.md) for full setup instructions including optional Arcade/Slack integration.

## How It Works

The app queries the [ClinicalTrials.gov API](https://clinicaltrials.gov/api/v2) for studies related to a drug, extracts serious adverse events, and aggregates the probability of each side effect across all studies. Only side effects above 1% probability are shown.

```
Browser -> Flask -> clinical_trials.py -> ClinicalTrials.gov API
                         |
                         v
                   SQLite database -> displayed in UI
```

In agent mode, GPT-4.1 orchestrates the workflow via LangChain:

```
Browser -> Flask -> LangChain ReAct agent <-> GPT-4.1
                         |
                    +----+----+
                    |         |
               Local tools  ClinicalTrials.gov
            (SQLite CRUD)    (API queries)
```

## Documentation

- [docs/SETUP.md](docs/SETUP.md) — Setup guide, architecture, role of each technology
- [docs/bugfixes.md](docs/bugfixes.md) — All code changes from the original with explanations

## Project Structure

```
side-effect-tracker/
  agent_app/
    main.py              # Flask app, routes, agent init
    models.py            # Drug and SideEffectReport models
    clinical_trials.py   # Direct ClinicalTrials.gov API client
    agent.py             # LangChain tools + optional Arcade MCP
    templates/
      index.html         # Web UI
    .env                 # API keys (only OPENAI_API_KEY needed for agent mode)
    pyproject.toml       # Dependencies (base + optional agent/arcade)
  side_effects_mcp/      # Arcade MCP server (optional, for cloud deployment)
```

## License

This project is for educational purposes.
