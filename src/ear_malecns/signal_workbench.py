"""Auditable acoustic experiments with all-cell voltages and delayed synaptic events."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import struct
import uuid

import numpy as np
import pandas as pd
from scipy.signal import hilbert, chirp
from scipy.ndimage import gaussian_filter1d

from .config import load_config
from .fem_io import synthetic_transfer_response, write_fem_h5, read_fem_h5
from .encoder import equivalent_particle_velocity_mm_s
from .pipeline import encode_events, control_snapshot
from .provenance import sha256, verify_manifest, write_json, manifest
from .stimulus import gated_tone, pulse_song_like
from .brain_report import segments_from_swc

DEFAULTS = dict(kind='tone', frequency_hz=250., amplitude_pa=1., ipi_ms=36., modulation_hz=20.,
                w0_mv=1., input_weight_mv=6., delay_ms=1.5, tau_m_ms=20., encoder_gain=1.,
                seed=42, topology='original', mechanical='demo')


def parameters(values):
    unknown = set(values) - set(DEFAULTS) - {'waveform', 'fem_id', 'rms_match_pa', 'topology_seed'}
    if unknown:
        raise ValueError(f'Unknown parameters: {sorted(unknown)}')
    p = {**DEFAULTS, **values}
    for name, low, high in [('frequency_hz', 50, 500), ('amplitude_pa', 0, 4), ('ipi_ms', 10, 100),
                           ('modulation_hz', 1, 100), ('w0_mv', 0, 2), ('input_weight_mv', 0, 12),
                           ('delay_ms', .1, 5), ('tau_m_ms', 5, 40), ('encoder_gain', .1, 4)]:
        value = float(p[name])
        if not np.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{name} must be in [{low}, {high}]')
        p[name] = value
    if float(p['seed']) != int(p['seed']) or not 0 <= int(p['seed']) <= 2**32-1:
        raise ValueError('Invalid random seed')
    p['seed'] = int(p['seed'])
    if p['kind'] not in ['tone', 'pulse', 'am', 'chirp', 'noise', 'wav'] or p['mechanical'] not in ['demo', 'direct', 'imported'] or p['topology'] not in ['original', 'rewired', 'weight_shuffled']:
        raise ValueError('Invalid experiment mode')
    if p['kind'] == 'wav' and p['mechanical'] != 'imported':
        wave = np.asarray(p.get('waveform'), dtype=float)
        if wave.ndim != 1 or len(wave) != 10000 or not np.isfinite(wave).all() or (np.abs(wave) > 1).any():
            raise ValueError('WAV input must be 10000 finite mono PCM samples in [-1,1]')
    if p.get('rms_match_pa') is not None:
        rms=float(p['rms_match_pa'])
        if not np.isfinite(rms) or not 0 < rms <= 2:
            raise ValueError('rms_match_pa must be finite in (0,2]')
        if p['mechanical']=='imported':
            raise ValueError('Imported mechanical responses cannot be RMS-rescaled independently')
        p['rms_match_pa']=rms
    ts=p.get('topology_seed',p['seed'])
    if float(ts)!=int(ts) or not 0<=int(ts)<=2**32-1:
        raise ValueError('Invalid topology seed')
    p['topology_seed']=int(ts)
    return p


def _source_wave(p):
    fs = 10000.
    t = np.arange(10000) / fs
    gate = (t >= .2) & (t < .8)
    f, amplitude = p['frequency_hz'], p['amplitude_pa']
    if p['kind'] == 'tone':
        return gated_tone(f, fs, 1., amplitude, .2, .8)
    if p['kind'] == 'pulse':
        _, pressure = pulse_song_like(f, p['ipi_ms'], fs, 1., amplitude=amplitude, start_s=.2)
    elif p['kind'] == 'am':
        pressure = amplitude * (.5 + .5 * np.sin(2*np.pi*p['modulation_hz']*t)) * np.sin(2*np.pi*f*t)
    elif p['kind'] == 'chirp':
        pressure = amplitude * chirp(t, f0=100, f1=400, t1=1.)
    elif p['kind'] == 'noise':
        pressure = amplitude * np.random.default_rng(p['seed']).normal(0, .3, len(t))
    else:
        # PCM-to-Pa scale is explicit; do not normalize each uploaded clip.
        return t, np.asarray(p['waveform']) * amplitude
    return t, pressure * gate


def source_wave(p):
    t,pressure=_source_wave(p)
    if p.get('rms_match_pa') is not None:
        active=(t>=.2)&(t<.8)
        rms=float(np.sqrt(np.mean(pressure[active]**2)))
        if rms<=0:
            raise ValueError('Cannot RMS-match a silent stimulus')
        pressure=pressure*(p['rms_match_pa']/rms)
    return t,pressure


def mechanical_data(p):
    t, pressure = source_wave(p)
    if p['mechanical'] == 'direct':
        # Dimensionless baseline stored in the common software adapter only.
        # These arrays are explicitly not physical stapes velocity/TM displacement.
        tm, velocity = np.zeros_like(pressure), pressure.copy()
        version = 'ACOUSTIC_DIRECT_BASELINE_NOT_EAR_FEM'
    else:
        tm, velocity = synthetic_transfer_response(pressure, 10000.)
        version = 'SYNTHETIC_REFERENCE_TRANSFER_NOT_OPENEAR_FEM'
    return dict(time_s=t, pressure_pa=pressure, tm_displacement_m=tm,
                stapes_velocity_m_s=velocity, sample_rate_hz=10000., fem_version=version)


def fit_reference_calibration(mechanical):
    """A fixed pooled reference set, never fit separately to a user test clip."""
    logs = []
    for kind in ['tone', 'pulse']:
        for amplitude in [.1, .25, 1., 2.]:
            d = mechanical_data({**DEFAULTS, 'kind': kind, 'amplitude_pa': amplitude, 'mechanical': mechanical})
            env = gaussian_filter1d(np.abs(hilbert(d['stapes_velocity_m_s'])), 50)
            logs.append(np.log(env+1e-15))
    lo, hi = np.quantile(np.concatenate(logs), [.05, .95])
    return dict(q_low=float(lo), q_high=float(hi), envelope_tau_ms=5.,
                source='Frozen synthetic reference set; not physiology fitting',
                amplitudes_pa=[.1, .25, 1., 2.], kinds=['tone', 'pulse'], mechanical=mechanical)


def ply_surface(path):
    """Read official simple OpenEar binary triangle PLY; no conversion install."""
    with path.open('rb') as stream:
        header=[]
        while True:
            line=stream.readline().decode('ascii').strip()
            header.append(line)
            if line=='end_header':
                break
        if 'format binary_little_endian 1.0' not in header:
            raise ValueError('Expected official OpenEar little-endian PLY')
        n=int(next(l.split()[-1] for l in header if l.startswith('element vertex')))
        nf=int(next(l.split()[-1] for l in header if l.startswith('element face')))
        start=header.index(f'element vertex {n}')+1
        stop=next(i for i in range(start,len(header)) if header[i].startswith('element '))
        types={'float':'<f4','double':'<f8','uchar':'u1','uint8':'u1','int':'<i4'}
        fields=[(l.split()[-1],types[l.split()[1]]) for l in header[start:stop] if l.startswith('property ')]
        dtype=np.dtype(fields)
        rows=np.frombuffer(stream.read(n*dtype.itemsize),dtype=dtype)
        vertices=np.column_stack([rows[k] for k in ['x','y','z']])
        edges=set()
        for _ in range(nf):
            count=struct.unpack('<B',stream.read(1))[0]
            face=struct.unpack('<'+'i'*count,stream.read(4*count))
            for a,b in zip(face,face[1:]+face[:1]):
                edges.add(tuple(sorted([a,b])))
    return dict(name=path.stem.split('_',1)[-1], vertices=np.round(vertices,4).tolist(),
                edges=[list(e) for e in sorted(edges)[::3]], sha256=sha256(path))


def analysis_window(duration):
    """A positive stimulus window is required for rates and latency statistics."""
    if not np.isfinite(duration) or not .4 < duration <= 2:
        raise ValueError('Workbench requires duration >0.4 and <=2 s for a nonempty analysis window')
    return .2,duration-.2


class Engine:
    def __init__(self, root, *, load_assets=True):
        self.root=root
        self.snapshot=root/'data/processed/malecns_snapshots/real_public_fixed_20261003'
        self.graph_meta=verify_manifest(self.snapshot)
        if self.graph_meta['source']!='PUBLIC_MALECNS_V1_0':
            raise ValueError('Workbench requires the verified real MaleCNS snapshot')
        self.nodes=pd.read_parquet(self.snapshot/'nodes.parquet').sort_values('bodyId').reset_index(drop=True)
        self.edges=pd.read_parquet(self.snapshot/'edges.parquet')
        self.ids=self.nodes.bodyId.astype(int).tolist()
        self.index={body:i for i,body in enumerate(self.ids)}
        self.seed_ids=sorted(pd.read_csv(self.snapshot/'auditory_input_cells.csv').bodyId.astype(int))
        self.cfg=load_config(root/'configs/pipeline_real_demo.yaml')
        self.directory=root/'outputs/workbench'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.calibrations={m:fit_reference_calibration(m) for m in ['demo','direct']}
        for m,c in self.calibrations.items():
            write_json(self.directory/f'calibration_{m}.json',c)
        self.assets=self.bootstrap() if load_assets else None

    def bootstrap(self):
        cells=[]
        positions={}
        for hop,group in self.nodes.groupby('hop'):
            for j,body in enumerate(group.bodyId):
                positions[int(body)]=[.12+.38*int(hop),.06+.88*(j+.5)/len(group)]
        for row in self.nodes.to_dict('records'):
            nt=row.get('consensusNt','unknown')
            cells.append(dict(id=str(row['bodyId']),type=str(row['type']),hop=int(row['hop']),
                nt='unknown' if pd.isna(nt) else str(nt),pos=positions[int(row['bodyId'])],seed=bool(row['is_seed'])))
        skeletons=[]
        folder=self.root/'skeletons/male-cns-v1.0/all_auditory'
        if not (folder/'manifest.json').exists():
            folder=self.root/'skeletons/male-cns-v1.0/activity_representative'
        smeta=verify_manifest(folder)
        for name in smeta['files']:
            body=int(Path(name).stem)
            if body in self.index:
                seg,total=segments_from_swc(folder/name,cap=300)
                skeletons.append(dict(node=self.index[body],segments=seg.tolist(),full_segments=total))
        surfaces=[]
        for name in ['03_Malleus.ply','04_Incus.ply','05_Stapes.ply','09_Tympanic Membrane.ply']:
            path=self.root/'fem/geometry/openear_zeta'/name
            if path.exists():
                surfaces.append(ply_surface(path))
        return dict(nodes=cells,skeletons=skeletons,ear=surfaces,defaults=DEFAULTS,
                    dataset='male-cns:v1.0',edge_count=len(self.edges),seed_count=len(self.seed_ids),
                    calibration=self.calibrations,storage=str(self.directory),
                    limitations=['Real connectome and geometry; assumed encoder/LIF dynamics.',
                    'OpenEar supplies geometry, not a solved mechanical FEM.',
                    'Envelope M1 does not assign physiology-fitted carrier tuning to JO subtypes.'])

    def run(self, supplied):
        p=parameters(supplied)
        cfg=copy.deepcopy(self.cfg)
        cfg['project']['seed']=p['seed']
        cfg['encoder']['gain']=p['encoder_gain']
        for key in ['w0_mv','input_weight_mv','delay_ms','tau_m_ms']:
            cfg['snn'][key]=p[key]
        cfg['snn']['delay_ms']=round(p['delay_ms']/.1)*.1
        run_id=datetime.now(timezone.utc).strftime('signal_%Y%m%dT%H%M%S_')+uuid.uuid4().hex[:8]
        out=self.directory/'experiments'/run_id
        out.mkdir(parents=True,exist_ok=False)
        if p['mechanical']=='imported':
            fem_id=p.get('fem_id','')
            if not isinstance(fem_id,str) or len(fem_id)!=32 or any(c not in '0123456789abcdef' for c in fem_id):
                raise ValueError('Import a FEM HDF5 and shared calibration first')
            d=read_fem_h5(self.directory/'imports'/fem_id/'response.h5')
            calibration=json.loads((self.directory/'imports'/fem_id/'calibration.json').read_text(encoding='utf-8'))
        else:
            d=mechanical_data(p)
            calibration=self.calibrations[p['mechanical']]
        duration=len(d['time_s'])/d['sample_rate_hz']
        onset,offset=analysis_window(duration)
        cfg['snn']['simulation_ms']=duration*1000
        cfg['fixed_input']['onset_s']=onset
        cfg['fixed_input']['offset_s']=offset
        write_fem_h5(out/'mechanical.h5',d['time_s'],d['pressure_pa'],d['tm_displacement_m'],d['stapes_velocity_m_s'],d['sample_rate_hz'],d['fem_version'])
        write_json(out/'calibration.json',calibration)
        channels,times,z,rate=encode_events(d,cfg,calibration,len(self.seed_ids))
        np.savez_compressed(out/'fixed_input.npz',body_ids=self.seed_ids,channels=channels,times_s=times,
                            dt_ms=.1,duration_ms=cfg['snn']['simulation_ms'])
        selected=self.snapshot
        if p['topology']!='original':
            selected=out/'control_snapshot'
            control_snapshot(self.snapshot,selected,p['topology'],p['topology_seed'])
        edges=pd.read_parquet(selected/'edges.parquet')
        spikes,vt,voltage,connections,arrivals=self.simulate(edges,channels,times,cfg)
        from .stage1 import summarize
        from .analysis import first_spike_latency
        neurons,hops=summarize(self.nodes,spikes,cfg)
        spikes.to_parquet(out/'spikes.parquet',index=False)
        neurons.to_csv(out/'neuron_metrics.csv',index=False)
        hops.to_csv(out/'hop_metrics.csv',index=False)
        latency=first_spike_latency(spikes,200,self.ids,(duration-.2)*1000)
        latency.to_csv(out/'latency.csv',index=False)
        np.savez_compressed(out/'voltage.npz',body_ids=self.ids,time_ms=vt,voltage_mv=voltage,
                            sample_dt_ms=.2,monitor_when='end')
        pd.DataFrame(arrivals,columns=['arrival_ms','edge_index']).to_parquet(out/'synaptic_arrivals.parquet',index=False)
        trains=[[] for _ in self.ids]
        for body,t in spikes[['bodyId','time_ms']].itertuples(index=False,name=None):
            trains[self.index[int(body)]].append(round(float(t),3))
        nmetrics=neurons.set_index('bodyId')
        lmap=latency.set_index('bodyId').latency_ms
        stride=max(1,int(np.ceil(len(z)/2500)))
        take=slice(None,None,stride)
        env=gaussian_filter1d(np.abs(hilbert(d['stapes_velocity_m_s'])),d['sample_rate_hz']*.005)
        freq=np.fft.rfftfreq(len(z),1/d['sample_rate_hz'])
        power=np.abs(np.fft.rfft(d['pressure_pa']))**2
        keep=freq<=1000
        features=dict(dominant_hz=float(freq[np.argmax(power)]) if power.max()>0 else 0.,
            peak_pressure_pa=float(np.max(np.abs(d['pressure_pa']))),
            stimulus_rms_pa=float(np.sqrt(np.mean(d['pressure_pa'][(d['time_s']>=.2)&(d['time_s']<.8)]**2))),
            onset_ms=200 if p['kind']!='wav' and p['mechanical']!='imported' else None,
            ipi_ms=p['ipi_ms'] if p['kind']=='pulse' and p['mechanical']!='imported' else None,
            encoder='Envelope/adaptation M1; no fitted carrier-selective JO tuning')
        data=dict(id=run_id,parameters={k:v for k,v in p.items() if k!='waveform'},config=cfg,
            mechanical_source=d['fem_version'],features=features,duration_ms=duration*1000,
            trace=dict(time_ms=np.round(d['time_s'][take]*1000,3).tolist(),pressure_pa=np.round(d['pressure_pa'][take],8).tolist(),
                tm_m=d['tm_displacement_m'][take].tolist(),stapes_m_s=d['stapes_velocity_m_s'][take].tolist(),
                envelope=env[take].tolist(),normalized=np.round(z[take],5).tolist(),rate_hz=np.round(rate[take],4).tolist(),
                equivalent_velocity_mm_s=np.round(equivalent_particle_velocity_mm_s(z[take]),5).tolist(),
                spectrum_hz=freq[keep].tolist(),spectrum_power=power[keep].tolist()),
            input_events=[[round(float(t)*1000,3),int(c)] for c,t in zip(channels,times)],
            spikes=trains,voltage_time_ms=np.round(vt,3).tolist(),voltage_mv=np.round(voltage,3).tolist(),
            edges=connections,arrivals=arrivals,hops=hops.to_dict('records'),
            rates=[round(float(nmetrics.loc[b,'stimulus_rate_hz']),4) for b in self.ids],
            latency_ms=[None if pd.isna(lmap[b]) else round(float(lmap[b]),3) for b in self.ids],
            input_sha256=sha256(out/'fixed_input.npz'),network_spikes=len(spikes),output=str(out),
            interpretation='Presynaptic spike + modeled delay produces signed voltage increment; no measured current or cable propagation.')
        write_json(out/'experiment.json',data)
        write_json(out/'config.json',cfg)
        write_json(out/'manifest.json',manifest([f for f in out.iterdir() if f.is_file()],source='REAL_MALECNS_SIGNAL_WORKBENCH',
            dataset='male-cns:v1.0',graph_manifest_sha256=sha256(selected/'manifest.json'),
            source_code_sha256={str(f.relative_to(self.root)):sha256(f) for f in sorted((self.root/'src').rglob('*.py'))},
            calibration_mode='shared_frozen',mechanical_source=d['fem_version'],voltage_monitor='all cells; 0.2 ms; end of step',
            arrivals='Derived exactly from monitored presynaptic spikes and Brian synaptic delays; not proof of postsynaptic causation'))
        return data

    def simulate(self,edges,channels,times,cfg, *, record_voltage=True):
        from brian2 import Network,StateMonitor,start_scope,defaultclock,prefs,seed,ms,mV
        from .snn import build_lif_network,attach_event_input
        from .analysis import spike_table
        start_scope();prefs.codegen.target='numpy';defaultclock.dt=.1*ms;seed(cfg['project']['seed'])
        params={k:cfg['snn'][k] for k in ['tau_m_ms','e_l_mv','v_th_mv','v_reset_mv','refractory_ms','delay_ms','w0_mv','uncertain_sign']}
        nt=self.nodes.set_index('bodyId').consensusNt.dropna().to_dict()
        group,syn,monitor,old_voltage,to_idx,to_body=build_lif_network(self.nodes,edges,nt_map=nt,**params)
        old_voltage.active=False
        voltage=StateMonitor(group,'v',record=True,dt=.2*ms,when='end') if record_voltage else None
        source,drive=attach_event_input(group,to_idx,self.seed_ids,channels,times,cfg['snn']['input_weight_mv'])
        objects=[group,syn,monitor,old_voltage,source,drive]
        if voltage is not None:objects.append(voltage)
        net=Network(*objects)
        net.run(cfg['snn']['simulation_ms']*ms)
        spikes=spike_table(monitor,to_body)
        connections=[[int(a),int(b),round(float(w),8),round(float(delay),6)] for a,b,w,delay in
                     zip(syn.i[:],syn.j[:],syn.w[:]/mV,syn.delay[:]/ms)]
        recorded_trains=monitor.spike_trains()
        trains={int(i):np.asarray(recorded_trains[i]/ms) for i in range(len(self.ids))}
        arrivals=[]
        for ei,(a,b,w,delay) in enumerate(connections):
            arrivals.extend([round(float(t+delay),3),ei] for t in trains[a] if t+delay<cfg['snn']['simulation_ms'])
        arrivals.sort(key=lambda a:(a[0],a[1]))
        vt=np.asarray(voltage.t/ms) if voltage is not None else np.empty(0)
        vv=np.asarray(voltage.v/mV) if voltage is not None else np.empty((len(self.ids),0))
        return spikes,vt,vv,connections,arrivals
