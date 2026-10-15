#!/usr/bin/env python3
"""Private native observation; worker JSON only, not a real-time benchmark."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'headless')]
from test_headless_mvp import HeadlessTests
from server import Control

def measure(call,iterations=256):
    samples=[]
    for _ in range(9):
        start=time.process_time_ns()
        for _ in range(iterations):call()
        samples.append((time.process_time_ns()-start)/iterations/1000)
    tracemalloc.start()
    for _ in range(iterations):call()
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    return dict(cpuUsPerRead=samples,medianCpuUs=statistics.median(samples),transientTracemallocPeakBytes=peak)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    HeadlessTests.setUpClass();api=HeadlessTests('runTest')
    try:
        api.command('panic');control=Control(api.sock);state=control.observation()
        # Hold the same actual state for both paths. Expiry/freshness is tested
        # separately; never benchmark two different/advancing payloads.
        control._observation_until=float('inf')
        uncached=lambda:json.dumps(state,separators=(',',':')).encode()
        cached=control.observation_payload
        expected=uncached();assert cached()==expected
        before=measure(uncached);after=measure(cached)
        assert cached()==expected
        report=dict(scope='Python control worker JSON encoding/read CPU only; no JACK/ARM latency claim',
                    runtimeBuildRevision=state['buildRevision'],nativePayloadBytes=len(expected),iterations=256,samples=9,
                    before=before,after=after,cachedPayloadRetainedBytes=len(expected),
                    freshness='Same frozen observed state; expiry and command invalidation have separate regression tests',
                    measurement='CPU samples without tracing; separate transient allocation samples with warmed cache')
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:HeadlessTests.tearDownClass()
if __name__=='__main__':main()
