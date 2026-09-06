import copy
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
import support
from mariotyport.audio_analysis import analyze, decode
from mariotyport.project import default_project, validate_project
from mariotyport.render import prepare_soundtrack


def make_clicks(path, duration=12):
    rate = 22050
    samples = np.zeros(round(duration * rate), dtype=np.float32)
    t = np.arange(round(.055 * rate)) / rate
    click = np.sin(t * 2 * np.pi * 1000) * np.exp(-t * 75)
    for at in np.arange(.25, duration - .1, .5):
        first = round(at * rate)
        samples[first:first + len(click)] += click[:len(samples) - first]
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate)
        audio.writeframes((samples * 24000).astype('<i2').tobytes())


class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / 'clicks.wav'
        make_clicks(cls.path)
        cls.analysis = analyze(cls.path, 'clicks.wav')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_tempo_waveform_sources(self):
        a = self.analysis
        self.assertLess(abs(a['bpm'] - 120), 3)
        self.assertGreater(len(a['beats']), 18)
        self.assertGreater(max(a['waveform']), .9)
        self.assertEqual(set(a['channels']), {'Mix', 'Low band', 'Mid band', 'High band'})
        self.assertGreater(len(a['channels']['Mix']['hits']), 18)

    def test_soundtrack_trim_delay_gain_and_muting(self):
        p = default_project(duration=3)
        p['audio'].update(file='clicks.wav', trim_start=.2, trim_end=1.7, start=.5, gain=.5, analysis=self.analysis)
        validate_project(p)
        target = Path(self.temp.name) / 'trimmed.wav'
        prepare_soundtrack(p['audio'], self.path, 3, target)
        result = decode(target, rate=48000, stereo=True)
        self.assertEqual(result.shape, (2, 144000))
        self.assertEqual(float(np.abs(result[:, :24000]).max()), 0)
        self.assertGreater(float(np.abs(result[:, 24000:96000]).max()), .1)
        self.assertEqual(float(np.abs(result[:, 96000:]).max()), 0)
        p['audio']['muted'] = True
        prepare_soundtrack(p['audio'], self.path, 3, target)
        self.assertEqual(float(np.abs(decode(target)).max()), 0)

    def test_reject_unavailable_source_and_stale_identity(self):
        p = default_project()
        p['audio'].update(file='clicks.wav', trim_end=5, analysis=copy.deepcopy(self.analysis))
        p['layers'][0].update(react_mode='Hits', react_source='Drums')
        with self.assertRaises(ValueError):validate_project(p)
        p['layers'][0]['react_source'] = 'Mix'
        validate_project(p)
        p['audio']['file'] = 'different.wav'
        with self.assertRaises(ValueError):validate_project(p)

    def test_legacy_project_is_normalized(self):
        p = default_project()
        del p['audio']
        for key in list(p['layers'][0]):
            if key.startswith('react_'):del p['layers'][0][key]
        result = validate_project(p)
        self.assertEqual(result['audio']['file'], '')
        self.assertEqual(result['layers'][0]['react_mode'], 'Off')

    def test_reject_bad_analysis(self):
        p = default_project()
        p['audio'].update(file='clicks.wav', trim_end=5, analysis=copy.deepcopy(self.analysis))
        p['audio']['analysis']['channels']['Mix']['levels'][0] = float('nan')
        with self.assertRaises(ValueError):validate_project(p)
