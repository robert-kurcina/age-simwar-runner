"""Portable, self-contained session handoff for trusted Chat/local referee use.

Integrity detects accidental changes, not hostile tampering. The included scenario
and session may contain private information: keep the bundle access-controlled.
"""
import argparse
import copy
import json
import re
from pathlib import Path
from play import verify_session
from runner import digest

FORMAT = 'age-simwar-chat-handoff'
VERSION = 1
SHA = re.compile(r'[0-9a-f]{40}')


def package(session, engine_revision):
    if not isinstance(engine_revision, str) or not SHA.fullmatch(engine_revision):
        raise ValueError('engine revision must be a pinned 40-character git commit SHA')
    verify_session(session)
    session = copy.deepcopy(session)
    payload = {'engine_revision': engine_revision, 'session': session,
               'session_digest': digest(session),
               'scenario_digest': digest(session['scenario'])}
    return {'format': FORMAT, 'version': VERSION, 'payload': payload,
            'payload_digest': digest(payload)}


def unpack(envelope, engine_revision):
    if not isinstance(envelope, dict) or set(envelope) != {'format', 'version', 'payload', 'payload_digest'}:
        raise ValueError('invalid handoff envelope')
    if envelope['format'] != FORMAT or type(envelope['version']) is not int or envelope['version'] != VERSION:
        raise ValueError('unsupported handoff format')
    payload = envelope['payload']
    if not isinstance(payload, dict) or set(payload) != {'engine_revision', 'session', 'session_digest', 'scenario_digest'}:
        raise ValueError('invalid handoff payload')
    if digest(payload) != envelope['payload_digest']:
        raise ValueError('handoff integrity mismatch')
    if not isinstance(engine_revision, str) or not SHA.fullmatch(engine_revision):
        raise ValueError('expected engine revision must be a pinned 40-character git commit SHA')
    if payload['engine_revision'] != engine_revision:
        raise ValueError('engine revision mismatch')
    session = payload['session']
    if digest(session) != payload['session_digest'] or digest(session['scenario']) != payload['scenario_digest']:
        raise ValueError('session or scenario digest mismatch')
    verify_session(session)
    return session


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, data):
    path = Path(path)
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'verify', 'restore'))
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', nargs='?', type=Path)
    parser.add_argument('--engine-revision', required=True,
                        help='40-character git SHA of the actual checked-out engine')
    args = parser.parse_args(argv)
    try:
        if args.command == 'export':
            if args.destination is None:
                raise ValueError('export requires a destination')
            envelope = package(read(args.source), args.engine_revision)
            write_new(args.destination, envelope)
            result = {'status': 'exported', 'digest': envelope['payload_digest']}
        else:
            session = unpack(read(args.source), args.engine_revision)
            if args.command == 'restore':
                if args.destination is None:
                    raise ValueError('restore requires a destination')
                if args.destination.exists():
                    raise ValueError('destination already exists; refuse overwrite')
                write_new(args.destination, session)
                result = {'status': 'restored', 'session_digest': digest(session)}
            else:
                if args.destination is not None:
                    raise ValueError('verify does not accept a destination')
                result = {'status': 'verified', 'session_digest': digest(session),
                          'scenario': session['scenario']['id'], 'turn': session['state']['turn']}
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
