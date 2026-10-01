import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from state import Store, validate_ticket


class Tests(unittest.TestCase):
    def test_idempotent_write(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d) / 'test.sqlite')
            args = dict(customer_ref='Test', issue='Mikrofon funktioniert nicht', priority='normal')
            first = store.create_ticket('same-operation', args)
            self.assertEqual(first, store.create_ticket('same-operation', args))
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0], 1)

    def test_reject_untrusted_confirmation(self):
        with self.assertRaises(ValueError):
            validate_ticket(dict(customer_ref='Test', issue='Mikrofon funktioniert nicht', priority='normal', confirmed=True))

    def test_reject_invalid_payloads(self):
        for args in [None, {}, dict(customer_ref='x', issue='short', priority='normal'), dict(customer_ref='x', issue='Valid issue text', priority='urgent')]:
            with self.assertRaises(ValueError):
                validate_ticket(args)

if __name__ == '__main__':
    unittest.main()
