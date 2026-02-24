"""Direct ClinicalTrials.gov API client — no MCP or LLM required."""

import requests

BASE_URL = 'https://clinicaltrials.gov/api/v2'


def get_side_effects(drug_name: str, page_size: int = 25, threshold: float = 0.01) -> list[dict]:
    """Query ClinicalTrials.gov for serious adverse events for a given drug.

    Returns a list of dicts with keys: side_effect_name, side_effect_probability
    Only includes side effects with probability > threshold.
    """
    params = {
        'query.term': drug_name,
        'pageSize': page_size,
        'sort': 'ResultsFirstPostDate',
    }

    resp = requests.get(f'{BASE_URL}/studies', params=params, timeout=30)
    resp.raise_for_status()

    studies = resp.json().get('studies', [])
    aggregated: dict[str, list[float]] = {}

    for study in studies:
        if not study.get('hasResults'):
            continue

        results_section = study.get('resultsSection', {})
        adverse_module = results_section.get('adverseEventsModule', {})

        if 'seriousEvents' not in adverse_module:
            continue

        for event in adverse_module['seriousEvents']:
            stats = event.get('stats', [{}])
            if not stats or stats[0].get('numAtRisk', 0) == 0:
                continue

            name = event.get('term', 'Unknown')
            probability = stats[0]['numAffected'] / stats[0]['numAtRisk']

            if name in aggregated:
                aggregated[name].append(probability)
            else:
                aggregated[name] = [probability]

    results = [
        {
            'side_effect_name': name,
            'side_effect_probability': sum(probs) / len(probs),
        }
        for name, probs in aggregated.items()
    ]

    return [r for r in results if r['side_effect_probability'] > threshold]
