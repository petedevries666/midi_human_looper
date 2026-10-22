"""Versioned HUMANIZER / VELOCITY CURVES patch carrier (schema 8)."""
import math

LIMIT=16_777_215

def decode(extension):
    if not isinstance(extension,dict) or set(extension)!={'version','configuration'} or type(extension['version']) is not int or extension['version']!=1:
        raise ValueError('Unsupported native expressive version; original patch preserved')
    wire=extension['configuration']
    if not isinstance(wire,list) or len(wire)<2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in wire):
        raise ValueError('Invalid native expressive carrier')
    if any(type(v) is not int for v in wire[:4]) or wire[0]!=1 or not 0<=wire[1]<=8:
        raise ValueError('Invalid native expressive header')
    rows=[];seen=set();at=2
    for _ in range(wire[1]):
        if len(wire)-at<15:raise ValueError('Truncated native expressive row')
        # Keep the wire order aligned with the native codec: velocity spread
        # precedes the three enum selectors.
        ident,hid,hen,timing,bias,velocity,feel,evolving,scope,seed,lookahead,cid,cen,amount,count=wire[at:at+15]
        if any(type(v) is not int for v in (ident,hid,hen,feel,evolving,scope,seed,cid,cen,count)):
            raise ValueError('Native expressive identities and enums must be integers')
        if not 1<=ident<=LIMIT or ident in seen or not 0<=hid<=LIMIT or hen not in (0,1):
            raise ValueError('Invalid HUMANIZER identity or bypass')
        if not math.isfinite(timing) or not 0<=timing<=2000 or not math.isfinite(bias) or not -2000<=bias<=2000 or not math.isfinite(velocity) or not 0<=velocity<=100:
            raise ValueError('HUMANIZER parameter outside range')
        if feel not in (0,1) or evolving not in (0,1) or scope not in (0,1) or not 0<=seed<=0xffffffff or not math.isfinite(lookahead) or not 0<=lookahead<=2000:
            raise ValueError('Invalid HUMANIZER mode, seed or lookahead')
        if not 0<=cid<=LIMIT or cen not in (0,1) or not math.isfinite(amount) or not 0<=amount<=100 or not 2<=count<=16:
            raise ValueError('Invalid VELOCITY CURVES settings')
        at+=15
        points=[]
        if len(wire)-at<count*2:raise ValueError('Truncated velocity curve')
        for _point in range(count):
            x,y=wire[at:at+2];at+=2
            if type(x) is not int or type(y) is not int or not 1<=x<=127 or not 1<=y<=127:
                raise ValueError('Curve points must be MIDI velocities 1..127')
            if points and x<=points[-1][0]:raise ValueError('Curve input points must increase strictly')
            points.append((x,y))
        if points[0][0]!=1 or points[-1][0]!=127:raise ValueError('Curve must span input velocity 1..127')
        seen.add(ident);rows.append((ident,hid,hen,timing,bias,velocity,feel,evolving,scope,seed,lookahead,cid,cen,amount,points))
    if at!=len(wire):raise ValueError('Trailing native expressive data')
    return rows

def wire(extension):
    decode(extension)
    return extension['configuration']
