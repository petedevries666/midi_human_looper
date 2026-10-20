import copy
import unittest
from headless.expressive_patch import defaults, validate, validate_patch

class ExpressivePatchTests(unittest.TestCase):
    def test_defaults(self):
        for kind in ("humanizer", "velocity_curves"):
            self.assertEqual(validate(defaults(kind)), defaults(kind))
        d = defaults("velocity_curves")
        d["points"][0][1] = 120
        self.assertEqual(defaults("velocity_curves")["points"][0][1], 1)

    def test_extreme_humanizer(self):
        h = defaults("humanizer")
        h.update(enabled=True, timingMs=2000, biasMs=-2000,
                 velocityPercent=100, scope="notes",
                 distribution="uniform", variation="evolving", seed=4294967295)
        self.assertEqual(validate(h)["timingMs"], 2000)
        for field, bad in (("timingMs", 2001), ("biasMs", -2001),
                           ("velocityPercent", 101), ("seed", -1),
                           ("distribution", "normal"), ("scope", "chords"),
                           ("enabled", 1)):
            copy_h = copy.deepcopy(h)
            copy_h[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(copy_h)
        h["timingMs"] = float("nan")
        with self.assertRaises(ValueError):
            validate(h)

    def test_velocity_curves(self):
        c = defaults("velocity_curves")
        c["points"] = [[1,127], [64,2], [127,1]]
        self.assertEqual(validate(c)["points"], c["points"])
        for points in ([[1,1],[1,3],[127,127]],
                       [[2,1],[127,127]], [[1,1],[126,127]],
                       [[1,1],[64,0],[127,127]],
                       [[1,1],[64.5,5],[127,127]]):
            bad = copy.deepcopy(c)
            bad["points"] = points
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate(bad)
        c["amount"] = float("inf")
        with self.assertRaises(ValueError):
            validate(c)

    def test_patch_and_no_unknown_keys(self):
        patch = {"expressiveVersion":1, "modules":[defaults("humanizer"),
                 defaults("velocity_curves")]}
        self.assertEqual(validate_patch(patch),patch)
        patch["modules"][0]["phantom"] = 1
        with self.assertRaises(ValueError):
            validate_patch(patch)
        patch["modules"][0].pop("phantom")
        patch["expressiveVersion"] = 2
        with self.assertRaises(ValueError):
            validate_patch(patch)

if __name__ == "__main__":
    unittest.main()
