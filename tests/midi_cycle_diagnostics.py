"""Validate every captured event; distinguish MIDI order from JACK clock epochs."""
def analyze(events,frames):
    discontinuities=[];regressions=[]
    for e in events:
        assert len(e)==8,'cycle diagnostics required, no inferred callback IDs'
        assert 0<=e[1]<frames,'MIDI offset outside callback'
        assert e[5]>0 and e[6]>=0,'invalid receiver cycle'
    for index,(a,b) in enumerate(zip(events,events[1:])):
        same=a[5]==b[5]
        if same:
            assert a[0]==b[0] and a[6]==b[6],'inconsistent clock/sample inside one callback'
            assert a[1]<=b[1],f'MIDI order violation inside receiver cycle {a[5]}: {a} then {b}'
        else:
            assert b[5]>a[5],'receiver cycle regressed'
            assert b[6]-a[6]==frames*(b[5]-a[5]),'receiver position/cycle mismatch'
            if b[0]-a[0]!=b[6]-a[6]:discontinuities.append(dict(index=index,previous=a,current=b))
        assert a[6]+a[1]<=b[6]+b[1],'actual receiver MIDI chronology violation'
        if a[0]+a[1]>b[0]+b[1]:
            assert not same and b[0]-a[0]!=b[6]-a[6],'unexplained absolute MIDI chronology violation'
            regressions.append(dict(index=index,previous=a,current=b))
    return dict(clockDiscontinuityCount=len(discontinuities),clockDiscontinuities=discontinuities[:32],absoluteTimestampAmbiguityCount=len(regressions),absoluteTimestampAmbiguities=regressions[:32],withinCycleOrderErrors=0,receiverPositionOrderErrors=0)
