import unittest
from age_runtime.core import dxd_hitpoints as hp, dxd_injury
from age_runtime.mythos import mythos


class HitpointTests(unittest.TestCase):
    def pc(self):
        return {"hitpoints": hp.initial(12), "injury": dxd_injury.initial(12, 12, 4),
                "concerns": {"capacity": {"recovery_rate": 4}}}

    def test_loss_is_not_unconsciousness(self):
        pc = self.pc()
        hp.lose(pc["hitpoints"], 12)
        self.assertFalse(hp.incapacitated(pc))
        self.assertEqual(pc["injury"]["injury"], 0)
        self.assertEqual(hp.advance(pc, 9, restful=True), 0)
        self.assertEqual(hp.advance(pc, 1, restful=True), 4)
        self.assertEqual(hp.advance(pc, 20, restful=True), 8)

    def test_subdue_and_overflow(self):
        pc = self.pc()
        hp.subdue(pc, 17)
        self.assertTrue(hp.incapacitated(pc))
        self.assertEqual(pc["injury"]["injury"], 1)
        self.assertEqual(hp.advance(pc, 600, restful=True), 0)
        hp.recover(pc["hitpoints"], 6)
        self.assertTrue(hp.incapacitated(pc))

    def test_interruption(self):
        pc = self.pc()
        hp.lose(pc["hitpoints"], 8)
        hp.advance(pc, 9, restful=True)
        hp.advance(pc, 1, restful=False)
        self.assertEqual(hp.advance(pc, 1, restful=True), 0)

    def test_runtime_incapacity(self):
        state = mythos.initial("boothbay", 42)
        pc = state["dxd"]
        self.assertEqual(mythos.view(state)["condition"]["hitpoints"]["current"], pc["hitpoints"]["capacity"])
        hp.subdue(pc, pc["hitpoints"]["capacity"])
        with self.assertRaises(ValueError):
            mythos.step(state, "observe")
        after = mythos.step(state, "await_assistance")
        self.assertTrue(after["dxd"]["hitpoints"]["unconscious"])
        self.assertEqual(after["dxd"]["hitpoints"]["current"], 0)
