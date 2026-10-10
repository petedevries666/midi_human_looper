"""Multiple browser observers share state requests; commands remain uncached."""
import sys,unittest
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
if __name__=='__main__':unittest.main()
