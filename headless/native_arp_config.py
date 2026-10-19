"""Native ARP settings v1; absent carrier migrates to STEP MAX 2 / CONTINUOUS."""
def decode(extension):
    if not isinstance(extension,dict) or set(extension)!={'version','configuration'} or type(extension['version']) is not int or extension['version']!=1:
        raise ValueError('Unsupported native ARP version; original preserved')
    wire=extension['configuration']
    if not isinstance(wire,list) or len(wire)<2 or any(type(v) is not int for v in wire) or wire[0]!=1 or not 0<=wire[1]<=8 or len(wire)!=2+wire[1]*3:
        raise ValueError('Invalid native ARP settings')
    rows=[];ids=set()
    for at in range(2,len(wire),3):
        ident,step,playback=wire[at:at+3]
        if not 1<=ident<=16777215 or ident in ids or not 1<=step<=4 or playback not in (0,1):raise ValueError('Invalid native ARP target/range')
        ids.add(ident);rows.append((ident,step,playback))
    return rows
