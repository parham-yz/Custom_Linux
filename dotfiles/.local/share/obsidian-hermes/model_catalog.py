"""Runs inside the existing Hermes container; only model IDs leave the process."""
import json
import logging
from pathlib import Path

import yaml

logging.disable(logging.CRITICAL)
config = yaml.safe_load(Path('/opt/data/config.yaml').read_text())
provider = config.get('model', {}).get('provider', '')
live = False
models = []
if provider == 'openai-codex':
    from hermes_cli.auth import resolve_codex_runtime_credentials
    from hermes_cli.codex_models import _fetch_models_from_api, get_codex_model_ids
    try:
        credentials = resolve_codex_runtime_credentials(refresh_if_expiring=True)
        models = _fetch_models_from_api(credentials.get('api_key', ''))
        live = bool(models)
    except Exception:
        pass
    if not models:
        models = get_codex_model_ids()
else:
    # The installed provider owns discovery; adding accounts remains a separate setup step.
    from hermes_cli.models import provider_model_ids
    models = provider_model_ids(provider, force_refresh=True)
print(json.dumps({'provider': provider, 'models': models, 'live': live}))
