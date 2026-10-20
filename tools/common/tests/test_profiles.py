"""Unit tests for tools.common.profiles."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.common.config import write_recorded_port
from tools.common.errors import AgentError
from tools.common.profiles import (
    load_registry,
    normalize_identity,
    profile_name,
    record_profile,
    registry_path,
    validate_registry,
)


class ProfilesTests(unittest.TestCase):
    def test_registry_path_defaults_next_to_package(self):
        self.assertEqual(registry_path().name, 'profiles.json')
        self.assertEqual(registry_path().parent.name, 'local')
        self.assertEqual(registry_path('/tmp/other').name, 'profiles.json')

    def test_load_registry_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as base_dir:
            self.assertEqual(load_registry(base_dir), {'profiles': {}})

    def test_load_registry_ignores_corrupt_or_misshapen_content(self):
        with tempfile.TemporaryDirectory() as base_dir:
            target = Path(base_dir) / 'profiles.json'
            target.write_text('not json', encoding='utf-8')
            self.assertEqual(load_registry(base_dir), {'profiles': {}})
            target.write_text(json.dumps({'profiles': ['wrong type']}), encoding='utf-8')
            self.assertEqual(load_registry(base_dir), {'profiles': {}})

    def test_profile_name_is_directory_basename(self):
        self.assertEqual(profile_name('/tmp/chrome-page-a'), 'chrome-page-a')

    def test_record_profile_writes_entry_and_port_file_is_used(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            profile_dir = Path(root) / 'chrome-page-a'
            write_recorded_port(profile_dir, 54123)

            registry = record_profile(profile_dir, backend='cdp', base_dir=base_dir)

            entry = registry['profiles']['chrome-page-a']
            self.assertEqual(entry['data_dir'], str(profile_dir.resolve()))
            self.assertEqual(entry['backend'], 'cdp')
            self.assertEqual(entry['port'], 54123)
            self.assertTrue(entry['last_used'].endswith('Z'))
            # Persisted, not just returned
            self.assertEqual(load_registry(base_dir), registry)

    def test_record_profile_updates_existing_entry_without_dropping_fields(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            profile_dir = Path(root) / 'chrome-page-a'

            record_profile(profile_dir, port=5000, backend='cdp', base_dir=base_dir)
            registry = record_profile(profile_dir, port=6000, base_dir=base_dir)

            self.assertEqual(len(registry['profiles']), 1)
            entry = registry['profiles']['chrome-page-a']
            self.assertEqual(entry['port'], 6000)
            self.assertEqual(entry['backend'], 'cdp')

    def test_record_profile_falls_back_to_configured_backend(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict('os.environ', {'BROWSER_BACKEND': 'invisible'}):
                registry = record_profile(Path(root) / 'chrome-page-a',
                                          base_dir=Path(root) / 'registry')
            self.assertEqual(registry['profiles']['chrome-page-a']['backend'], 'invisible')

    def test_record_profile_defaults_to_configured_profile_and_keeps_profiles_apart(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            with patch.dict('os.environ', {'CHROME_USER_DATA_DIR': str(Path(root) / 'chrome-page-a')}):
                record_profile(base_dir=base_dir, port=5000, backend='cdp')
            record_profile(Path(root) / 'chrome-page-b', base_dir=base_dir, port=5001, backend='cdp')

            registry = load_registry(base_dir)
            self.assertEqual(sorted(registry['profiles']), ['chrome-page-a', 'chrome-page-b'])
            self.assertEqual(registry['profiles']['chrome-page-a']['port'], 5000)
            self.assertEqual(registry['profiles']['chrome-page-b']['port'], 5001)

    def test_normalize_identity_trims_and_accepts_platform_fields(self):
        self.assertEqual(
            normalize_identity('facebook', {'page_id': ' 61595289277974 '}),
            {'page_id': '61595289277974'},
        )
        self.assertEqual(normalize_identity('twitter', {'account': '@TheVinhNguyen4'}),
                         {'account': 'TheVinhNguyen4'})
        self.assertEqual(normalize_identity('linkedin', {'account': 'Vinh Nguyen'}),
                         {'account': 'Vinh Nguyen'})

    def test_normalize_identity_rejects_bad_values(self):
        for platform, values in (
            ('facebook', {'page_id': 'not-digits'}),
            ('facebook', {'page_id': '٦١٥٩'}),
            ('facebook', {'page_name': 'Ink'}),
            ('twitter', {'account': 'has space'}),
            ('twitter', {'account': '@'}),
            ('linkedin', {'page_id': '123'}),
            ('mastodon', {'account': 'x'}),
        ):
            with self.subTest(platform=platform, values=values):
                with self.assertRaises(AgentError) as ctx:
                    normalize_identity(platform, values)
                self.assertEqual(ctx.exception.code, 'invalid_identity')

    def test_record_profile_links_identities_without_clearing_others(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            profile_dir = Path(root) / 'chrome-twitter-profile'

            record_profile(profile_dir, base_dir=base_dir,
                           identities={'facebook': {'page_id': '61595289277974'}})
            registry = record_profile(profile_dir, base_dir=base_dir,
                                      identities={'twitter': {'account': 'TheVinhNguyen4'}})

            identities = registry['profiles']['chrome-twitter-profile']['identities']
            self.assertEqual(identities['facebook'], {'page_id': '61595289277974'})
            self.assertEqual(identities['twitter'], {'account': 'TheVinhNguyen4'})
            self.assertEqual(load_registry(base_dir), registry)

    def test_record_profile_updates_one_identity_field_in_place(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            profile_dir = Path(root) / 'chrome-twitter-profile'

            record_profile(profile_dir, base_dir=base_dir, identities={
                'facebook': {'page_id': '111'},
                'twitter': {'account': 'TheVinhNguyen4'},
            })
            registry = record_profile(profile_dir, base_dir=base_dir, identities={
                'facebook': {'page_id': '61595289277974'},
            })

            identities = registry['profiles']['chrome-twitter-profile']['identities']
            self.assertEqual(identities['facebook'], {'page_id': '61595289277974'})
            self.assertEqual(identities['twitter'], {'account': 'TheVinhNguyen4'})

    def test_record_profile_keeps_identities_when_only_the_port_changes(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            profile_dir = Path(root) / 'chrome-twitter-profile'

            record_profile(profile_dir, base_dir=base_dir, port=5000,
                           identities={'facebook': {'page_id': '61595289277974'}})
            registry = record_profile(profile_dir, base_dir=base_dir, port=6000)

            entry = registry['profiles']['chrome-twitter-profile']
            self.assertEqual(entry['port'], 6000)
            self.assertEqual(entry['identities']['facebook']['page_id'], '61595289277974')

    def test_validate_registry_accepts_recorded_profiles(self):
        with tempfile.TemporaryDirectory() as root:
            base_dir = Path(root) / 'registry'
            record_profile(Path(root) / 'chrome-twitter-profile', base_dir=base_dir,
                           identities={'facebook': {'page_id': '61595289277974'}})
            validate_registry(load_registry(base_dir))

    def test_validate_registry_rejects_unknown_platform_or_bad_field(self):
        for registry in (
            {'profiles': {'p': {'identities': {'mastodon': {'account': 'x'}}}}},
            {'profiles': {'p': {'identities': {'facebook': {'page_id': 'abc'}}}}},
            {'profiles': {'p': {'identities': []}}},
            {'profiles': []},
        ):
            with self.subTest(registry=registry):
                with self.assertRaises(AgentError) as ctx:
                    validate_registry(registry)
                self.assertEqual(ctx.exception.code, 'invalid_registry')


if __name__ == '__main__':
    unittest.main()
