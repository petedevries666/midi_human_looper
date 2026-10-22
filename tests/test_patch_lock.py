#!/usr/bin/env python3
"""Exercise patch-library flock behavior across real POSIX processes."""
import multiprocessing
import os
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from patch_lock import library_lock


def hold_lock(directory,entered,release):
    with library_lock(directory):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('parent did not release lock')


def wait_for_lock(directory,started,acquired):
    started.set()
    with library_lock(directory,wait=True):
        acquired.set()


class PatchLockProcessTests(unittest.TestCase):
    @unittest.skipIf(os.name=='nt','POSIX flock is not used on Windows')
    def test_nonblocking_conflict_and_waiting_process(self):
        ctx=multiprocessing.get_context('fork')
        with tempfile.TemporaryDirectory(prefix='mbmf-patch-lock-') as tmp:
            entered=ctx.Event();release=ctx.Event()
            holder=ctx.Process(target=hold_lock,args=(tmp,entered,release))
            waiter_started=ctx.Event();acquired=ctx.Event()
            waiter=ctx.Process(target=wait_for_lock,args=(tmp,waiter_started,acquired))
            holder.start()
            try:
                self.assertTrue(entered.wait(3),'holder never acquired patch lock')
                with self.assertRaisesRegex(ValueError,'already in progress'):
                    with library_lock(tmp):
                        self.fail('nonblocking lock must reject another process')
                waiter.start()
                self.assertTrue(waiter_started.wait(3),'waiter did not start')
                self.assertFalse(acquired.wait(.2),'wait=True entered before owner released')
                release.set()
                self.assertTrue(acquired.wait(3),'waiter did not acquire after release')
            finally:
                release.set()
                if waiter.pid is not None:
                    waiter.join(3)
                    if waiter.is_alive():waiter.terminate();waiter.join(2)
                holder.join(3)
                if holder.is_alive():holder.terminate();holder.join(2)
            self.assertEqual(holder.exitcode,0)
            self.assertEqual(waiter.exitcode,0)
            self.assertTrue((pathlib.Path(tmp)/'.patch-operation.lock').is_file())


if __name__=='__main__':
    unittest.main(verbosity=2)