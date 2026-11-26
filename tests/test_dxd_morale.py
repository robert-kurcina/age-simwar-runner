import unittest
from age_runtime.core import dxd_morale as m, dxd_conditions as c, dxd

class MoraleTests(unittest.TestCase):
    def test_failure_misses_and_fear_cap(self):
        state = m.initial()
        concerns = c.initial(dict.fromkeys(dxd.ATTRIBUTES, 7))
        m.apply(state, concerns, kind="fear", trigger="brutality",
                result={"passed":False,"margin":-8,"dof":1}, event="a", turn=1)
        self.assertEqual(concerns["stress"], 8)
        self.assertEqual(concerns["weariness"], 1)
        self.assertEqual(state["fear"], 1)
        m.calm(state, safe=True)
        self.assertEqual(state["fear"], 0)
        self.assertEqual(concerns["stress"], 8)
        with self.assertRaises(ValueError):
            m.apply(state, concerns, kind="fear", trigger="brutality",
                    result={"passed":False,"margin":-8,"dof":1}, event="a", turn=2)

    def test_shock_and_bravery_distinct(self):
        state = m.initial()
        concerns = c.initial(dict.fromkeys(dxd.ATTRIBUTES, 7))
        r = m.apply(state, concerns, kind="shock", trigger="amazement",
                    result={"passed":False,"margin":-6,"dof":1}, event="a", turn=1)
        self.assertEqual(r["hesitation_combat_turns"], 2)
        self.assertEqual(state["fear"], 0)
        m.apply(state, concerns, kind="bravery", trigger="risk",
                result={"passed":False,"margin":-1,"dof":0}, event="b", turn=2)
        self.assertEqual(state["fear"], 1)
        self.assertEqual(m.specification("shock","amazement")["fixed_dm"], -3)
        self.assertEqual(state["revelations"], [])
