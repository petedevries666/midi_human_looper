#!/usr/bin/env python3
"""Paired LAN client and bounded asynchronous ReaScript file-spool worker.
No network operation is performed in REAPER's JSFX or MIDI callback.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from phrase_midi import read_smf, write_smf
import portable_project as portable
from project_sync import atomic_json, read, Conflict

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Paired origin redirected; refusing to forward authentication')

class Bridge:
    def __init__(self, live, token, spool):
        url=urllib.parse.urlsplit(live)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError('Use a paired engine origin, without embedded credentials')
        self.live=live.rstrip('/');self.token=token;self.spool=Path(spool)
        self.spool.mkdir(parents=True,exist_ok=True)
    def remote(self,path,data=None,binary=False):
        request=urllib.request.Request(self.live+path,data=portable.canonical(data) if data is not None else None,
                                      headers={'Content-Type':'application/json','X-Engine-Token':self.token})
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=15) as response:
                raw=response.read(portable.MAX_BYTES+1)
                if len(raw)>portable.MAX_BYTES:raise ValueError('Oversized remote response')
                return raw if binary else json.loads(raw)
        except urllib.error.HTTPError as error:
            try:message=json.loads(error.read(4096)).get('error','Remote command refused')
            except ValueError:message='Remote command refused'
            raise Conflict(message) from None
    def baseline(self):
        path=self.spool/'baseline.json'
        return read(path) if path.exists() else None
    def execute(self,job):
        if not isinstance(job,dict) or job.get('version')!=1:raise ValueError('Unsupported bridge job')
        action=job.get('action');phrase=job.get('phraseId')
        client_id=str(uuid.UUID(job['reaperProjectId'])) if job.get('reaperProjectId') else None
        if action in ('send_preview','send','get'):
            if type(phrase) is not int or not 1<=phrase<=16:raise ValueError('Phrase ID must be 1..16')
            if action=='get':return {'phrase':read_smf(self.remote(f'/api/v1/phrase/{phrase}/midi',binary=True))}
            smf=write_smf(job['phrase']);state=self.remote('/api/v1/state')
            if action=='send':
                expected=job['expected']
                if state['revision']!=expected['revision'] or state['engineSessionId']!=expected['engineSessionId']:raise Conflict('Live target changed after preview; preview again')
            return self.remote('/api/v1/phrase/midi',dict(file=base64.b64encode(smf).decode(),phraseId=phrase,
                mode='preview' if action=='send_preview' else 'replace',expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])) | {'expected':{'revision':state['revision'],'engineSessionId':state['engineSessionId']}}
        if action=='push':
            live=self.remote('/api/v1/project/capture');base=self.baseline()
            if base:
                if base.get('reaperProjectId')!=client_id:
                    raise Conflict('Different REAPER project; explicitly PULL/adopt before PUSH')
                if live['activeRevisionId']!=base['activeRevisionId'] or live['fingerprint']!=base['remoteFingerprint']:
                    raise Conflict('Live changes conflict with local baseline. PULL or duplicate before PUSH')
            elif job.get('confirmInitialReplace') is not True:
                raise Conflict('First PUSH requires explicit initial replacement confirmation')
            local=job['patch'];sample_rate=job['sampleRate']
            # The legacy REAPER mailbox cannot carry native-only control data.
            # Never let a base-only PUSH erase #30's live extensions.
            portable.materialize(live['project'],sample_rate,'reaper')
            import copy
            local=copy.deepcopy(local)
            for extension in ('controllerEngine','globalSnapshots'):
                if extension not in local and extension in live['project']['payload']['patch']:
                    local[extension]=copy.deepcopy(live['project']['payload']['patch'][extension])
            project=portable.capture(local,sample_rate,client_id if client_id and live['activeRevisionId'] is None else live['project']['projectId'],live['activeRevisionId'],job.get('name',live['project']['payload']['name']))
            staged=self.remote('/api/v1/project/stage',dict(project=project,expectedActiveRevisionId=live['activeRevisionId']))
            result=self.remote('/api/v1/project/activate',dict(revisionId=staged['revisionId'],expectedActiveRevisionId=live['activeRevisionId'],
                expectedRevision=live['engineRevision'],expectedEngineSessionId=live['engineSessionId'],expectedFingerprint=live['fingerprint']))
            atomic_json(self.spool/'local-project.json',project)
            atomic_json(self.spool/'baseline.json',dict(activeRevisionId=result['revisionId'],remoteFingerprint=result['fingerprint'],
                localFingerprint=portable.digest(portable.timing(job['patch'],1/portable.rate(sample_rate))),reaperProjectId=client_id))
            return result
        if action=='pull_duplicate':
            live=self.remote('/api/v1/project/capture')
            filename='project-'+live['project']['revisionId']+'.json'
            atomic_json(self.spool/filename,portable.validate(live['project']))
            return dict(status='duplicated',file=filename)
        if action=='pull':
            base=self.baseline();local=job['patch'];sample_rate=job['sampleRate']
            fingerprint=portable.digest(portable.timing(local,1/portable.rate(sample_rate)))
            if (not base or base.get('reaperProjectId')!=client_id or fingerprint!=base['localFingerprint']) and job.get('confirmLocalReplace') is not True:
                raise Conflict('Local edits are unsynchronized; explicitly replace, duplicate or cancel')
            live=self.remote('/api/v1/project/capture')
            # Check execution capability before any local executable state changes.
            patch=portable.materialize(live['project'],sample_rate,'reaper')
            pending=str(uuid.uuid4())
            baseline=dict(activeRevisionId=live['activeRevisionId'],remoteFingerprint=live['fingerprint'],
                localFingerprint=portable.digest(portable.timing(patch,1/portable.rate(sample_rate))),reaperProjectId=client_id)
            atomic_json(self.spool/('pull-'+pending+'.json'),dict(project=live['project'],baseline=baseline))
            return dict(patch=patch,pendingId=pending)
        if action=='pull_commit':
            # Only ReaScript's successful JSFX acknowledgement commits its own
            # transaction, never another concurrently retrieved project.
            pending=str(uuid.UUID(job['pendingId']))
            path=self.spool/('pull-'+pending+'.json');document=read(path)
            atomic_json(self.spool/'local-project.json',portable.validate(document['project']))
            atomic_json(self.spool/'baseline.json',document['baseline']);path.unlink()
            return dict(status='pulled')
        raise ValueError('Unknown bridge action')
    def once(self):
        # Never execute unbounded work or arbitrary paths/commands from a job.
        paths=sorted(self.spool.glob('*.job.json'))[:8]
        for path in paths:
            stem=path.name[:-9]
            try:uuid.UUID(stem)
            except ValueError:continue
            claimed=self.spool/(stem+'.working.json')
            try:path.rename(claimed)
            except FileNotFoundError:continue
            try:result=dict(ok=True,result=self.execute(read(claimed)))
            except (ValueError,KeyError,TypeError,OSError) as error:result=dict(ok=False,error=str(error))
            atomic_json(self.spool/(stem+'.result.json'),result)
            claimed.unlink()
        return len(paths)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',required=True);parser.add_argument('--token-file',type=Path)
    parser.add_argument('--spool',type=Path,required=True);parser.add_argument('--once',action='store_true')
    args=parser.parse_args();bridge=Bridge(args.live,args.token_file.read_text().strip() if args.token_file else '',args.spool)
    if args.once:bridge.once()
    else:
        try:
            while True:bridge.once();time.sleep(.1)
        except KeyboardInterrupt:pass
