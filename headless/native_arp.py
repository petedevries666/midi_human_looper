"""Native-only bounded arp selectors. Scratch is runtime-only, never serialized."""
EEL = r'''
function native_arp_pick(gi,mode)
local(b,count,n,j,changed,idx,last,pos,pick,tmp,direction,remaining,delta,result,length)
(
 b=28000000+gi*1024;count=0;changed=mem[b]!=mode+1;
 n=0;loop(128,mem[engine_addr(ARP_HELD_COUNT_BASE,gi*128+n)]>0?(
   mem[b+16+count]!=n?changed=1;mem[b+16+count]=n;count+=1;
 );n+=1;);
 count!=mem[b+1]?changed=1;last=mem[b+4];
 changed?(
   mem[b]=mode+1;mem[b+1]=count;mem[b+2]=0;mem[b+3]=mode==10 || mode==12?-1:1;
   mem[b+4]=-1;last=-1;
 );
 result=-1;
 count>0?(
 idx=-1;j=0;loop(count,mem[b+16+j]==last?idx=j;j+=1;);
 mode==3?(
   pick=floor(rand(max(1,count-(idx>=0 && count>1))));
   idx>=0 && count>1 && pick>=idx?pick+=1;
 ):
 mode==4?(
   pos=mem[b+2];
   changed || pos>=count?(
     j=0;loop(count,mem[b+272+j]=j;j+=1;);
     j=count-1;loop(max(0,count-1),n=floor(rand(j+1));tmp=mem[b+272+j];mem[b+272+j]=mem[b+272+n];mem[b+272+n]=tmp;j-=1;);
     count>1 && mem[b+16+mem[b+272]]==last?(tmp=mem[b+272];mem[b+272]=mem[b+273];mem[b+273]=tmp;);
     pos=0;
   );pick=mem[b+272+pos];mem[b+2]=pos+1;
 ):
 mode==5 || mode==7?(
   length=8;pos=mem[b+2];
   changed?(j=0;loop(length,mem[b+400+j]=floor(rand(count));j+=1;););
   mode==7 && pos>=length?(j=0;loop(length,rand(1)<.25?mem[b+400+j]=floor(rand(count));j+=1;););
   pos%=length;pick=mem[b+400+pos];mem[b+2]=pos+1;
 ):
 mode==6?(
   idx<0?pick=floor(rand(count)):(
     count<=1?pick=0:(idx<=0?direction=1:idx>=count-1?direction=-1:direction=rand(1)<.5?-1:1;pick=idx+direction;);
   );
 ):
 mode==8?(
   // Rank weighting: the lowest held note has count tickets, the highest one.
   remaining=floor(rand(count*(count+1)/2));pick=-1;
   j=0;loop(count,pick<0?(remaining<count-j?pick=j:remaining-=count-j;);j+=1;);
 ):(
   // CLIMB is an exploratory, biased random walk, not a sorted-note staircase.
   // Both UP variants begin at the bottom; both DOWN variants at the top.
   // Reverse the preferred direction at the endpoints, never teleport.
   direction=mem[b+3];
   idx<0?pick=direction>0?0:count-1:(
     count<=1?pick=0:(
       idx==count-1?direction=-1;
       idx==0?direction=1;
       // 70% in the preferred direction, 30% of exploratory backtracking.
       // When a chosen direction is blocked, take the available direction.
       n=rand(1)<.7?direction:-direction;
       remaining=n>0?count-1-idx:idx;
       remaining<=0?(n=-n;remaining=n>0?count-1-idx:idx;);
       // STEP MAX = 2 held-note positions (native default).
       delta=min(remaining,1+floor(rand(2)));
       pick=idx+n*delta;
     );
   );mem[b+3]=direction;
 );
 result=mem[b+16+max(0,min(count-1,pick))];mem[b+4]=result;
 );result;
);
'''

def extend(source):
    anchor='function arp_process_instrument(gi)'
    if source.count(anchor)!=1:raise ValueError('ARP function contract changed')
    source=source.replace(anchor,'memset(28000000,0,8192);\n'+EEL+'\n'+anchor)
    source=source.replace('sw_edit_target=-1;sw_preview_target=-1;sw_edit_new=0;', 'memset(28000000,0,8192);sw_edit_target=-1;sw_preview_target=-1;sw_edit_new=0;')
    old='mode==0 ? (\n          pick=floor(rand(held)); n=0;'
    if source.count(old)!=1:raise ValueError('ARP selector contract changed')
    source=source.replace(old,'mode>=3 ? choice=native_arp_pick(gi,mode) : '+old)
    # Reset patterns when all sources disappear or the instrument is disabled.
    source=source.replace('held<=0 ? (arp_release_instrument(gi);','held<=0 ? (mem[28000000+gi*1024]=0;arp_release_instrument(gi);')
    source=source.replace(') : (arp_release_instrument(gi);mem[engine_addr(ARP_STEP_REMAIN_BASE,gi)]=0;);',') : (mem[28000000+gi*1024]=0;arp_release_instrument(gi);mem[engine_addr(ARP_STEP_REMAIN_BASE,gi)]=0;);')
    # Legacy EEL bounds remain frozen; widen only its generated native variant.
    import re
    source,n=re.subn(r'(function param_max\(kind\).*?kind==4\s*\?\s*)2\b',r'\g<1>12',source,count=1,flags=re.S)
    if n!=1:raise ValueError('ARP parameter bound contract changed')
    return source
