"""Lifecycle tests with an external CDP boundary double."""

import unittest
from unittest.mock import patch

from tools.facebook_agent.browser import Browser
from tools.facebook_agent.models import AgentError


class Page:
    def __init__(self):
        self.closed = False
        self.timeout = None
        self.front = False

    def close(self):
        self.closed = True

    def set_default_timeout(self, timeout):
        self.timeout = timeout

    def bring_to_front(self):
        self.front = True


class Session:
    def __init__(self):
        self.existing = Page()
        self.created = Page()
        self.stopped = False
        self.chromium = self
        self.contexts = [self]

    def start(self):
        return self

    def stop(self):
        self.stopped = True

    def connect_over_cdp(self, endpoint, timeout):
        if endpoint != 'http://127.0.0.1:9222':
            raise RuntimeError('Unavailable')
        return self

    def new_page(self):
        return self.created


class BrowserTests(unittest.TestCase):
    def test_doctor_closes_only_created_tab(self):
        session = Session()
        with patch('tools.facebook_agent.browser.sync_playwright', return_value=session):
            with Browser(timeout_ms=500) as browser:
                self.assertIs(browser.page, session.created)
                self.assertTrue(session.created.front)
                self.assertEqual(session.created.timeout, 500)
        self.assertTrue(session.created.closed)
        self.assertFalse(session.existing.closed)
        self.assertTrue(session.stopped)

    def test_post_preserves_created_and_existing_tabs(self):
        session = Session()
        with patch('tools.facebook_agent.browser.sync_playwright', return_value=session):
            with Browser() as browser:
                browser.keep_page = True
        self.assertFalse(session.created.closed)
        self.assertFalse(session.existing.closed)
        self.assertTrue(session.stopped)

    def test_failed_connection_disconnects_client(self):
        session = Session()
        with patch('tools.facebook_agent.browser.sync_playwright', return_value=session):
            with self.assertRaises(AgentError) as error:
                with Browser(endpoint='http://127.0.0.1:1'):
                    self.fail('Connection should fail')
        self.assertEqual(error.exception.code, 'browser_connection_failed')
        self.assertTrue(session.stopped)

    def test_empty_contexts_rejected(self):
        session = Session()
        session.contexts = []
        with patch('tools.facebook_agent.browser.sync_playwright', return_value=session):
            with self.assertRaises(AgentError):
                with Browser():
                    self.fail('No contexts should fail')
        self.assertTrue(session.stopped)
