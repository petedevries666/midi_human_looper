"""Scoped Zynthian chain capture. No routes, playback, patches or other chains change."""
import copy, hashlib, json, time, uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit


def clone(value):
    return json.loads(json.dumps(value, allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def fingerprint(chain,links,aliases=None):
    destination={'chainId':chain.chain_id}
    return digest(dict(processors=visible_state(chain,aliases),
                       volume=links.chain_volume(destination),pan=links.chain_pan(destination)))


def validate_assets(document, root):
    records=document.get('mbmfChainSaves',{})
    if not isinstance(records,dict) or len(records)>128:raise ValueError('Invalid saved chain references')
    for record in records.values():
        assets=record.get('assets',[])
        if not isinstance(assets,list) or len(assets)>16:raise ValueError('Invalid chain preset assets')
        for asset in assets:
            uri=urlsplit(asset['uri']);path=Path(unquote(uri.path))
            if uri.scheme!='file' or path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()) or not path.is_file() or path.stat().st_size>33554432:
                raise ValueError('Un preset de la chaîne est indisponible')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=asset['sha256']:
                raise ValueError('Un preset sauvegardé a changé ; refaire SAVE CHAÎNE')


def members(chain):
    result=[]
    for role, attribute in (('MIDI','midi_slots'),('INSTRUMENT','synth_slots'),('FX','audio_slots')):
        for slot in getattr(chain,attribute,[]):
            for processor in slot:
                result.append((role,processor))
    if not result or len(result)>16 or len({p.id for _,p in result})!=len(result):
        raise ValueError('Chaîne vide, partagée ou trop grande pour SAVE')
    return result


def summary(chain):
    values=[]
    for role,p in members(chain):
        preset=getattr(p,'preset_info',None)
        values.append(dict(role=role,id=p.id,instrument=str(p.eng_code).split('/',1)[-1],
                           preset=str(preset[2]) if preset else 'AUCUN PRESET'))
    return values


def visible_state(chain, aliases=None):
    aliases=aliases or {}
    result=[]
    for role,p in members(chain):
        state=clone(p.get_state());preset=state.get('preset_info')
        uri=preset[0] if preset else None
        result.append(dict(role=role,id=p.id,engine=p.eng_code,
                           preset=aliases.get(uri,uri),controllers=state.get('controllers',{})))
    return result


def snapshot_chain(document, identity):
    matches=[]
    for key,config in document.get('engine_config',{}).items():
        if key.startswith('MB/'):
            matches.extend(str(cid) for cid,value in config.get('hostChainIdentities',{}).items() if value.get('identity')==identity)
    if len(matches)!=1 or matches[0] not in document.get('chains',{}):
        raise ValueError('Cette chaîne manque au snapshot : sauvegarder d’abord la paire patch + snapshot')
    return matches[0]


def saved_summary(document, identity):
    try: cid=snapshot_chain(document,identity)
    except ValueError:return None
    states=document.get('zs3',{}).get('zs3-0',{}).get('processors',{})
    values=[]
    for slot in document['chains'][cid].get('slots',[]):
        for pid,code in slot.items():
            p=states.get(str(pid),{}).get('preset_info')
            values.append(dict(instrument=str(code).split('/',1)[-1],preset=str(p[2]) if p else 'AUCUN PRESET'))
    return dict(chainId=cid,processors=values,record=document.get('mbmfChainSaves',{}).get(identity))


def scoped_update(document, cid, chain_state, processor_states, record, mixer=None, extended=None):
    """Replace only the selected instrument/FX slots and their captured settings."""
    result=clone(document);cid=str(cid);before=result['chains'][cid]
    old_ids={str(pid) for slot in before['slots'] for pid in slot}
    other_ids={str(pid) for key,c in result['chains'].items() if str(key)!=cid for slot in c['slots'] for pid in slot}
    new_ids={str(pid) for slot in chain_state['slots'] for pid in slot}
    if new_ids & other_ids or new_ids!=set(processor_states):
        raise ValueError('Identités des effets en conflit : actualiser le snapshot complet')
    if before.get('midi_chan')!=chain_state.get('midi_chan') or before.get('mixer_chan')!=chain_state.get('mixer_chan'):
        raise ValueError('Canal de chaîne modifié : actualiser le snapshot complet')
    # Preserve routing, MIDI profile, source phrases, other ZS3s and engine state.
    before['slots']=clone(chain_state['slots']);before['fader_pos']=chain_state.get('fader_pos',before.get('fader_pos',0))
    states=result['zs3']['zs3-0']['processors']
    for pid in old_ids:states.pop(pid,None)
    states.update(clone(processor_states))
    if mixer is not None:
        key=f"chan_{before['mixer_chan']:02d}"
        result['zs3']['zs3-0'].setdefault('mixer',{})[key]=clone(mixer)
    for key,value in (extended or {}).items():
        if key.startswith('MB/'):raise ValueError('Ne peut pas remplacer le moteur MBMF')
        if value:result.setdefault('engine_config',{})[key]=clone(value)
    result.setdefault('mbmfChainSaves',{})[record['identity']]=clone(record)
    return result


def capture_processors(chain, slot):
    """LV2 SAVE exports actual opaque plugin state, even when its GUI name is stale.

    Fresh names make old snapshots immutable. This never selects a new preset in
    the running processor and never overwrites a musician's existing preset.
    """
    states={};aliases={};assets=[]
    for _,p in members(chain):
        state=clone(p.get_state());engine=p.engine
        if str(p.eng_code).startswith('JV/'):
            if not callable(getattr(engine,'save_preset',None)) or len(getattr(engine,'processors',[]))!=1:
                raise ValueError('Cet instrument/effet ne permet pas une capture LV2 indépendante')
            name=f'MBMF_P{slot:03d}_C{chain.chain_id}_{uuid.uuid4().hex}'
            uri=engine.save_preset(None,name)
            if not isinstance(uri,str) or urlsplit(uri).scheme!='file':raise ValueError('Capture LV2 non confirmée')
            path=Path(unquote(urlsplit(uri).path));boundary=(Path(engine.my_data_dir)/'presets/lv2').resolve()
            if path.is_symlink() or not path.resolve().is_relative_to(boundary) or not path.is_file() or not 0<path.stat().st_size<33554432:
                raise ValueError('Fichier de capture LV2 invalide')
            old=state.get('preset_info');label=old[2] if old else str(p.eng_code).split('/',1)[-1]
            aliases[uri]=old[0] if old else None
            state['bank_info']=None;state['bank_subdir_info']=None
            state['preset_info']=[uri,None,label,None];state['preset_subdir_info']=None
            assets.append(dict(uri=uri,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        elif not state.get('preset_info') and not callable(getattr(engine,'get_extended_config',None)):
            raise ValueError('Cet instrument ne fournit pas d’état rappelable')
        states[str(p.id)]=state
    return states,aliases,assets


class ChainSaves:
    def __init__(self, service):
        self.service=service;self.cache_key=None;self.cache={}

    def baseline(self,slot):
        link=self.service.settings['links'].get(str(slot))
        if not link:raise ValueError('Lier un snapshot au patch avant SAVE CHAÎNE')
        path=self.service.snapshot_path(link['snapshot'])
        return path,self.service.validate_snapshot(path)

    def inventory(self):
        service=self.service;manager=getattr(service.manager,'chain_manager',None)
        if manager is None:return []
        entry=service.one_entry();links=entry['host_chains'].links
        destinations=links.destinations();slot=service.selected
        link=service.settings['links'].get(str(slot));references={}
        if link:
            try:
                path=service.snapshot_path(link['snapshot']);stat=path.stat();key=(str(path),stat.st_mtime_ns,stat.st_size)
                if key!=self.cache_key:
                    document=service.validate_snapshot(path)
                    self.cache={v['identity']:saved_summary(document,v['identity']) for v in destinations};self.cache_key=key
                references=self.cache
            except (OSError,ValueError,KeyError) as error:raise ValueError(str(error)) from error
        rows=[];state=entry['control'].observation() if hasattr(entry['control'],'observation') else entry['control'].request()
        from zynthian_chains import at_rest
        for destination in destinations:
            chain=manager.chains.get(destination['chainId'])
            if chain is None:continue
            try:
                ref=references.get(destination['identity']);record=(ref or {}).get('record') or {}
                observed=fingerprint(chain,links,record.get('aliases'))
                mark='modified' if record and observed!=record.get('fingerprint') else 'saved' if record else 'reference' if ref else 'unlinked'
                public_ref={k:v for k,v in ref.items() if k!='record'} if ref else None
                rows.append(dict(chainId=chain.chain_id,identity=destination['identity'],channel=destination['channel'],
                                 current=summary(chain),reference=public_ref,fingerprint=observed,state=mark,
                                 canSave=ref is not None and at_rest(state),engineSessionId=state['engineSessionId']))
            except (ValueError,TypeError,AttributeError,RuntimeError):
                rows.append(dict(chainId=chain.chain_id,current=[],state='unsupported',canSave=False))
        return rows

    def save(self,request):
        from zynthian_chains import at_rest
        service=self.service;slot=request['slot'];entry=service.one_entry();links=entry['host_chains'].links
        state=entry['control'].request()
        if not at_rest(state):raise ValueError('Arrêter MBMF et relâcher les notes avant SAVE CHAÎNE')
        if state['engineSessionId']!=request['expectedEngineSessionId']:raise ValueError('Le moteur a redémarré ; actualiser')
        chain=service.manager.chain_manager.chains.get(request['chainId'])
        if chain is None or getattr(chain,'_mbmf_instrument_identity',None)!=request['identity']:raise ValueError('La chaîne a changé ; actualiser')
        path,_=self.baseline(slot);previous=path.read_bytes();document=json.loads(previous);cid=snapshot_chain(document,request['identity'])
        if cid!=str(chain.chain_id):raise ValueError('Identité de chaîne déplacée : actualiser le snapshot complet')
        reference=saved_summary(document,request['identity']);old_record=(reference or {}).get('record') or {}
        before=fingerprint(chain,links,old_record.get('aliases'))
        if before!=request['fingerprint']:raise ValueError('Réglages modifiés depuis l’affichage ; réessayer SAVE')
        processors,aliases,assets=capture_processors(chain,slot)
        if before!=fingerprint(chain,links,old_record.get('aliases')):raise ValueError('Réglages modifiés pendant SAVE ; réessayer')
        # Fold older managed aliases into their original source identity.
        aliases={uri:old_record.get('aliases',{}).get(source,source) for uri,source in aliases.items()}
        live_uris={p.preset_info[0] for _,p in members(chain) if getattr(p,'preset_info',None)}
        aliases={**{uri:value for uri,value in old_record.get('aliases',{}).items() if uri in live_uris},**aliases}
        record=dict(identity=request['identity'],fingerprint=before,aliases=aliases,assets=assets,savedAt=time.time(),processors=summary(chain))
        mixer=None;mix=getattr(service.manager,'zynmixer',None);index=getattr(chain,'mixer_chan',None)
        if mix is not None and type(index) is int:
            mixer=mix.get_state().get(f'chan_{index:02d}')
        extended={};selected_engines={id(p.engine):p.engine for _,p in members(chain)}
        selected_ids={p.id for _,p in members(chain)}
        for key,engine in service.manager.chain_manager.zyngines.items():
            if id(engine) in selected_engines:
                value=engine.get_extended_config()
                if value and any(p.id not in selected_ids for p in engine.processors):raise ValueError('État moteur partagé entre chaînes : SAVE indépendant impossible')
                if value:extended[key]=value
        updated=scoped_update(document,cid,chain.get_state(),processors,record,mixer,extended)
        if path.read_bytes()!=previous:raise ValueError('Snapshot modifié pendant SAVE ; réessayer')
        if links.manager.chains.get(chain.chain_id) is not chain or getattr(chain,'_mbmf_instrument_identity',None)!=request['identity']:
            raise ValueError('La chaîne a été remplacée pendant SAVE')
        backups=service.directory/'chain-save-backups';backups.mkdir(exist_ok=True)
        backup=backups/(uuid.uuid4().hex+'.zss');backup.write_bytes(previous)
        from project_sync import atomic_json
        atomic_json(path,updated);self.cache_key=None
