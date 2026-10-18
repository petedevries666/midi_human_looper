#!/usr/bin/env python3
"""Production native worker/HTTP patch and portable carrier tests; no alternate engine."""
import copy,json,sys,unittest,uuid,urllib.request,urllib.error,socket
from pathlib import Path
from test_headless_mvp import HeadlessTests, ROOT
sys.path.insert(0,str(ROOT/'headless'))
import conductor,portable_project
from server import Control


def uid():return str(uuid.uuid4())
def block(source,kind='PHRASE'):
    return dict(id=uid(),type=kind,sourceId=source,overrides={})
def step(blocks):
    return dict(id=uid(),transition='INHERIT',layers=[dict(id=uid(),block=b) for b in blocks])
def fixture(patch):
    model=conductor.migrate(patch);source=model['sources'][0]['id']
    a=block(source);b=block(source)
    b['overrides']={'playMode':dict(mode='OVERRIDE',value='HOLD'),'trigger':dict(mode='INHERIT')}
    model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([a,None]),step([b,block(uid(),'MOVEMENT')]),step([None,block(uid(),'MOVEMENT')])])]
    return model


class ConductorPersistence(HeadlessTests):
    def setUp(self):
        super().setUp()
        self.control=Control(self.sock)
        state=self.call()
        self.original=self.control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        # Restore a real production legacy patch between cases, not a mock model.
        self.original.pop('conductor',None)
        self.load(self.original)
        self.model=fixture(self.original)
    def load(self,patch,expected='ok'):
        state=self.call();result=self.control.request(op=5,target=patch['schema'],patch=patch,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(result['status'],expected);return result
    def save(self):
        state=self.call();return self.control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
    def data(self):return json.load(urllib.request.urlopen(self.base+'/api/v1/conductor'))
    def commit(self,model,expected=200):return self.command('conductor_commit',conductor=model,expected=expected)
    def test_reference_override_order_delete_missing_atomic_roundtrip(self):
        source_before=self.save()['memory']
        self.commit(self.model)
        self.assertEqual(self.data()['model'],self.model)
        self.assertEqual(len(self.data()['missingReferences']),2)
        model=copy.deepcopy(self.model)
        model['switches'][0]['steps'].reverse()
        model['switches'][0]['steps'][1]['layers'][0]['block']=None
        self.commit(model)
        self.assertEqual(self.data()['model'],model)
        self.assertEqual(self.save()['memory'],source_before)
        model['sources'].pop(0) # refs survive deletion; slot re-use cannot resolve old ID
        model['sources'].append(dict(id=uid(),type='PHRASE',slot=1))
        self.commit(model)
        self.assertEqual(len(self.data()['missingReferences']),3)
        saved=self.save();self.load(saved)
        self.assertEqual(saved,self.save())
        self.assertFalse(self.call()['instances']);self.assertEqual(self.call()['activeNotes'],0)
        # No mutation of the source or sibling override during edits.
        self.assertEqual(self.model['switches'][0]['steps'][0]['layers'][0]['block']['overrides'],{})
    def test_legacy_preserved_and_worker_restart(self):
        self.assertIsNone(self.data()['model'])
        self.commit(self.model)
        self.stop_web();self.start_web()
        self.assertEqual(self.data()['model'],self.model)
        self.load(self.original)
        self.assertIsNone(self.data()['model'])
        self.assertEqual(self.original['memory'],self.save()['memory'])
    def test_invalid_atomic_no_partial_mutation(self):
        self.commit(self.model);before=self.save()
        cases=[]
        def bad(fn):
            m=copy.deepcopy(self.model);fn(m);cases.append(m)
        bad(lambda m:m.update(version=2))
        bad(lambda m:m.update(runtime={'queued':True}))
        bad(lambda m:m['switches'][0]['steps'][0]['layers'][0].update(block=block(uid(),'MOVEMENT')))
        bad(lambda m:m['switches'][0]['steps'][0]['layers'][0]['block']['overrides'].update(muteGroup=dict(mode='OVERRIDE',value=1)))
        bad(lambda m:m['sources'][1].update(id=m['sources'][0]['id']))
        bad(lambda m:m['switches'][0]['steps'][0]['layers'][0]['block']['overrides'].update(playMode=dict(mode='OVERRIDE',value=37)))
        bad(lambda m:m['sources'][1].update(slot=1))
        for model in cases:
            self.commit(model,400);self.assertEqual(before,self.save())
        malformed=copy.deepcopy(before);malformed['conductor']['configuration']=[123,125]
        with self.assertRaises(ValueError):self.load(malformed)
        self.assertEqual(before,self.save())
        # Native worker rejection after adapter validation (actual rollback path).
        broken=copy.deepcopy(before);broken['memory'][164892]=999
        self.load(broken,'invalid');self.assertEqual(before,self.save())
        # Post-handoff rollback: valid carrier/patch, but a Controller binding
        # cannot resolve its instrument after patch activation. Keep old model.
        from controller_config import binding_wire
        replacement=copy.deepcopy(self.model)
        replacement['switches'][0]['traversal']='BACKWARD'
        broken=copy.deepcopy(before);broken['conductor']=conductor.encode(replacement)
        record=[0,0,0,0,0,1,0,0,0,0,0,.02,.2,1,1,.5,1,2]+[0,0,0,1,1,0]+[0]*42
        wire=[1]+[0]*64+record*32
        wire[1:5]=[101,0,0,0]
        wire[65:131]=binding_wire(dict(id=1,sourceId=101,targetId=555,instrumentId=999,kind=1))
        broken['controllerEngine']=dict(version=1,configuration=wire)
        self.load(broken,'invalid');self.assertEqual(before,self.save())
    def test_native_socket_rejects_invalid_typed_document_before_handoff(self):
        self.commit(self.model);before=self.save();state=self.call()
        invalid=copy.deepcopy(self.model)
        invalid['switches'][0]['steps'][0]['layers'][0]['block']['type']='MOVEMENT'
        variants=[invalid,dict(invalid,version=2),dict(invalid,runtime={'queued':True})]
        for model in variants:
            wire=list(json.dumps(model,sort_keys=True,separators=(',',':')).encode('ascii'))
            line=f"81 5 7 0 {state['revision']} 0 0 0 session {state['engineSessionId']} "+' '.join(format(v,'.17g') for v in before['globals']+before['memory'])+' conductor '+str(len(wire))+' '+' '.join(str(v) for v in wire)+'\n'
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(15);client.connect(self.sock);client.sendall(line.encode());data=bytearray()
                while b'\n' not in data:data.extend(client.recv(65536))
            self.assertEqual(json.loads(data)['status'],'invalid')
            self.assertEqual(before,self.save())

    def test_disk_save_reload_failed_load_and_legacy_migrations(self):
        self.commit(self.model)
        directory=Path(self.temp.name)/'patches';path=directory/'patch1.json'
        def disk(action,expected=200):
            state=self.call();req=urllib.request.Request(self.base+'/api/v1/patch/'+action,data=json.dumps(dict(slot=1,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])).encode(),headers={'Content-Type':'application/json'})
            try:response=urllib.request.urlopen(req,timeout=10)
            except urllib.error.HTTPError as error:response=error
            self.assertEqual(response.status,expected);response.close()
        disk('save');first=path.read_bytes()
        self.load(self.original);disk('load');disk('save')
        self.assertEqual(path.read_bytes(),first)
        before=self.save();bad=copy.deepcopy(before);bad['conductor']['version']=99
        path.write_text(json.dumps(bad));disk('load',422)
        self.assertEqual(before,self.save())
        original_bad=path.read_bytes();disk('save',422);self.assertEqual(path.read_bytes(),original_bad)
        path.write_bytes(first)
        for schema,size in enumerate(portable_project.MARKERS,1):
            legacy=dict(format=self.original['format'],schema=schema,work_mem_size=size,globals=self.original['globals'],memory=self.original['memory'][:size])
            self.load(legacy)
            migrated=self.save()
            self.assertEqual(migrated['schema'],7);self.assertNotIn('conductor',migrated)
            self.assertEqual(migrated['memory'][:164840],legacy['memory'][:164840])
            self.assertFalse(self.call()['instances'])

    def test_portable_and_reaper_preservation(self):
        self.commit(self.model);patch=self.save()
        project=portable_project.capture(patch,48000)
        self.assertEqual(project['version'],1)
        for rate in (44100,48000,96000):
            restored=portable_project.materialize(project,rate)
            self.assertEqual(conductor.decode(restored['conductor']),self.model)
        original=copy.deepcopy(project)
        with self.assertRaisesRegex(ValueError,'REAPER cannot execute CONDUCTOR'):
            portable_project.materialize(project,48000,'reaper')
        self.assertEqual(original,project)
    def test_commit_conflict_and_active_notes_refusal(self):
        old=self.call();self.command('midi',channel=1,note=61,value=100)
        self.commit(self.model,409)
        self.assertIsNone(self.data()['model'])
        self.assertGreater(self.call()['activeNotes'],0)
        self.command('midi',channel=1,note=61,value=0)
        self.command('instrument_route',instrumentId=1,field='level',value=73)
        self.call(dict(protocolVersion=1,action='conductor_commit',conductor=self.model,expectedRevision=old['revision']),expected=409)
        self.assertIsNone(self.data()['model'])
    def test_two_switches_shared_source_actions_no_autoplay(self):
        other=copy.deepcopy(self.model['switches'][0]);other['switchId']=2
        for st in other['steps']:
            st['id']=uid()
            for layer in st['layers']:
                layer['id']=uid()
                if layer['block']:layer['block']['id']=uid()
        other['steps'][0]['layers'][1]['block']=dict(id=uid(),type='ACTION',action='STOP',target=dict(type='ALL_PHRASES'),trigger='PRESS')
        self.model['switches'].append(other)
        self.commit(self.model)
        self.assertEqual(self.data()['model'],self.model)
        self.assertFalse(self.call()['instances'])
        patch=self.save();self.load(patch)
        self.assertFalse(self.call()['instances']);self.assertEqual(self.call()['activeNotes'],0)

if __name__=='__main__':
    unittest.main(defaultTest='ConductorPersistence')
