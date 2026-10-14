"""Multiple browser observers share state requests; commands remain uncached."""
import sys,unittest,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from server import Control
class ObservationTests(unittest.TestCase):
    def test_observers_share_one_request_per_window(self):
        control=Control('/unused');state={'revision':1}
        with patch.object(control,'request',return_value=state) as request,patch('server.time.monotonic',return_value=1):
            with ThreadPoolExecutor(max_workers=16) as executor:
                values=list(executor.map(lambda _:control.observation(),range(64)))
            self.assertEqual(request.call_count,1)
            self.assertTrue(all(value==state for value in values))
            with patch('server.time.monotonic',return_value=1.26):
                control.observation();self.assertEqual(request.call_count,2)
    def test_even_failed_mutation_invalidates_observation(self):
        control=Control('/unused');control._observation={'revision':1}
        # A failed socket connection must not leave a stale successful-command
        # view; query-only direct API requests remain uncached too.
        with patch('server.socket.socket') as constructor:
            constructor.return_value.__enter__.return_value.connect.side_effect=OSError('offline')
            with self.assertRaises(OSError):control.request(op=2)
        self.assertIsNone(control._observation)

class PayloadTests(unittest.TestCase):
    def test_parallel_payloads_share_encoding_and_expiry_refreshes_same_object(self):
        control=Control('/unused');state={'revision':1,'engineSessionId':123,'activeNotes':0}
        real_dumps=json.dumps
        with patch.object(control,'request',return_value=state) as request,patch('server.time.monotonic',return_value=1),patch('server.json.dumps',wraps=real_dumps) as encode:
            with ThreadPoolExecutor(max_workers=16) as executor:
                payloads=list(executor.map(lambda _:control.observation_payload(),range(64)))
            self.assertEqual(request.call_count,1);self.assertEqual(encode.call_count,1)
            self.assertTrue(all(value is payloads[0] for value in payloads));self.assertEqual(json.loads(payloads[0]),state)
            with patch('server.time.monotonic',return_value=1.26):
                control.observation_payload();self.assertEqual(request.call_count,2);self.assertEqual(encode.call_count,2)
    def test_failed_mutation_invalidates_cached_bytes_too(self):
        control=Control('/unused');control._observation={'revision':1};control._observation_json=b'{"revision":1}'
        with patch('server.socket.socket') as constructor:
            constructor.return_value.__enter__.return_value.connect.side_effect=OSError('offline')
            with self.assertRaises(OSError):control.request(op=2)
        self.assertIsNone(control._observation);self.assertIsNone(control._observation_json)

if __name__=='__main__':unittest.main()
