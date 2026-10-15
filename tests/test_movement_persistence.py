#!/usr/bin/env python3
import copy,sys,unittest,time,socket,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_conductor_persistence import ConductorPersistence,uid,block,step
import conductor,portable_project

def movement():return dict(id=uid(),name='FILTER RISE',target=dict(type='CC',channel=1,number=11),points=[[0,0],[.5,.2],[1,1]],duration=1.0,interpolation='LINEAR',retrigger='SOFT_RESTART',glideSeconds=.2)
class MovementPersistence(ConductorPersistence):
 def test_movement_roundtrip_and_atomic_validation(self):
  model=copy.deepcopy(self.model);model.update(version=2,movements=[movement()],ccRate=25)
  model['switches'][0]['steps']=[step([None,block(model['movements'][0]['id'],'MOVEMENT')])]
  self.commit(model);self.assertEqual(self.data()['model'],model);self.assertEqual(self.data()['missingReferences'],[])
  before=self.save();self.load(before);self.assertEqual(self.save(),before);self.assertFalse(self.call()['instances']);self.assertEqual(self.call()['movements']['active'],0)
  project=portable_project.capture(before,48000)
  self.assertEqual(conductor.decode(portable_project.materialize(project,96000)['conductor']),model)
  for key,value in [('ccRate',20),('movements',None)]:
   invalid=copy.deepcopy(model);invalid[key]=value;self.commit(invalid,400);self.assertEqual(self.save(),before)
  for key,value in [('duration',0),('points',[[0,0],[0,1],[1,1]]),('interpolation','BENT'),('glideSeconds',61),('name','bad\\name')]:
   invalid=copy.deepcopy(model);invalid['movements'][0][key]=value;self.commit(invalid,400);self.assertEqual(self.save(),before)
  model['movements']=[];self.commit(model);self.assertEqual(len(self.data()['missingReferences']),1)
 def test_storage_points_are_not_runtime_curve_mapping_limit(self):
  model=copy.deepcopy(self.model);m=movement();m['points']=[[i/100,i/100] for i in range(101)];model.update(version=2,movements=[m],ccRate=100)
  self.commit(model);self.assertEqual(self.data()['model']['movements'][0]['points'],m['points'])
 def test_unrelated_source_learn_forget_preserves_movement(self):
  self.command('controller_source',sourceId=101)
  m=movement();m.update(duration=60,retrigger='DIRECT')
  model=conductor.migrate(self.save());model.update(version=2,movements=[m],ccRate=25);self.commit(model)
  self.command('movement_preview',movementId=m['id']);before=self.call()
  self.assertEqual(before['movements']['active'],1)
  self.command('controller_learn',sourceId=101)
  self.command('midi_cc',channel=2,number=21,value=80)
  self.command('controller_forget',sourceId=101)
  self.command('controller_source',sourceId=101,kind=2,channel=3,number=22)
  after=self.call()
  self.assertEqual(after['movements']['active'],1)
  self.assertEqual(after['movements']['cancelled'],before['movements']['cancelled'])
  self.command('panic');self.assertEqual(self.call()['movements']['active'],0)
 def test_parameter_controller_takeover_and_legacy_refusal(self):
  self.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
  self.command('mapping_commit',mapping=dict(id=1,sourceId=101,targetId=555,instrumentId=1,moduleId=0,kind=1,takeover=0,returnMode=0,points=[[0,0,0],[1,1,0]]))
  m=movement();m.update(duration=5,retrigger='DIRECT',target=dict(type='PARAMETER',instrumentId=1,moduleId=0,kind=1))
  model=conductor.migrate(self.save());model.update(version=2,movements=[m],ccRate=25);self.commit(model)
  self.command('movement_preview',movementId=m['id']);time.sleep(.1);state=self.call();self.assertEqual(state['movements']['active'],1);self.assertLess(state['instruments'][0]['level'],15)
  # Real production MIDI command adapter -> existing mapped ownership core.
  self.command('midi_cc',channel=2,number=21,value=90);time.sleep(.1);state=self.call();self.assertEqual(state['movements']['active'],0);self.assertAlmostEqual(state['instruments'][0]['level'],90,delta=1)
  self.command('panic');self.command('mapping_delete',mappingId=1)
  # Legacy expression ownership cannot receive a competing Movement writer.
  import ast,re,operator
  constants={};ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
  def val(n):
   if isinstance(n,ast.Constant):return n.value
   if isinstance(n,ast.Name):return constants[n.id]
   if isinstance(n,ast.BinOp):return ops[type(n.op)](val(n.left),val(n.right))
   raise ValueError()
  from test_headless_mvp import ROOT
  for name,expr in re.findall(r'\b([A-Z][A-Z0-9_]*)\s*=\s*([^;]+);',(ROOT/'midi_human_looper.jsfx').read_text().split('function ')[0]):
   try:constants[name]=val(ast.parse(expr.strip(),mode='eval').body)
   except (ValueError,KeyError,SyntaxError,TypeError):pass
  patch=self.save();patch['memory'][int(constants['INST_EXP_ASSIGN_BASE'])+1]=1;self.load(patch)
  self.command('movement_preview',movementId=m['id'],expected=409);self.assertEqual(self.call()['movements']['active'],0)
 def test_native_invalid_v2_rejects_without_mutation(self):
  model=copy.deepcopy(self.model);model.update(version=2,movements=[movement()],ccRate=25);self.commit(model);before=self.save();state=self.call()
  model['movements'][0]['points']=[[0,0],[.5,2],[1,1]]
  wire=list(json.dumps(model,sort_keys=True,separators=(',',':')).encode('ascii'))
  line=f"81 5 7 0 {state['revision']} 0 0 0 session {state['engineSessionId']} "+' '.join(format(v,'.17g') for v in before['globals']+before['memory'])+' conductor '+str(len(wire))+' '+' '.join(str(v) for v in wire)+'\n'
  with socket.socket(socket.AF_UNIX) as client:
   client.settimeout(15);client.connect(self.sock);client.sendall(line.encode());data=bytearray()
   while b'\n' not in data:data.extend(client.recv(65536))
  self.assertEqual(json.loads(data)['status'],'invalid');self.assertEqual(self.save(),before)
if __name__=='__main__':unittest.main(defaultTest=['MovementPersistence.'+name for name in ('test_movement_roundtrip_and_atomic_validation','test_storage_points_are_not_runtime_curve_mapping_limit','test_unrelated_source_learn_forget_preserves_movement','test_parameter_controller_takeover_and_legacy_refusal','test_native_invalid_v2_rejects_without_mutation')])
