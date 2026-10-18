"""Offline tests for the unified post format: validation and per-platform adapters."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.common.post import (
    LINKEDIN_MAX_TEXT,
    TWITTER_MAX_TEXT,
    PostError,
    load_post,
    parse_post,
)


def post(**overrides):
    """A minimal valid Facebook-only post, with overrides merged on top."""
    data = {'content': {'text': 'Shared caption.'}, 'platforms': {'facebook': {}}}
    data.update(overrides)
    return data


class LoadPostTests(unittest.TestCase):
    def test_load_from_file_resolves_media_relative_to_the_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'post.json'
            path.write_text(json.dumps(post(
                content={'text': 'Hi', 'images': ['assets/a.png']},
                platforms={'linkedin': {}})), encoding='utf-8')
            loaded = load_post(path)
            self.assertEqual(
                loaded.for_platform('linkedin').images,
                (str(Path(tmp).resolve() / 'assets' / 'a.png'),),
            )

    def test_missing_file_is_invalid_post(self):
        with self.assertRaises(PostError) as ctx:
            load_post('/nonexistent/post.json')
        self.assertEqual(ctx.exception.code, 'invalid_post')

    def test_malformed_json_is_invalid_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'post.json'
            path.write_text('{not json', encoding='utf-8')
            with self.assertRaises(PostError) as ctx:
                load_post(path)
            self.assertEqual(ctx.exception.code, 'invalid_post')


class ShapeTests(unittest.TestCase):
    def test_unknown_top_level_key(self):
        with self.assertRaises(PostError):
            parse_post(post(extra=1))

    def test_unknown_content_key(self):
        with self.assertRaises(PostError):
            parse_post({'content': {'text': 'x', 'link': 'y'}, 'platforms': {'facebook': {}}})

    def test_unknown_platform(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'mastodon': {}}))

    def test_unknown_platform_key(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'audience': 'public'}}))

    def test_content_text_required(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': '   '}))

    def test_platforms_required(self):
        with self.assertRaises(PostError):
            parse_post({'content': {'text': 'x'}, 'platforms': {}})

    def test_platform_not_object(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': 'yes'}))

    def test_enabled_must_be_bool(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'enabled': 'no'}}))

    def test_platform_not_enabled_lookup(self):
        loaded = parse_post(post(platforms={'facebook': {}}))
        with self.assertRaises(PostError) as ctx:
            loaded.for_platform('linkedin')
        self.assertEqual(ctx.exception.code, 'platform_not_enabled')

    def test_id_and_title_are_optional(self):
        loaded = parse_post(post())
        self.assertIsNone(loaded.id)
        self.assertIsNone(loaded.title)
        loaded = parse_post(post(id='p1', title='Launch'))
        self.assertEqual((loaded.id, loaded.title), ('p1', 'Launch'))


class ResolutionTests(unittest.TestCase):
    def test_platform_inherits_shared_content(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'images': ['a.png']},
            platforms={'facebook': {}}))
        plan = loaded.for_platform('facebook')
        self.assertEqual(plan.text, 'Shared')
        self.assertEqual(plan.images, ('a.png',))

    def test_platform_override_replaces_text_and_images(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'images': ['a.png']},
            platforms={'linkedin': {'text': 'Custom', 'images': ['b.png', 'c.png']}}))
        plan = loaded.for_platform('linkedin')
        self.assertEqual(plan.text, 'Custom')
        self.assertEqual(plan.images, ('b.png', 'c.png'))

    def test_present_empty_images_drops_inherited_media(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'images': ['a.png']},
            platforms={'facebook': {'images': []}}))
        self.assertEqual(loaded.for_platform('facebook').images, ())

    def test_present_null_video_drops_inherited_video(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'video': 'clip.mp4'},
            platforms={'facebook': {'video': None}}))
        self.assertEqual(loaded.for_platform('facebook').video, None)

    def test_absent_video_inherits(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'video': 'clip.mp4'},
            platforms={'facebook': {}}))
        self.assertEqual(loaded.for_platform('facebook').video, 'clip.mp4')

    def test_disabled_platform_excluded(self):
        loaded = parse_post(post(
            content={'text': 'Shared', 'images': ['a.png']},
            platforms={'facebook': {}, 'linkedin': {'enabled': False}}))
        self.assertEqual(loaded.platform_names, ('facebook',))

    def test_all_platforms_disabled_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'enabled': False}}))


class GroupTests(unittest.TestCase):
    def test_facebook_inherits_top_level_posting_groups(self):
        loaded = parse_post(post(posting_groups=['Alpha', 'Beta']))
        self.assertEqual(loaded.for_platform('facebook').posting_groups, ('Alpha', 'Beta'))
        self.assertEqual(loaded.posting_groups, ('Alpha', 'Beta'))

    def test_facebook_overrides_posting_groups(self):
        loaded = parse_post(post(posting_groups=['Alpha'], platforms={'facebook': {'posting_groups': ['Gamma']}}))
        self.assertEqual(loaded.for_platform('facebook').posting_groups, ('Gamma',))

    def test_duplicate_groups_rejected(self):
        with self.assertRaises(PostError) as ctx:
            parse_post(post(posting_groups=['Alpha', 'Alpha']))
        self.assertEqual(ctx.exception.code, 'invalid_groups')

    def test_group_limit_enforced(self):
        with self.assertRaises(PostError):
            parse_post(post(posting_groups=[f'G{i}' for i in range(10)]))

    def test_blank_group_name_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(posting_groups=['  ']))

    def test_posting_groups_not_allowed_on_linkedin(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'linkedin': {'posting_groups': ['Alpha']}}))


class FacebookTests(unittest.TestCase):
    def test_multiple_images_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png', 'b.png']},
                            platforms={'facebook': {}}))

    def test_image_and_video_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png'], 'video': 'v.mp4'},
                            platforms={'facebook': {}}))

    def test_page_profile_requires_identity(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'profile': 'page'}}))

    def test_page_profile_accepts_page_id(self):
        loaded = parse_post(post(platforms={'facebook': {'profile': 'page', 'page_id': '123'}}))
        plan = loaded.for_platform('facebook')
        self.assertEqual((plan.profile, plan.page_id), ('page', '123'))

    def test_page_id_must_be_ascii_digits(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'profile': 'page', 'page_id': '12a'}}))

    def test_personal_profile_forbids_page_fields(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'page_name': 'My Shop'}}))

    def test_invalid_profile_value(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'facebook': {'profile': 'group'}}))


class LinkedInTests(unittest.TestCase):
    def test_images_required(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'linkedin': {}}))

    def test_text_limit(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x' * (LINKEDIN_MAX_TEXT + 1), 'images': ['a.png']},
                            platforms={'linkedin': {}}))

    def test_video_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png'], 'video': 'v.mp4'},
                            platforms={'linkedin': {}}))


class TwitterTests(unittest.TestCase):
    def test_requires_exactly_one_image(self):
        with self.assertRaises(PostError):
            parse_post(post(platforms={'twitter': {'account': 'handle'}}))
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png', 'b.png']},
                            platforms={'twitter': {'account': 'handle'}}))

    def test_text_limit(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x' * (TWITTER_MAX_TEXT + 1), 'images': ['a.png']},
                            platforms={'twitter': {'account': 'handle'}}))

    def test_account_required(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png']}, platforms={'twitter': {}}))

    def test_account_normalized(self):
        loaded = parse_post(post(content={'text': 'x', 'images': ['a.png']},
                                 platforms={'twitter': {'account': '@Handle_1'}}))
        self.assertEqual(loaded.for_platform('twitter').account, 'Handle_1')

    def test_invalid_account_rejected(self):
        with self.assertRaises(PostError):
            parse_post(post(content={'text': 'x', 'images': ['a.png']},
                            platforms={'twitter': {'account': 'bad handle'}}))

    def test_approved_defaults_false(self):
        loaded = parse_post(post(content={'text': 'x', 'images': ['a.png']},
                                 platforms={'twitter': {'account': 'handle'}}))
        self.assertFalse(loaded.for_platform('twitter').approved)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.loaded = parse_post({
            'content': {'text': 'Shared', 'images': ['a.png']},
            'posting_groups': ['Alpha'],
            'platforms': {
                'facebook': {'profile': 'page', 'page_id': '42'},
                'linkedin': {},
                'twitter': {'account': 'handle', 'approved': True},
            },
        })

    def test_facebook_arguments(self):
        self.assertEqual(self.loaded.for_platform('facebook').arguments(), {
            'text': 'Shared', 'image': 'a.png', 'video': None,
            'groups': ['Alpha'], 'page_name': None, 'page_id': '42',
        })

    def test_linkedin_arguments(self):
        self.assertEqual(self.loaded.for_platform('linkedin').arguments(), {
            'text': 'Shared', 'images': ['a.png'],
        })

    def test_twitter_arguments(self):
        self.assertEqual(self.loaded.for_platform('twitter').arguments(), {
            'text': 'Shared', 'image': 'a.png', 'account': 'handle', 'approved': True,
        })

    def test_facebook_command_includes_groups_and_page(self):
        argv = self.loaded.for_platform('facebook').command()
        self.assertEqual(argv[:6], ['uv', 'run', 'python', '-m', 'tools.facebook_agent', 'post'])
        self.assertIn('--page-id', argv)
        self.assertEqual(argv[argv.index('--group') + 1], 'Alpha')

    def test_linkedin_command_repeats_images(self):
        argv = self.loaded.for_platform('linkedin').command()
        self.assertEqual(argv.count('--image'), 1)

    def test_twitter_command_uses_publish_module_and_approval(self):
        argv = self.loaded.for_platform('twitter').command()
        self.assertIn('tools.twitter_agent.publish', argv)
        self.assertIn('--approved', argv)

    def test_twitter_command_omits_approval_when_not_approved(self):
        loaded = parse_post(post(content={'text': 'x', 'images': ['a.png']},
                                 platforms={'twitter': {'account': 'handle'}}))
        self.assertNotIn('--approved', loaded.for_platform('twitter').command())


if __name__ == '__main__':
    unittest.main()
