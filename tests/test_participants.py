import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from age_runtime.core.participants import compile_profile

def example():
    return {"version":1,"world":"synthetic","id":"library","kind":"organization",
            "effective_date":"2000-01-01","label":"Library","rules_namespace":"civic",
            "properties":{"resources.credits":{"unit":"credits","value":2,
                "classification":"hypothetical","reason":"Illustrative budget"},
                "motivations.service":{"unit":"text","value":"Keep rooms available",
                "classification":"hypothetical","reason":"Authored goal"},
                "conditions.trust":{"unit":"unspecified","value":None,
                "classification":"unresolved","reason":"No source"}}}

class ParticipantTests(unittest.TestCase):
    def test_determinism_and_no_mutation(self):
        spec = example()
        prior = copy.deepcopy(spec)
        a = compile_profile(spec,{})
        self.assertEqual(a, compile_profile(spec,{}))
        self.assertEqual(spec,prior)
        spec["properties"]["resources.credits"]["value"] = 3
        self.assertNotEqual(a["profile_digest"],compile_profile(spec,{})["profile_digest"])

    def test_reject_unverified_and_unknown(self):
        for classification,value in [("canonical",2),("unresolved",0),("hypothetical",None)]:
            spec = example()
            spec["properties"]["resources.credits"].update(classification=classification,value=value)
            with self.assertRaises(ValueError):
                compile_profile(spec,{})

    def test_dated_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                return subprocess.check_output(["git","-C",tmp,*args],stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            git("config","user.email","fixture@example.invalid")
            git("config","user.name","Fixture")
            Path(tmp,"source.json").write_text(json.dumps({"entities":{"library":{"fields":{"credits":{
                "value":4,"classification":"canonical","effective_date":"2000-01-01"}}}}}))
            git("add","source.json")
            git("commit","-m","synthetic source")
            ref={"owner":"fixture","revision":git("rev-parse","HEAD"),"path":"source.json",
                 "entity":"library","field":"credits","effective_date":"2000-01-01","classification":"canonical"}
            spec=example()
            spec["properties"]["resources.credits"]={"unit":"credits","reference":ref}
            result=compile_profile(spec,{"fixture":tmp})
            self.assertEqual(result["profile"]["properties"]["resources.credits"]["value"],4)
            spec["effective_date"]="2001-01-01"
            with self.assertRaises(ValueError):
                compile_profile(spec,{"fixture":tmp})
