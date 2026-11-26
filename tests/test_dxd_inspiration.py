import unittest
from fractions import Fraction
from itertools import product
from age_runtime.core import dxd_inspiration as i

class InspirationTests(unittest.TestCase):
    def test_probability_matches_enumeration(self):
        for base, bonus, penalty, favor in [(2,0,0,0),(2,1,0,0),(2,0,2,1),(3,0,1,0)]:
            count = base + favor
            net = bonus - penalty
            n = count + abs(net)
            successes = sum(sum(sorted(dice, reverse=net>0)[:count])+2 >= 10
                            for dice in product(range(1,7), repeat=n))
            self.assertEqual(i.probability(tn=10,dm=2,base=base,bonus=bonus,
                                           penalty=penalty,favor=favor), Fraction(successes,6**n))
        self.assertEqual(i.probability(narrative=True,adversity_dice=2,dm=3),
                         i.probability(tn=13,dm=3))

    def test_thresholds_cooldown_and_advantage(self):
        def check(p, consequence="meaningful", turn=4, last=1, extra=0):
            return i.eligible(p, turn=turn,last_turn=last,consequence=consequence,
                              maximum=1,extra_base=extra)
        self.assertTrue(check(Fraction(33,100)))
        self.assertFalse(check(Fraction(1,3)))
        self.assertTrue(check(Fraction(67,100),"irreversible"))
        self.assertFalse(check(Fraction(671,1000),"irreversible"))
        self.assertFalse(check(Fraction(1,2)))
        self.assertFalse(check(Fraction(0),"routine"))
        self.assertFalse(check(Fraction(0),turn=3))
        self.assertFalse(check(Fraction(0),extra=1))
        self.assertTrue(check(Fraction(0),turn=1,last=None))

    def test_persistent_modifier(self):
        entries = [{"tag":"investigation"}]*4 + [{"tag":"interview"}]
        self.assertEqual(i.applicable_dm(entries,["investigation"]),3)
        self.assertEqual(i.applicable_dm(entries,["interview"]),1)
        self.assertEqual(i.applicable_dm(entries,["physical"]),0)
