import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_tools import analyze_beats, detect_focus
from engine import PromoRenderer, Settings
from planning import MOTION_NAMES, PRESETS, SCENE_NAMES, beat_boundaries, build_plan, validate_focus, validate_plan


def click_track(duration=12, rate=22050):
    signal = np.zeros(round(duration * rate), dtype=np.float32)
    t = np.arange(round(rate * 0.065)) / rate
    pulse = (np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 70)).astype(np.float32)
    markers = np.arange(0.25, duration - 0.1, 0.5)
    for time in markers:
        begin = round(time * rate)
        signal[begin:begin + len(pulse)] += pulse[:len(signal) - begin]
    return signal, markers


class PlanningTests(unittest.TestCase):
    def test_long_presets_are_distinct_seeded_and_not_short_loops(self):
        signatures = []
        for preset in PRESETS:
            plan = build_plan(30, preset=preset, seed=19)
            self.assertEqual(plan, build_plan(30, preset=preset, seed=19))
            self.assertNotEqual(plan, build_plan(30, preset=preset, seed=20))
            shots = plan["shots"]
            signature = [(s["scene"], s["motion"], s["variant"]) for s in shots]
            signatures.append(signature)
            for period in range(1, 9):
                self.assertFalse(all(signature[i] == signature[i % period] for i in range(30)))
            self.assertGreaterEqual(len({s["motion"] for s in shots}), 3)
            self.assertGreaterEqual(len({s["duration"] for s in shots}), 3)
            self.assertEqual(shots[0]["scene"], "hero")
            self.assertEqual(shots[-1]["scene"], "hero")
            validate_plan(plan, 30)
        self.assertEqual(len({str(s) for s in signatures}), 4)

    def test_new_pacing_stays_on_detected_beats_and_even_is_even(self):
        beats = {"version": 1, "times": [0.2 + i * 0.5 for i in range(300)]}
        for preset in PRESETS:
            plan = build_plan(20, preset=preset, beats=beats)
            boundaries = np.cumsum([shot["duration"] for shot in plan["shots"]])
            for boundary in boundaries:
                self.assertLess(min(abs(boundary - time) for time in beats["times"]), 1e-5)
            even = build_plan(20, preset=preset, timing="Seconds", seconds_per_image=1.2, pacing="Even")
            self.assertEqual({s["duration"] for s in even["shots"]}, {1.2})

    def test_legacy_plans_and_new_metadata_validation(self):
        plan = build_plan(2)
        for shot in plan["shots"]:
            for key in ("motion", "strength", "variant"):
                del shot[key]
        self.assertEqual(validate_plan(plan, 2), plan)
        for update in ({"motion": "invalid"}, {"strength": float("nan")}, {"variant": 8}, {"variant": True}):
            edited = copy.deepcopy(plan)
            edited["shots"][0].update(update)
            with self.assertRaises(ValueError):
                validate_plan(edited, 2)

    def test_all_compositions_render_across_aspects(self):
        images = [Image.new("RGB", (941, 1672), (60, 190, 90))] * 3
        for width, height in ((192, 108), (108, 192), (64, 64)):
            for scene in SCENE_NAMES:
                for variant in (0, 7):
                    plan = build_plan(3, timing="Seconds", pacing="Even", seconds_per_image=0.4)
                    for shot in plan["shots"]:
                        shot.update(scene=scene, variant=variant)
                    renderer = PromoRenderer(images, Settings(width=width, height=height, motion_blur=1,
                        grain=0, graphics=False), plan=plan)
                    for frame in (0, 13, renderer.frame_count - 1):
                        result = np.asarray(renderer.frame(frame))
                        self.assertEqual(result.shape, (height, width, 3))
                        self.assertGreater(result.mean(), 10)
                    renderer.clear_cache()

    def test_camera_paths_have_no_unfilled_edges(self):
        image = Image.new("RGB", (192, 108), (60, 190, 90))
        renderer = PromoRenderer([image], Settings(width=192, height=108, framing="Fill", intensity=1))
        for motion in MOTION_NAMES:
            for phase in np.linspace(0, 1, 17):
                moved = renderer._moving_photo(0, 192, 108, phase, shot={"motion": motion, "strength": 1})
                self.assertEqual(moved.getextrema(), ((60, 60), (190, 190), (90, 90)))

    def test_real_markers_preserve_offset_and_dynamic_pacing(self):
        beats = {"version": 1, "times": [0.2 + i * 0.5 for i in range(40)]}
        bounds = beat_boundaries(4, beats, 4, "Dynamic")
        np.testing.assert_allclose(bounds, [0, 1.7, 2.7, 4.7, 5.7])
        with self.assertRaises(ValueError):
            beat_boundaries(30, beats, 4, "Even")
        with self.assertRaises(ValueError):
            beat_boundaries(4, beats, 2.5, "Even")

    def test_shuffle_keeps_headlines_attached(self):
        plan = build_plan(4, headlines="A\nB\nC\nD", shuffle=True, seed=7)
        self.assertEqual(sorted(s["image_index"] for s in plan["shots"]), [0, 1, 2, 3])
        for shot in plan["shots"]:
            self.assertEqual(shot["headline"], "ABCD"[shot["image_index"]])
        self.assertEqual(plan, build_plan(4, headlines="A\nB\nC\nD", shuffle=True, seed=7))

    def test_edited_plan_repeats_sources_and_controls_duration(self):
        plan = build_plan(2, timing="Seconds", seconds_per_image=0.5, pacing="Even")
        plan["shots"][0].update(scene="stack", transition="cut", image_index=1)
        plan["shots"].append(copy.deepcopy(plan["shots"][0]))
        plan = validate_plan(json.loads(json.dumps(plan)), 2)
        renderer = PromoRenderer([Image.new("RGB", (320, 180), "red"), Image.new("RGB", (180, 320), "blue")],
            Settings(width=192, height=108, fps=24, motion_blur=1, grain=0), plan=plan)
        self.assertEqual(renderer.frame_count, 36)
        self.assertEqual(renderer.shot_count, 3)
        self.assertEqual(renderer.frame(35).size, (192, 108))

    def test_rejects_invalid_edit_before_render(self):
        for update in ({"duration": float("nan")}, {"duration": -1}, {"image_index": 9}, {"scene": "missing"}):
            plan = build_plan(2)
            plan["shots"][0].update(update)
            with self.assertRaises(ValueError):
                validate_plan(plan, 2)

    def test_motion_blur_does_not_dissolve_a_hard_cut(self):
        plan = build_plan(2, preset="Hard-cut promo", timing="Seconds", seconds_per_image=0.5, pacing="Even")
        for shot in plan["shots"]:
            shot["scene"] = "hero"
        renderer = PromoRenderer([Image.new("RGB", (192, 108), "red"), Image.new("RGB", (192, 108), "blue")],
            Settings(width=192, height=108, fps=24, motion_blur=5, grain=0, graphics=False), plan=plan)
        pixel = np.asarray(renderer.frame(12))[54, 96]
        self.assertEqual(tuple(pixel), (0, 0, 255))


