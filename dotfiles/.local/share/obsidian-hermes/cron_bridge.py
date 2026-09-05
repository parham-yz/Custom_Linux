"""Run inside the pinned Hermes container; uses Hermes's own job storage/locking."""
import json
from pathlib import Path
import sys
import uuid
from cron.jobs import create_job

body = json.load(sys.stdin)
text = body['text'].strip()
if not text or len(text) > 500:
    raise ValueError('Reminder must contain 1–500 characters')
name = 'desktop-reminder-' + uuid.uuid4().hex + '.py'
path = Path('/opt/data/scripts') / name
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text('print(' + repr(text) + ')\n')
path.chmod(0o600)
try:
    job = create_job(prompt=None, schedule=body['schedule'], name=text,
                     deliver='local', script=name, no_agent=True, repeat=1)
except Exception:
    path.unlink(missing_ok=True)
    raise
print(json.dumps({'job': job}))
