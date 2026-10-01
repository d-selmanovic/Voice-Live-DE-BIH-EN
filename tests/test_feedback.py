import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedback import FeedbackStore
from voices import selection


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ratings.sqlite'
        self.store = FeedbackStore(path=self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def rating(self, test, tester, score, voice='marin', language='bs', version='v1'):
        self.store.new_test(test, 'token-'+test, tester, voice, language, version)
        self.store.heard(test)
        body = {'test_id': test, 'test_token': 'token-'+test,
                'pronunciation': score, 'clarity': score, 'naturalness': score}
        self.store.rate(body)
        return body

    def test_latest_per_tester_and_shared_persistence(self):
        self.rating('a', 'person1', 1)
        self.rating('b', 'person1', 5)
        self.rating('c', 'person2', 3)
        reopened = FeedbackStore(path=self.path)
        result = reopened.stats('v1')
        self.assertEqual(result['testers'], 2)
        self.assertEqual(result['ratings'], 2)
        self.assertEqual(result['rows'][0]['pronunciation'], 4)
        self.assertEqual(result['rows'][0]['testers'], 2)

    def test_language_voice_and_version_do_not_mix(self):
        self.rating('a', 'person1', 5)
        self.rating('b', 'person1', 1, language='de')
        self.rating('c', 'person2', 2, voice='cedar')
        self.rating('d', 'person2', 1, version='v2')
        rows = {(r['voice'], r['language']): r for r in self.store.stats('v1')['rows']}
        self.assertEqual(rows['marin', 'bs']['pronunciation'], 5)
        self.assertEqual(rows['marin', 'de']['pronunciation'], 1)
        self.assertEqual(rows['cedar', 'bs']['pronunciation'], 2)
        self.assertEqual(set(self.store.versions()), {'v1', 'v2'})

    def test_reject_forged_unheard_and_invalid_scores(self):
        self.store.new_test('a', 'secret', 'person1', 'marin', 'bs', 'v1')
        body = {'test_id':'a','test_token':'secret','pronunciation':5,'clarity':4,'naturalness':3}
        with self.assertRaises(ValueError): self.store.rate(body)
        self.store.heard('a')
        with self.assertRaises(ValueError): self.store.rate(body | {'test_token':'forged'})
        for bad in [0, 6, True, '5', None]:
            with self.assertRaises(ValueError): self.store.rate(body | {'clarity':bad})
        self.store.rate(body | {'voice':'injected','language':'de'})
        row = self.store.stats('v1')['rows'][0]
        self.assertEqual((row['voice'],row['language']), ('marin','bs'))
        self.assertEqual(row['overall'], 4)

    def test_validate_voice_and_language(self):
        self.assertEqual(selection({'voice':'cedar','language':'bs','tester_code':' Tester-X '}), ('cedar','bs','tester-x'))
        for body in [[], {'voice':'bad'}, {'language':'hr'}, {'language':[]}, {'tester_code':'ab'}]:
            with self.assertRaises(ValueError): selection(body)


if __name__ == '__main__': unittest.main()
