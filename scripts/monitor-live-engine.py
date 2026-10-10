#!/usr/bin/env python3
"""Observe one running processor; never start JACK, modify routing or send commands."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from server import Control
from reliability_report import summarize,FIELDS

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--socket',required=True)
    p.add_argument('--seconds',type=int,default=60)
    args=p.parse_args()
    if not 1<=args.seconds<=3600:p.error('seconds must be 1..3600')
    control=Control(args.socket);samples=[]
    for i in range(args.seconds+1):
        state=control.request() # op=0: bounded control-worker query, no MIDI command
        samples.append({k:state.get(k) for k in FIELDS})
        if i<args.seconds:time.sleep(1)
    report=summarize(samples);print(json.dumps(report,indent=2))
    return int(bool(report['problems']))
if __name__=='__main__':sys.exit(main())
