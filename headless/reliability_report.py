"""Read-only evidence reduction. Counter increases are failures, never retried away."""
import math
FIELDS=('buildRevision','engineSessionId','backend','sampleRate','blockSize',
        'chainTimingVersion','chainFrameGap','chainClockGap','chainError',
        'lateBlocks','maxCallbackUs','outputOverflow','activeNotes','pendingOutput')

def summarize(samples):
    if len(samples)<2:
        raise ValueError('at least two state observations required')
    for state in samples:
        for key in ('sampleRate','blockSize','lateBlocks','outputOverflow','maxCallbackUs'):
            value=state.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError('invalid/missing diagnostic: '+key)
        if state['sampleRate']==0 or state['blockSize']==0:
            raise ValueError('invalid zero sample rate/block size')
    problems=[]
    first,last=samples[0],samples[-1]
    for key in ('engineSessionId','sampleRate','blockSize'):
        if any(s.get(key)!=first.get(key) for s in samples):
            problems.append(key+' changed: interval cannot be compared')
    for key in ('lateBlocks','outputOverflow'):
        values=[s[key] for s in samples]
        if any(b<a for a,b in zip(values,values[1:])):
            problems.append(key+' counter reset')
        if any(b>a for a,b in zip(values,values[1:])):
            problems.append(key+' increased')
    if any(s.get('chainError') or s.get('chainFrameGap') or s.get('chainClockGap') for s in samples):
        problems.append('transport/recording interruption reported')
    period=last['blockSize']*1e6/last['sampleRate']
    if max(s['maxCallbackUs'] for s in samples)>=period:
        problems.append('historical callback maximum reached current block deadline')
    if any(s.get('backend')!='jack' for s in samples):
        problems.append('not a JACK hardware observation')
    return dict(first={k:first.get(k) for k in FIELDS},last={k:last.get(k) for k in FIELDS},
                observations=len(samples),blockPeriodUs=period,problems=problems,
                qualification='observational evidence only; not hardware certification')
