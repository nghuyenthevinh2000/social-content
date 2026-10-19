"""Structured operational errors shared by social agent tools."""


class AgentError(Exception):
    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required
