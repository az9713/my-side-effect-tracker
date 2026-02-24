import asyncio
import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

from models import db, Drug, SideEffectReport
from clinical_trials import get_side_effects

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///drugs.db'

db.init_app(app)

with app.app_context():
    db.create_all()

# --- Agent mode (requires OPENAI_API_KEY + langchain packages) -------------

agent_executor = None

_openai_key = os.getenv('OPENAI_API_KEY', '')

if _openai_key:
    try:
        from langchain.agents import create_agent
        import agent as agent_module
        from agent import local_tools, get_mcp_tools

        agent_module.flask_app = app

        # Local tools always available; Arcade MCP tools added if keys are set
        mcp_tools = asyncio.run(get_mcp_tools())
        all_tools = local_tools + mcp_tools

        has_slack = any('slack' in t.name.lower() for t in mcp_tools)

        system_prompt = '''You are a helpful assistant for finding side effects of drugs.

The procedure should always be:
1. List all drugs in the database
2. If the drug already exists, list all side effects for that drug
3. Get new side effects using the get_side_effects_for_drug tool
4. If there is any new side effect that is not in the database, create a new side effect report for that drug in the DB
5. Summarise what you found and what was new'''

        if has_slack:
            system_prompt += '''
6. Send a Slack message to the channel #all-neuralnine with the new information exclusively'''

        agent_executor = create_agent('openai:gpt-4.1', all_tools, system_prompt=system_prompt)

        extras = ' + Arcade/Slack' if mcp_tools else ''
        print(f'Agent mode: enabled (OpenAI{extras})')
    except ImportError as e:
        print(f'Agent mode: disabled (missing packages: {e})')
        print('Install with: pip install ".[agent]"')


# --- Routes -----------------------------------------------------------------

@app.route('/')
def home():
    drugs = Drug.query.all()
    return render_template('index.html', drugs=drugs, agent_enabled=agent_executor is not None)


@app.route('/search', methods=['POST'])
def search():
    """Direct ClinicalTrials.gov search — no LLM, no API keys needed."""
    drug_name = request.json.get('drug_name', '').strip()
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400

    # Fetch side effects from the API
    side_effects = get_side_effects(drug_name)

    # Upsert drug
    drug = Drug.query.filter_by(drug_name=drug_name).first()
    if not drug:
        drug = Drug(drug_name=drug_name)
        db.session.add(drug)
        db.session.commit()

    # Store new side effects
    new_effects = []
    for se in side_effects:
        existing = SideEffectReport.query.filter_by(
            drug_id=drug.id, side_effect_name=se['side_effect_name']
        ).first()
        if not existing:
            report = SideEffectReport(
                side_effect_name=se['side_effect_name'],
                side_effect_probability=se['side_effect_probability'],
                drug_id=drug.id,
            )
            db.session.add(report)
            new_effects.append(se)

    db.session.commit()

    return jsonify({
        'drug': drug_name,
        'total_side_effects': len(side_effects),
        'new_side_effects': len(new_effects),
        'side_effects': side_effects,
    })


@app.route('/query', methods=['POST'])
def query():
    """LLM agent query — requires OPENAI_API_KEY."""
    if agent_executor is None:
        return jsonify({'error': 'Agent mode not available. Set OPENAI_API_KEY in .env and install: pip install ".[agent]"'}), 503

    user_query = request.json.get('query')
    result = asyncio.run(agent_executor.ainvoke({'messages': user_query}))
    response = result['messages'][-1].content

    return jsonify({'response': response})


if __name__ == '__main__':
    mode = 'Agent + Direct' if agent_executor else 'Direct API only'
    print(f'Starting in mode: {mode}')
    app.run(debug=True)
