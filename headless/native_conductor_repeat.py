"""Count admitted STEP entries, not HOLD/release phases or incoming MIDI edges."""
def extend(source):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Native REPEAT contract changed: '+old[:90])
        source=source.replace(old,new)
    change('function instance_discard_all()',
           'NATIVE_CONDUCTOR_REPEAT_BASE=CONDUCTOR_BASE-6700;\nfunction instance_discard_all()')
    # Runtime counters occupy 128 cells between snapshot actions and release
    # flags. They are deliberately absent from serialized musical source data.
    change('function conductor_has(si)', '''function native_conductor_repeat_limit(b)
local(a)
(a=mem[b+79];a>0?max(1,min(999,mem[a+1+mem[a]*4+mem[b+2]])):1;);
function native_conductor_next(si)
local(h,current,b,used)
(h=conductor_header(si);current=mem[h+3];b=mem[h+2]+max(0,current)*80;
 used=mem[NATIVE_CONDUCTOR_REPEAT_BASE+si*2];
 current>=0 && used>=1 && used<native_conductor_repeat_limit(b)?current:(current+1)%max(1,mem[h+1]););
function native_conductor_repeat_commit(si,b,step)
local(h,a,limit,used)
(h=conductor_header(si);a=NATIVE_CONDUCTOR_REPEAT_BASE+si*2;
 limit=native_conductor_repeat_limit(b);used=mem[a];
 mem[a]=mem[h+3]==step && used>=1 && used<limit?used+1:1;mem[a+1]=limit;);
function conductor_has(si)''')
    change('step=phase?mem[h+3]:(mem[h+3]+1)%mem[h+1];',
           'step=phase?mem[h+3]:native_conductor_next(si);')
    # This point is reached only after source safety, output capacity and voice
    # admission checks. Refused entries and later gesture phases consume none.
    change(');mem[h+3]=step;mem[sw_rt(si)+7]=step;',
           ');!phase?native_conductor_repeat_commit(si,b,step);mem[h+3]=step;mem[sw_rt(si)+7]=step;')
    change('mem[sw_rt(si)+23]=(mem[h+3]+1)%max(1,mem[h+1])+1;',
           'mem[sw_rt(si)+23]=native_conductor_next(si)+1;')
    change('mem[g+3]=(mem[h+3]+1)%mem[h+1]+1;',
           'mem[g+3]=native_conductor_next(si)+1;')
    change('mem[h+2]+((mem[h+3]+1)%max(1,mem[h+1]))*80',
           'mem[h+2]+native_conductor_next(si)*80')
    change('(mem[conductor_header(si)+3]+1)%max(1,mem[conductor_header(si)+1])+1',
           'native_conductor_next(si)+1')
    return source
