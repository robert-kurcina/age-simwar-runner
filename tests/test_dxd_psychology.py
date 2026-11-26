import unittest
from age_runtime.core import dxd, dxd_conditions as c, dxd_morale as m, dxd_psychology as p

class PsychologyTests(unittest.TestCase):
    def setUp(self):
        self.m = m.initial()
        self.c = c.initial(dict.fromkeys(dxd.ATTRIBUTES, 7))

    def acquire(self, revelation="fictional truth", understood=True, destabilized=True):
        p.acquire(self.m, self.c, revelation=revelation, understood=understood,
                  destabilized=destabilized, disability="Paranoid", turn=1)

    def test_explicit_acquisition_and_recovery(self):
        self.acquire()
        self.assertEqual(self.m["fear"], 4)
        self.assertEqual(self.m["psychology"], {"Paranoid":1})
        self.assertEqual(self.c["min_stress"], 1)
        self.acquire("another revelation")
        self.assertEqual(self.m["psychology"], {"Paranoid":2})
        self.assertEqual(self.c["min_stress"], 1)
        c.recover(self.c, 60, safe=True, restful=True)
        m.calm(self.m, safe=True)
        self.assertEqual(self.c["stress"], 1)
        self.assertEqual(self.m["fear"], 0)
        self.assertEqual(len(self.m["revelations"]), 2)
        self.assertEqual(p.effects(self.m, "first_friendliness"), {"dm":0,"penalty":2})
        self.assertEqual(p.effects(self.m, "trust_decision"), {"dm":-6,"penalty":0})
        self.assertEqual(p.effects(self.m, None), {"dm":0,"penalty":0})

    def test_no_ordinary_shock_acquisition_or_duplicate(self):
        with self.assertRaises(ValueError):
            self.acquire(understood=False)
        with self.assertRaises(ValueError):
            self.acquire(destabilized=False)
        self.assertEqual(self.m["revelations"], [])
        self.acquire()
        with self.assertRaises(ValueError):
            self.acquire()
