"""JSON CLI plumbing; command dispatch and exit policies stay with each agent."""

import argparse
import json
import sys

from .errors import AgentError


class JsonArgumentParser(argparse.ArgumentParser):
    error_message = None
    error_class = AgentError

    def error(self, message):
        raise self.error_class('invalid_arguments', self.error_message or message)


def error_result(code: str, message: str, human_action_required: bool = False) -> dict:
    return {'ok': False, 'error': {
        'code': code, 'message': message, 'human_action_required': human_action_required,
    }}


def emit_result(result, *, ensure_ascii: bool = True, indent: int | None = 2):
    sys.stdout.write(json.dumps(result, ensure_ascii=ensure_ascii, indent=indent) + '\n')
    sys.stdout.flush()


def emit_success(data, *, ok: bool = True, ensure_ascii: bool = True):
    emit_result({'ok': ok, 'data': data}, ensure_ascii=ensure_ascii)


def emit_error(code: str, message: str, human_action_required: bool = False,
               *, ensure_ascii: bool = True):
    emit_result(error_result(code, message, human_action_required), ensure_ascii=ensure_ascii)
