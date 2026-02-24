import os

from langchain.tools import tool

from models import db, Drug, SideEffectReport
from clinical_trials import get_side_effects as _get_side_effects

flask_app = None


# --- ClinicalTrials.gov tool (replaces Arcade MCP) -------------------------

@tool
def get_side_effects_for_drug(drug_name: str) -> list[dict]:
    """Get side effect reports from ClinicalTrials.gov for a given drug name.
    Returns a list of dicts with side_effect_name and side_effect_probability."""
    return _get_side_effects(drug_name)


# --- Local DB tools ---------------------------------------------------------

@tool
def list_drugs() -> list[str]:
    """List all drugs in the database"""
    with flask_app.app_context():
        return [drug.drug_name for drug in Drug.query.all()]


@tool
def create_drug(drug_name: str) -> str:
    """Create a new drug in the database. IMPORTANT: Always use list_drugs first to check if the drug already exists before creating."""
    with flask_app.app_context():
        existing = Drug.query.filter_by(drug_name=drug_name).first()
        if existing:
            return f"Drug '{drug_name}' already exists with ID {existing.id}"
        drug = Drug(drug_name=drug_name)
        db.session.add(drug)
        db.session.commit()
        return f"Drug '{drug_name}' created with ID {drug.id}"


@tool
def create_side_effect(drug_name: str, side_effect_name: str, probability: float) -> str:
    """Create a new side effect report for an existing drug. IMPORTANT: Always use list_side_effects first to check if this side effect already exists for this drug."""
    with flask_app.app_context():
        drug = Drug.query.filter_by(drug_name=drug_name).first()
        if not drug:
            return f"Drug '{drug_name}' not found"

        existing = SideEffectReport.query.filter_by(drug_id=drug.id, side_effect_name=side_effect_name).first()
        if existing:
            return f"Side effect '{side_effect_name}' already exists for '{drug_name}'"

        report = SideEffectReport(
            side_effect_name=side_effect_name,
            side_effect_probability=probability,
            drug_id=drug.id
        )

        db.session.add(report)
        db.session.commit()
        return f"Side effect '{side_effect_name}' added to '{drug_name}'"


@tool
def list_side_effects(drug_name: str) -> list[dict]:
    """List all side effects for a specific drug"""
    with flask_app.app_context():
        drug = Drug.query.filter_by(drug_name=drug_name).first()
        if not drug:
            return f"Drug '{drug_name}' not found"

        return [
            {
                "name": report.side_effect_name,
                "probability": report.side_effect_probability,
            }
            for report in drug.side_effect_reports
        ]


# --- Arcade MCP tools (optional, for Slack etc.) ---------------------------

async def get_mcp_tools():
    """Connect to the Arcade MCP gateway and return remote tools.

    Requires ARCADE_GATEWAY_URL, ARCADE_API_KEY, and ARCADE_USER_ID env vars.
    Returns [] if keys are missing or langchain-mcp-adapters is not installed.
    """
    gateway_url = os.getenv('ARCADE_GATEWAY_URL', '')
    api_key = os.getenv('ARCADE_API_KEY', '')
    user_id = os.getenv('ARCADE_USER_ID', '')

    if not all([gateway_url, api_key, user_id]):
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        return []

    client = MultiServerMCPClient(
        {
            'arcade': {
                'transport': 'http',
                'url': gateway_url,
                'headers': {
                    'Authorization': f'Bearer {api_key}',
                    'Arcade-User-ID': user_id,
                }
            }
        }
    )

    return await client.get_tools()


local_tools = [
    get_side_effects_for_drug,
    list_drugs,
    list_side_effects,
    create_drug,
    create_side_effect,
]
