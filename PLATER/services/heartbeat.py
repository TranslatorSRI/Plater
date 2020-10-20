"""Plater heartbeat."""
import argparse
import threading
import time

import httpx

from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

PLATER_TITLE = config.get("PLATER_TITLE", "Plater API")


def send_heart_beat(automat_host):
    """Send heartbeat."""
    heart_rate = config.get('heart_rate', 30)
    logger.debug(f'contacting {automat_host}')
    automat_heart_beat_url = f'{automat_host}/heartbeat'
    plater_address = config.get('PLATER_SERVICE_ADDRESS')
    if not plater_address:
        logger.error(
            'PLATER_SERVICE_ADDRESS environment variable not set. Please set '
            'this variable to the address of the host PLATER is running on.'
        )
        raise ValueError(
            'PLATER_SERVICE_ADDRESS cannot be None when joining automat '
            'cluster.'
        )
    payload = {
        'host': plater_address,
        'tag': PLATER_TITLE,
        'port': config.get('WEB_PORT', 8080)
    }
    while True:
        try:
            resp = httpx.post(
                automat_heart_beat_url,
                json=payload,
                timeout=0.5,
            )
            logger.debug(
                'heartbeat to %s returned %d',
                automat_host,
                resp.status_code,
            )
        except Exception as err:
            logger.error(f'[X] Error contacting automat server {err}')
        time.sleep(heart_rate)


def beat(automat_host):
    """Start beating."""
    logger.debug(f'Running in clustered mode about to join {automat_host}')

    # start heart beat thread.
    heart_beat_thread = threading.Thread(
        target=send_heart_beat,
        args=(automat_host),
        daemon=True
    )
    heart_beat_thread.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='PLATER, stand up a REST-api in front of neo4j database.'
    )
    parser.add_argument(
        '-a',
        '--automat_host',
        help=(
            'Needs to be a full http/https url. Eg. '
            'http://<automat_location>:<automat_port>. If you have an Automat '
            '(https://github.com/TranslatorIIPrototypes/KITCHEN/tree/master/KITCHEN/Automat) '
            'cluster and you\'d like this instance to be accessible via the '
            'Automat interface. Needs PLATER_SERVICE_ADDRESS env variable to '
            'the host name of where this instance is deployed.'
        ),
    )

    args = parser.parse_args()
    beat(args.automat_host)
