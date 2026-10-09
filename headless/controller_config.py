"""Versioned native Controller wire contract; UI-independent validation."""
import math
FIELDS=('id','sourceId','targetId','instrumentId','moduleId','kind','base','priority','takeover','returnMode','easing','threshold','glideSeconds','slewPerSecond','idleSeconds','returnSeconds','enabled','pointCount')
DEFAULT=[0,0,0,0,0,1,0,0,0,0,0,.02,.2,1,1,.5,1,2]
def binding_wire(data):
    if not isinstance(data,dict):raise ValueError('mapping required')
    points=data.get('points',[[0,0,0],[1,1,0]])
    if not isinstance(points,list) or not 2<=len(points)<=16:raise ValueError('curve point count')
    result=[data.get(field,default) for field,default in zip(FIELDS,DEFAULT)]
    result[17]=len(points)
    if any(type(v) is not int or not 0<=v<=16777215 for v in result[:6]):raise ValueError('stable IDs/kind required')
    if not all(result[j] for j in (0,1,2,3)) or result[5]>15:raise ValueError('invalid mapping identity')
    if any(type(result[j]) is not int or not 0<=result[j]<=limit for j,limit in ((7,1000),(8,3),(9,3),(10,1),(16,1))):raise ValueError('invalid policy')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in result):raise ValueError('finite values required')
    if not 0<=result[6]<=1 or not 0<=result[11]<=1 or not 0<result[12]<=60 or not 0<result[13]<=1000 or not 0<=result[14]<=3600 or not 0<result[15]<=60:raise ValueError('invalid duration/threshold')
    previous=-1
    for point in points:
        if not isinstance(point,list) or len(point)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):raise ValueError('invalid point')
        x,y,bend=point
        if not 0<=x<=1 or x<=previous or not 0<=y<=1 or abs(bend)>.98:raise ValueError('invalid curve')
        previous=x;result.extend(point)
    if points[0][0]!=0 or points[-1][0]!=1:raise ValueError('curve endpoints required')
    result.extend([0]*(3*(16-len(points))))
    return result
def decode(document):
    if not isinstance(document,dict) or type(document.get('version')) is not int or document.get('version')!=1:raise ValueError('controller configuration version')
    wire=document.get('configuration')
    if not isinstance(wire,list) or len(wire)!=2177 or wire[0]!=1 or any(type(v) not in (int,float) or not math.isfinite(v) for v in wire):raise ValueError('invalid controller configuration')
    sources=[];bindings=[]
    for i in range(16):
        record=wire[1+4*i:5+4*i]
        if record[0]:
            if any(type(v) is not int for v in record) or not 1<=record[0]<=16777215 or not 0<=record[1]<=2 or not 0<=record[2]<16 or not 0<=record[3]<128:raise ValueError('invalid source')
            sources.append(dict(zip(('id','kind','channel','number'),record)))
    for i in range(32):
        record=wire[65+66*i:65+66*(i+1)]
        if record[0]:
            b=dict(zip(FIELDS,record[:18]));
            if type(b['pointCount']) is not int or not 2<=b['pointCount']<=16:raise ValueError('invalid point count')
            b['points']=[record[18+3*j:21+3*j] for j in range(int(b['pointCount']))];binding_wire(b);b['slot']=i;bindings.append(b)
    return dict(sources=sources,mappings=bindings)
