"""Exercise import and structural controls against the actual local service."""
import _bootstrap
from pathlib import Path
import json, base64, time
import requests
from ear_malecns.paths import configure_storage
from ear_malecns.provenance import write_json
root=configure_storage();folder=root/'outputs/workbench';url='http://127.0.0.1:8765'
s=requests.Session();s.trust_env=False
b=s.get(url+'/api/bootstrap',timeout=30).json()
headers={'X-Workbench-Token':b['token']}
assert s.post(url+'/api/run',json={},timeout=10).status_code==403
assert s.post(url+'/api/run',json={'delay_ms':0},headers=headers,timeout=10).status_code==400
first=s.get(url+'/api/experiment/'+b['cases'][0]['id'],timeout=30).json()
original=Path(first['output'])
cal=json.loads((original/'calibration.json').read_text(encoding='utf-8'))
r=s.post(url+'/api/import-fem',json={'hdf5':base64.b64encode((original/'mechanical.h5').read_bytes()).decode(),'calibration':cal},headers=headers,timeout=30)
r.raise_for_status();fem=r.json()['fem_id']
results=[]
def run(label,p):
    r=s.post(url+'/api/run',json=p,headers=headers,timeout=30);r.raise_for_status();job=r.json()['job'];deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        state=s.get(url+'/api/job/'+job,timeout=30).json()
        if state['state']=='failed':raise RuntimeError(state['message'])
        if state['state']=='complete':break
        time.sleep(.3)
    else:raise TimeoutError('Brian2 job timeout')
    d=s.get(url+'/api/experiment/'+state['experiment'],timeout=30).json()
    results.append({'label':label,'id':d['id'],'spikes':d['network_spikes'],'hops':d['hops'],'input_sha256':d['input_sha256'],'parameters':d['parameters']})
    print(label,d['network_spikes'],[h['active_neurons'] for h in d['hops']],flush=True)
    return d
imported=run('Imported response round trip (synthetic fixture)',{'mechanical':'imported','fem_id':fem})
assert imported['network_spikes']==first['network_spikes'] and imported['input_sha256']==first['input_sha256']
control=run('Same stimulus, shuffled weights',{'topology':'weight_shuffled'})
assert control['input_sha256']==first['input_sha256']
gain=run('Same stimulus, assumed w0=2 mV',{'w0_mv':2})
assert gain['input_sha256']==first['input_sha256']
library=json.loads((folder/'case_library.json').read_text(encoding='utf-8'))
for d in [control,gain]:
    if not any(c['parameters']==d['parameters'] for c in library['cases']):
        library['cases'].append(dict(id=d['id'],label='Weight shuffled' if d['parameters']['topology']=='weight_shuffled' else 'Assumed w0=2 mV',parameters=d['parameters'],spikes=d['network_spikes'],hops=d['hops']))
write_json(folder/'case_library.json',library)
write_json(folder/'http_qa.json',dict(auth_rejected=True,invalid_rejected=True,import_identity_verified=True,same_input_control_verified=True,results=results))

