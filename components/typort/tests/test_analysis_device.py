import unittest
from unittest.mock import patch

import support
from mariotyport.audio_analysis import resolve_separation_device


class AnalysisDeviceTests(unittest.TestCase):
    def test_auto_gpu(self):
        with patch('torch.cuda.is_available', return_value=True):
            self.assertEqual(resolve_separation_device('auto'), 'cuda')
            self.assertEqual(resolve_separation_device('cuda'), 'cuda')

    def test_auto_cpu(self):
        with patch('torch.cuda.is_available', return_value=False):
            self.assertEqual(resolve_separation_device('auto'), 'cpu')
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                resolve_separation_device('cuda')

    def test_explicit_cpu(self):
        with patch('torch.cuda.is_available') as available:
            self.assertEqual(resolve_separation_device('cpu'), 'cpu')
            available.assert_not_called()

    def test_invalid(self):
        for device in ('cuda:99', '', None, [], {}):
            with self.subTest(device=device), self.assertRaises(ValueError):
                resolve_separation_device(device)
