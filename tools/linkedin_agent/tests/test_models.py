"""Local-only validation tests using synthetic images and temporary files."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.linkedin_agent.models import AgentError, ImageInput, validate_inputs


class ValidateInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.png = self.write_image('first.png', b'\x89PNG\r\n\x1a\nsynthetic')

    def write_image(self, name, buffer):
        path = self.root / name
        path.write_bytes(buffer)
        return str(path)

    def assert_invalid(self, text, paths, code):
        with self.assertRaises(AgentError) as caught:
            validate_inputs(text, paths)
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(caught.exception.human_action_required)
        self.assertTrue(caught.exception.message)
        return caught.exception

    def test_blank_text_is_rejected(self):
        self.assert_invalid(' \n', [], 'invalid_text')

    def test_oversized_text_is_rejected_without_echoing_it(self):
        text = 'sensitive-placeholder' * 151
        error = self.assert_invalid(text, [self.png], 'invalid_text')
        self.assertNotIn(text, str(error))

    def test_exact_text_limit_is_accepted(self):
        text, _ = validate_inputs('a' * 3000, [self.png])
        self.assertEqual(text, 'a' * 3000)

    def test_zero_images_are_rejected(self):
        self.assert_invalid('Approved text', [], 'invalid_images')

    def test_twenty_one_images_are_rejected(self):
        paths = [self.write_image(f'{i}.png', b'\x89PNG\r\n\x1a\n') for i in range(21)]
        self.assert_invalid('Approved text', paths, 'invalid_images')

    def test_twenty_images_are_accepted_in_order(self):
        paths = [self.write_image(f'{i}.png', b'\x89PNG\r\n\x1a\n') for i in range(20)]
        _, images = validate_inputs('Approved text', paths)
        self.assertEqual([image.name for image in images], [f'{i}.png' for i in range(20)])

    def test_missing_file_is_rejected(self):
        self.assert_invalid('Approved text', [str(self.root / 'missing.png')], 'invalid_images')

    def test_directory_is_rejected(self):
        self.assert_invalid('Approved text', [str(self.root)], 'invalid_images')

    def test_unreadable_file_is_rejected(self):
        # Permission bits do not reliably prevent reads for privileged users.
        with patch.object(Path, 'open', side_effect=PermissionError('private filesystem detail')):
            error = self.assert_invalid('Approved text', [self.png], 'invalid_images')
        self.assertNotIn('private filesystem detail', error.message)

    def test_duplicate_resolved_paths_are_rejected(self):
        alias = self.root / 'alias.png'
        alias.symlink_to(self.png)
        self.assert_invalid('Approved text', [self.png, str(alias)], 'invalid_images')

    def test_duplicate_dot_paths_are_rejected(self):
        alias = f'{self.root}/./first.png'
        self.assert_invalid('Approved text', [self.png, alias], 'invalid_images')

    def test_invalid_signatures_are_rejected_without_echoing_bytes(self):
        for buffer in (b'', b'\x89PNG', b'\xff\xd8', b'private-image-payload'):
            with self.subTest(buffer_length=len(buffer)):
                path = self.write_image('bad.png', buffer)
                error = self.assert_invalid('Approved text', [path], 'invalid_images')
                self.assertNotIn('private-image-payload', error.message)

    def test_oversized_image_is_rejected(self):
        path = self.write_image('large.png', b'\x89PNG\r\n\x1a\n' + b'x' * (10 * 1024 * 1024 - 7))
        self.assert_invalid('Approved text', [path], 'invalid_images')

    def test_exact_image_size_limit_is_accepted(self):
        buffer = b'\x89PNG\r\n\x1a\n' + b'x' * (10 * 1024 * 1024 - 8)
        path = self.write_image('limit.png', buffer)
        _, images = validate_inputs('Approved text', [path])
        self.assertEqual(images[0].buffer, buffer)

    def test_mime_classification_uses_signature_not_extension(self):
        jpeg = self.write_image('second.png', b'\xff\xd8\xffsynthetic')
        png = self.write_image('third.jpg', b'\x89PNG\r\n\x1a\nsynthetic')
        _, images = validate_inputs('Approved text', [jpeg, png])
        self.assertEqual([image.mime_type for image in images], ['image/jpeg', 'image/png'])

    def test_original_text_and_image_order_are_preserved(self):
        jpeg = self.write_image('second.jpeg', b'\xff\xd8\xffsynthetic')
        original = '  Approved\r\nmultiline\ntext  '
        text, images = validate_inputs(original, [jpeg, self.png])
        self.assertEqual(text, original)
        self.assertIsInstance(images, tuple)
        self.assertEqual(images, (
            ImageInput('second.jpeg', 'image/jpeg', b'\xff\xd8\xffsynthetic'),
            ImageInput('first.png', 'image/png', b'\x89PNG\r\n\x1a\nsynthetic'),
        ))

    def test_image_snapshot_survives_source_mutation_and_deletion(self):
        _, images = validate_inputs('Approved text', [self.png])
        Path(self.png).write_bytes(b'changed')
        Path(self.png).unlink()
        self.assertEqual(images[0].buffer, b'\x89PNG\r\n\x1a\nsynthetic')
        with self.assertRaises(FrozenInstanceError):
            images[0].buffer = b'changed'

    def test_image_read_is_bounded(self):
        # Wrap real disk I/O to observe its budget without replacing image data.
        real_open = Path.open
        budgets = []

        class RecordingReader:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def read(self, size=-1):
                budgets.append(size)
                return self.stream.read(size)

        def recording_open(path, *args, **kwargs):
            return RecordingReader(real_open(path, *args, **kwargs))

        with patch.object(Path, 'open', recording_open):
            _, images = validate_inputs('Approved text', [self.png])
        self.assertEqual(images[0].buffer, b'\x89PNG\r\n\x1a\nsynthetic')
        self.assertEqual(budgets, [10 * 1024 * 1024 + 1])

    def test_structured_error_supports_human_action_flag(self):
        error = AgentError('submission_uncertain', 'Inspect LinkedIn manually.', True)
        self.assertEqual(error.code, 'submission_uncertain')
        self.assertEqual(str(error), 'Inspect LinkedIn manually.')
        self.assertTrue(error.human_action_required)


if __name__ == '__main__':
    unittest.main()
