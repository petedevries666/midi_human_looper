"""UI-neutral descriptor contracts; no engine timing or live parameter ownership."""
import json, math
from pathlib import Path
class Registry:
    def __init__(self,document):
        if document.get('contractVersion')!=1:raise ValueError('unsupported contract')
        self.parameters={};self.modules={};self.engine_types={}
        for p in document['parameters']:
            if p['id'] in self.parameters or p['valueType'] not in ('float','int','enum','toggle') or not p['min']<=p['default']<=p['max'] or p['min']>=p['max'] or p['step']<=0:raise ValueError('invalid parameter')
            self.parameters[p['id']]=dict(p)
        for m in document['modules']:self.register(m)
    def register(self,module):
        required=('typeId','scope','parameters','serializationVersion','migration','processingStage','orderingConstraints','stateResetHook','panicHook')
        if any(k not in module for k in required) or module['scope'] not in ('phrase','instrument','global') or module['typeId'] in self.modules or any(p not in self.parameters for p in module['parameters']):raise ValueError('invalid module')
        if module['engineType'] in self.engine_types:raise ValueError('duplicate engine type')
        self.modules[module['typeId']]=dict(module);self.engine_types[module['engineType']]=module['typeId']
    def normalize(self,id,value):
        p=self.parameters[id]
        if not math.isfinite(value):raise ValueError('nonfinite parameter')
        return max(0,min(1,(value-p['min'])/(p['max']-p['min'])))
    def scale(self,id,x):
        p=self.parameters[id];x=max(0,min(1,x))
        if p['normalizedConversion']=='equal_bins':return min(p['max'],math.floor(x*(p['max']+1)))
        raw=p['min']+(p['max']-p['min'])*x
        return max(p['min'],min(p['max'],math.floor(raw/p['step']+.5)*p['step']))
    def document(self):
        return dict(contractVersion=1,parameters=list(self.parameters.values()),modules=list(self.modules.values()))
REGISTRY=Registry(json.loads((Path(__file__).resolve().parents[1]/'modules/catalog.json').read_text()))
