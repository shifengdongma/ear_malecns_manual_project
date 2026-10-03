"""Local-only experiment UI. Serialized Brian2 jobs; all persistent files on H."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import uuid

from .paths import configure_storage
from .signal_workbench import Engine
from .provenance import write_json, verify_manifest
from .fem_io import read_fem_h5


def main(argv=None):
    root=configure_storage()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--prepare',action='store_true',help='Run reference cases without starting the HTTP service')
    args=parser.parse_args(argv)
    engine=Engine(root)
    template=(Path(__file__).parent/'workbench_template.html').read_text(encoding='utf-8')
    cache_file=engine.directory/'case_library.json'
    if args.prepare:
        cases=[]
        for label,params in [('250 Hz tone',{}),('150 Hz tone',{'frequency_hz':150}),
                             ('Pulse IPI 15 ms',{'kind':'pulse','ipi_ms':15}),
                             ('Pulse IPI 36 ms',{'kind':'pulse','ipi_ms':36}),
                             ('Pulse IPI 72 ms',{'kind':'pulse','ipi_ms':72}),
                             ('Silence + 5 Hz spontaneous sensory drive',{'amplitude_pa':0})]:
            print('Running:',label,flush=True)
            data=engine.run(params)
            cases.append(dict(id=data['id'],label=label,parameters=data['parameters'],spikes=data['network_spikes'],hops=data['hops']))
            print(f'Completed {label}: {data["network_spikes"]} spikes',flush=True)
        write_json(cache_file,{'cases':cases})
        return 0
    # Brian2 installs its SIGINT handler during first import, which must be on the main thread.
    import brian2
    token=secrets.token_urlsafe(32)
    jobs={}
    lock=threading.Lock()
    worker=ThreadPoolExecutor(max_workers=1) # Brian2 global clocks/scopes cannot run concurrently.
    def experiment(identifier):
        if not identifier or any(c not in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-' for c in identifier):
            raise ValueError('Invalid experiment ID')
        folder=engine.directory/'experiments'/identifier
        verify_manifest(folder)
        return json.loads((folder/'experiment.json').read_text(encoding='utf-8'))
    def execute(identifier,params):
        with lock:jobs[identifier]={'state':'running'}
        try:
            data=engine.run(params)
            with lock:jobs[identifier]={'state':'complete','experiment':data['id']}
        except Exception as error:
            with lock:jobs[identifier]={'state':'failed','message':str(error)}
            print('Experiment failed:',error,flush=True)
    class Handler(BaseHTTPRequestHandler):
        def send(self,payload,kind='application/json; charset=utf-8',status=200,filename=None):
            if not isinstance(payload,bytes):
                payload=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8') if kind.startswith('application/json') else payload.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            if len(payload)>4096 and 'gzip' in self.headers.get('Accept-Encoding',''):
                payload=gzip.compress(payload,compresslevel=3)
                self.send_header('Content-Encoding','gzip')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers();self.wfile.write(payload)
        def valid_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{args.port}'
        def do_GET(self):
            if not self.valid_host():return self.send({'error':'Use the 127.0.0.1 URL'},status=403)
            try:
                path=self.path.split('?',1)[0]
                if path=='/':return self.send(template,'text/html; charset=utf-8')
                if path=='/api/bootstrap':
                    cases=json.loads(cache_file.read_text())['cases'] if cache_file.exists() else []
                    return self.send({**engine.assets,'token':token,'cases':cases})
                if path.startswith('/api/job/'):
                    with lock:copy_state=jobs.get(path.rsplit('/',1)[-1],{'state':'unknown'})
                    return self.send(copy_state)
                if path.startswith('/api/experiment/'):
                    return self.send(experiment(path.rsplit('/',1)[-1]))
                if path.startswith('/api/export/'):
                    data=experiment(path.rsplit('/',1)[-1])
                    exported=template.replace('<!--OFFLINE_DATA-->',
                        '<script>window.WORKBENCH_OFFLINE='+json.dumps({'bootstrap':engine.assets,'experiment':data},ensure_ascii=False).replace('<','\\u003c')+';</script>')
                    folder=engine.directory/'experiments'/data['id']
                    (folder/'visual_report.html').write_text(exported,encoding='utf-8')
                    return self.send(exported,'text/html; charset=utf-8',filename='signal_visual_report.html')
                return self.send({'error':'Not found'},status=404)
            except (ValueError,OSError,KeyError) as error:return self.send({'error':str(error)},status=400)
        def do_POST(self):
            origin=self.headers.get('Origin')
            if not self.valid_host() or self.headers.get('X-Workbench-Token')!=token or origin not in [None,f'http://127.0.0.1:{args.port}']:
                return self.send({'error':'Local workbench token/origin required'},status=403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=30*1024*1024:raise ValueError('Request must be at most 30 MB')
                payload=json.loads(self.rfile.read(length))
                if self.path=='/api/run':
                    from .signal_workbench import parameters
                    values=parameters(payload)
                    with lock:
                        if any(j['state'] in ['queued','running'] for j in jobs.values()):
                            return self.send({'error':'A simulation is already running; wait for completion'},status=409)
                        identifier=uuid.uuid4().hex;jobs[identifier]={'state':'queued'}
                    worker.submit(execute,identifier,values)
                    return self.send({'job':identifier},status=202)
                if self.path=='/api/import-fem':
                    binary=base64.b64decode(payload['hdf5'],validate=True)
                    calibration=payload['calibration']
                    import numpy as np
                    if len(binary)>20*1024*1024 or not np.isfinite([calibration['q_low'],calibration['q_high']]).all() or calibration['q_high']<=calibration['q_low'] or calibration['envelope_tau_ms']!=5:
                        raise ValueError('FEM needs <=20 MB HDF5 and valid frozen 5 ms envelope calibration')
                    identifier=uuid.uuid4().hex;folder=engine.directory/'imports'/identifier;folder.mkdir(parents=True)
                    (folder/'response.h5').write_bytes(binary)
                    import h5py
                    with h5py.File(folder/'response.h5','r') as f:
                        for name in ['stimulus/time_s','stimulus/pressure_Pa','fem/tm_displacement_m','fem/stapes_velocity_m_s']:
                            if f[name].ndim!=1 or f[name].size>100000:raise ValueError('FEM arrays must be 1D, at most 100000 samples')
                    data=read_fem_h5(folder/'response.h5')
                    duration=len(data['time_s'])/data['sample_rate_hz']
                    if not .4<=duration<=2:raise ValueError('FEM duration must be 0.4–2 s')
                    write_json(folder/'calibration.json',calibration)
                    return self.send({'fem_id':identifier,'version':data['fem_version'],'duration_s':duration})
                return self.send({'error':'Not found'},status=404)
            except (ValueError,TypeError,KeyError,OSError) as error:return self.send({'error':str(error)},status=400)
        def log_message(self,fmt,*values):
            if not self.path.startswith('/api/job/'):
                print(fmt % values,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    write_json(engine.directory/'server.json',{'url':f'http://127.0.0.1:{args.port}','storage':str(engine.directory),'pid':os.getpid()})
    print(f'Workbench ready: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();worker.shutdown(wait=True)
    return 0
