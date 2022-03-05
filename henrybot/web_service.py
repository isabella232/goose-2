import sys
import logging
from pathlib import Path
from logging.config import fileConfig

REPO_ROOT = Path(__file__).resolve().parent.parent

fileConfig(f'{REPO_ROOT}/logging.cfg')

log = logging.getLogger(__name__)

def uncaught_exception_handler(exctype, value, tb):
   log.exception('Uncaught exception', extra={    # pragma: no cover
        'exctype': exctype,
        'value': value,
        'tb': tb
    })
sys.excepthook = uncaught_exception_handler


from quart import Quart, request
from .event_processors import Processor, ConfigEntry
import json
import os
import yaml
commit_info = None
if os.path.exists(f'{REPO_ROOT}/git-info.txt'):
    with open(f'{REPO_ROOT}/git-info.txt') as f: # pragma: no cover
        commit_info = ''.join(f.readlines())


with open(f'{REPO_ROOT}/service-config.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
processor_list = []
for entry in cfg:
    processor_list.append(
        ConfigEntry(
            entry['name'],
            entry['url'],
            [x for x in entry.get('filePatterns', '') if '*' not in x],
        )
    )

# TODO: per-environment config
process = Processor(processor_list)

GITHUB_EVENT_NAME_HEADER = 'X-GitHub-Event'
FOUND_WEBHOOK_HEADER = 'did-process'

app = Quart(__name__)

@app.route('/')
async def index():
    log.info("Index")
    return f"works: {commit_info}"

@app.route('/webhook', methods=['POST'])
async def webhook():
    log.info("webhook")
    # TODO: Emit metric on payload size. Github caps events at 25mb.
    event = request.headers.get(GITHUB_EVENT_NAME_HEADER)
    # TODO: hmac validation of incoming payload
    log.info(f"Incoming event: {event}")

    j = await (request.get_json())
    log.debug(f"JSON: {json.dumps(j, indent=2)}")

    p = getattr(process, 'process_{}'.format(event), None)
    log.debug(f'Has attr? {p}')
    processed = 'no'
    if p is not None:
        # TODO: This should likely be
        p((await request.get_json()))
        processed = 'yes'
    else:
        log.debug(f"Unable to find a handler for event: {event}")


    return {}, 200, {FOUND_WEBHOOK_HEADER: processed}

if __name__ == '__main__':
    app.run()
