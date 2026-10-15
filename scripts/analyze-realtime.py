#!/usr/bin/env python3
"""Analyze saved production JACK traces. Exit 2 means RT gate not qualified."""
import argparse,csv,gzip,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
def stat(v):
 v=sorted(v)
 return dict(count=len(v),p95Us=v[int((len(v)-1)*.95)]/1000,p99Us=v[int((len(v)-1)*.99)]/1000,maxUs=v[-1]/1000) if v else {}
results=[]
for directory in sorted(a.directory.glob('[0-9]*'),key=lambda p:int(p.name),reverse=True):
 with gzip.open(directory/'callback.csv.gz','rt') as f:
  lines=f.read().splitlines()
 rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(l for l in lines if not l.startswith('#'))]
 frames=int(directory.name);deadline=frames/48000*1e9
 result=dict(frames=frames,deadlineUs=deadline/1000,wall=stat([r['wall_ns'] for r in rows]),cpu=stat([r['cpu_ns'] for r in rows]),offCpu=stat([max(0,r['wall_ns']-r['cpu_ns']) for r in rows]),entryGap=stat([r['entry_gap_ns'] for r in rows]),wallOverruns=sum(r['wall_ns']>deadline for r in rows),cpuOverruns=sum(r['cpu_ns']>deadline for r in rows),xruns=max(r['xruns'] for r in rows),rejected=max(r['rejected'] for r in rows),overflow=max(r['overflow'] for r in rows),dropped=int(lines[-1].split('=')[1]),stages={k:stat([r[k] for r in rows]) for k in rows[0] if k.endswith('_cpu_ns') and k!='cpu_ns'})
 result['qualified']=not any(result[k] for k in ('wallOverruns','xruns','rejected','overflow','dropped'));results.append(result)
summary=dict(physicalHardware=False,qualified=all(r['qualified'] for r in results),buffers=results)
(a.directory/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')
print('| Frames | Deadline ms | Wall p95/p99/max ms | CPU p99/max ms | Entry gap max ms | Wall/CPU overruns | XRUN | Refus/overflow |')
print('|---:|---:|---:|---:|---:|---:|---:|---:|')
for r in results:
 w=r['wall'];c=r['cpu'];print(f"| {r['frames']} | {r['deadlineUs']/1000:.3f} | {w['p95Us']/1000:.3f}/{w['p99Us']/1000:.3f}/{w['maxUs']/1000:.3f} | {c['p99Us']/1000:.3f}/{c['maxUs']/1000:.3f} | {r['entryGap']['maxUs']/1000:.3f} | {r['wallOverruns']}/{r['cpuOverruns']} | {r['xruns']} | {r['rejected']}/{r['overflow']} |")
print('\nDetailed load intervals (actions included; startup/shutdown are in the whole-run table above):\n')
print('| Frames | Charge | CPU p95/p99/max ms | Wall max ms | Overruns | XRUN delta |')
print('|---:|---|---:|---:|---:|---:|')
for r in results:
 d=json.loads((a.directory/str(r['frames'])/'summary.json').read_text())
 for ph in d['phases']:
  c=ph['cpu'];print(f"| {r['frames']} | {ph['name']} | {c['p95Us']/1000:.3f}/{c['p99Us']/1000:.3f}/{c['maxUs']/1000:.3f} | {ph['wall']['maxUs']/1000:.3f} | {ph['deadlineOverruns']} | {ph['xruns']} |")
raise SystemExit(0 if summary['qualified'] else 2)
