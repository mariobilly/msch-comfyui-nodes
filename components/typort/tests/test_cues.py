import unittest

import support
from mariotyport.project import default_project, validate_project


class CueTests(unittest.TestCase):
    def test_old_project(self):
        p = default_project()
        del p['text_cues'], p['cues_visible']
        result = validate_project(p)
        self.assertEqual(result['text_cues'], [])
        self.assertTrue(result['cues_visible'])

    def test_saved_cues(self):
        p = default_project()
        p['text_cues'] = [{'start': .5, 'end': 2}, {'start': 2, 'end': 4}]
        p['cues_visible'] = False
        self.assertEqual(validate_project(p), p)

    def test_invalid_cues(self):
        for cues in ([{'start': 2, 'end': 1}], [{'start': -1, 'end': 2}],
                     [{'start': 1, 'end': 6}], [{'start': float('nan'), 'end': 2}],
                     [{'start': 0, 'end': 2}, {'start': 1, 'end': 3}],
                     [{'start': 0, 'end': 1, 'text': 'unexpected'}]):
            with self.subTest(cues=cues):
                p = default_project()
                p['text_cues'] = cues
                with self.assertRaises(ValueError):
                    validate_project(p)