class FocusTests(unittest.TestCase):
    def test_focused_crop_roundoff_stays_inside_source(self):
        for size, target in (((941, 1672), (426, 720)), ((1672, 941), (720, 426))):
            image = Image.new("RGB", size, (30, 180, 90))
            for framing in ("Fill", "Smart fit"):
                for item in ({"x": 0.5, "y": 0.5},
                             {"x": 0.45, "y": 0.45, "box": [0.3, 0.3, 0.6, 0.6]},
                             {"x": 1.0, "y": 1.0, "box": [0.8, 0.8, 1.0, 1.0]}):
                    with self.subTest(size=size, framing=framing, item=item):
                        renderer = PromoRenderer([image], Settings(framing=framing),
                            focus={"version": 1, "items": [item]})
                        crop = renderer._cover(0, *target)
                        self.assertEqual(crop.size, target)
                        self.assertEqual(crop.getextrema(), ((30, 30), (180, 180), (90, 90)))

    def test_mask_finds_off_center_subject(self):
        image = Image.new("RGB", (400, 160), (40, 40, 40))
        ImageDraw.Draw(image).rectangle((320, 45, 370, 115), fill=(20, 240, 20))
        mask = np.zeros((160, 400), np.float32)
        mask[45:116, 320:371] = 1
        item = detect_focus(image, mask=mask, margin=0.15)
        self.assertGreater(item["x"], 0.8)
        focus = {"version": 1, "items": [item]}
        settings = Settings(width=128, height=128, fps=24, framing="Fill", motion_blur=1, grain=0, graphics=False)
        plain = PromoRenderer([image], settings)
        guided = PromoRenderer([image], settings, focus=focus)
        baseline = np.asarray(plain.frame(0))
        self.assertLess(np.count_nonzero(baseline[:, :, 1] > 150), 10)
        for number in (0, 10, guided.frame_count - 1):
            frame = np.asarray(guided.frame(number))
            self.assertGreater(np.count_nonzero(frame[:, :, 1] > 150), 1800)

    def test_smart_fit_preserves_wide_subject_and_manual_focus(self):
        image = Image.new("RGB", (400, 160), "white")
        item = {"x": 0.5, "y": 0.5, "box": [0.05, 0.1, 0.95, 0.9]}
        r = PromoRenderer([image], Settings(width=128, height=128, motion_blur=1), focus={"version": 1, "items": [item]})
        self.assertEqual(r.frame(0).size, (128, 128))
        manual = detect_focus(image, "Manual", 0.8, 0.2)
        self.assertEqual((manual["x"], manual["y"]), (0.8, 0.2))
        with self.assertRaises(ValueError):
            validate_focus({"version": 1, "items": [manual]}, 2)


class BeatTests(unittest.TestCase):
    def test_click_track_has_expected_tempo_and_phase(self):
        signal, expected = click_track()
        beats, preview = analyze_beats(signal, 22050, tempo_hint=120)
        self.assertAlmostEqual(beats["bpm"], 120, delta=0.1)
        self.assertGreater(len(beats["times"]), 15)
        error = [min(abs(np.asarray(expected) - t)) for t in beats["times"]]
        self.assertLess(float(np.median(error)), 0.06)
        self.assertEqual(preview.size, (1200, 260))

    def test_silence_does_not_invent_beats(self):
        with self.assertRaisesRegex(ValueError, "silent"):
            analyze_beats(np.zeros(22050 * 3), 22050)


if __name__ == "__main__":
    unittest.main()
