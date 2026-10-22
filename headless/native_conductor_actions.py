"""Bounded typed actions for the native Conductor; frozen legacy source untouched."""
def extend(source):
    # These existing functions do not call Conductor. Declare them before its
    # action dispatcher so EEL resolves the same production STOP/PANIC helpers.
    start=source.index('function sw_traverse(si)')
    end=source.index('function sw_fire(si,gesture,offs)',start)
    helpers=source[start:end]
    source=source[:start]+source[end:]
    anchor='function conductor_apply(si,offs,phase)'
    if source.count(anchor)!=1:raise ValueError('Conductor action insertion changed')
    dispatch='''function native_conductor_actions(si,b,offs,phase)
local(a,n,j,op,kind,target,p,r)
(
 a=mem[b+79];a>0?(n=min(32,max(0,mem[a]));a+=1;j=0;loop(n,
  mem[a]==phase?(
   op=mem[a+1];kind=mem[a+2];target=mem[a+3];
   op==1?(kind==2?sw_stop_phrases_at(offs):(
    p=0;loop(LAYERS,(kind==0&&p==target)||(kind==1&&mem[PHRASE_GROUP_BASE+p]==target)?(
     mem[MODE_BASE+p]>=.5?phrase_toggle_stop(p,offs):free_loop_stop_at(p,offs);
    );p+=1;);
   )):op==3?sw_reset(target):op==4?(r=sw_rt(target);mem[r+9]=0;mem[r+10]=-1;):
   op==5?(sw_stop_phrases_at(offs);sw_reset(target);):
   op==6?(sw_stop_phrases_at(offs);native_panic_at(offs););
  );a+=4;j+=1;
 ););
);
'''
    source=source.replace(anchor,helpers+dispatch+anchor)
    anchor='j=0;loop(min(MAX_ONCE_VOICES,mem[b+2]),p=mem[b+4+j*5];'
    # Only the admission loop, after whole-step validation and cursor commit.
    if source.count(anchor)!=1:raise ValueError('Conductor admission contract changed')
    return source.replace(anchor,'native_conductor_actions(si,b,offs,phase);\n    '+anchor)
