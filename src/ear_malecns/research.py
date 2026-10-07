"""Paired stochastic trials of a verified connectome; exploratory model evidence."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import re
import numpy as np
import pandas as pd
from .signal_workbench import Engine, parameters, mechanical_data
from .pipeline import encode_events, control_snapshot
from .provenance import write_json, manifest, sha256
from .paths import configure_storage
from .fem_io import write_fem_h5

METRICS=['network_spikes','downstream_stimulus_spikes','hop1_active_fraction','hop2_active_fraction','downstream_spikes_per_input_event']

def event_digest(channels,times):
    c=np.asarray(channels,dtype='<i8');t=np.asarray(times,dtype='<f8')
    return hashlib.sha256(c.tobytes()+t.tobytes()).hexdigest()

def shuffle_stimulus_times(channels,times,seed,dt=.0001):
    """Preserve per-channel counts and outside-window events; sample without collisions."""
    channels=np.asarray(channels).copy();times=np.asarray(times).copy()
    rng=np.random.default_rng(seed);bins=np.arange(round(.2/dt),round(.8/dt))
    for ch in np.unique(channels):
        mask=(channels==ch)&(times>=.2)&(times<.8)
        times[mask]=rng.choice(bins,size=int(mask.sum()),replace=False)*dt
    order=np.lexsort((channels,times))
    return channels[order],times[order]

def interval(values,seed=20261007):
    values=np.asarray(values,dtype=float)
    if len(values)<2 or not np.isfinite(values).all():
        raise ValueError('Intervals require at least two finite independent trial values')
    rng=np.random.default_rng(seed)
    means=rng.choice(values,size=(10000,len(values)),replace=True).mean(axis=1)
    low,high=np.quantile(means,[.025,.975])
    return {'n':len(values),'mean':float(values.mean()),'sd':float(values.std(ddof=1)),
            'ci95_low':float(low),'ci95_high':float(high)}

def summarize_trials(trials):
    rows=[]
    for name,g in trials.groupby('condition',sort=False):
        for metric in METRICS:
            rows.append(dict(condition=name,metric=metric,**interval(g[metric])))
    return pd.DataFrame(rows)

def paired_difference(trials,a,b,metric):
    left=trials[trials.condition==a].set_index('trial_seed')
    right=trials[trials.condition==b].set_index('trial_seed')
    if left.index.duplicated().any() or right.index.duplicated().any() or set(left.index)!=set(right.index):
        raise ValueError('Paired comparison requires one result per identical trial seed')
    idx=sorted(left.index);delta=left.loc[idx,metric].to_numpy()-right.loc[idx,metric].to_numpy()
    return dict(condition=a,reference=b,metric=metric,**interval(delta))

def trial_metrics(engine,spikes,channels,times):
    active=spikes[(spikes.time_ms>=200)&(spikes.time_ms<800)]
    hop=engine.nodes.set_index('bodyId').hop.to_dict()
    downstream=active[active.bodyId.map(hop)>0]
    n_input=int(((times>=.2)&(times<.8)).sum())
    latency=downstream.groupby('bodyId').time_ms.min()-200
    return dict(network_spikes=len(spikes),input_stimulus_events=n_input,
        downstream_stimulus_spikes=len(downstream),
        hop1_active_fraction=float(active.loc[active.bodyId.map(hop)==1,'bodyId'].nunique()/sum(engine.nodes.hop==1)),
        hop2_active_fraction=float(active.loc[active.bodyId.map(hop)==2,'bodyId'].nunique()/sum(engine.nodes.hop==2)),
        downstream_spikes_per_input_event=float(len(downstream)/n_input) if n_input else 0.,
        responsive_downstream_cells=downstream.bodyId.nunique(),
        conditional_median_first_spike_ms=None if latency.empty else float(latency.median()))

def run_protocol(root,plan,progress=print):
    seeds=plan['trial_seeds']
    if len(seeds)<2 or len(set(seeds))!=len(seeds) or any(isinstance(s,bool) or not isinstance(s,int) or not 0<=s<2**32 for s in seeds):
        raise ValueError('Protocol needs at least two distinct integer trial seeds')
    conditions=plan['conditions'];names=[c['name'] for c in conditions]
    if len(set(names))!=len(names) or any(not re.fullmatch('[a-z0-9_]+',n) for n in names):
        raise ValueError('Condition names must be unique lowercase identifiers')
    engine=Engine(root,load_assets=False)
    out=root/'outputs/research'/datetime.now(timezone.utc).strftime('research_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True,exist_ok=False);write_json(out/'protocol.json',plan)
    engine.calibrations['demo']=copy.deepcopy(engine.calibrations['demo'])
    write_json(out/'calibration.json',engine.calibrations['demo'])
    rows=[];snapshots={};frozen={};sources={}
    for trial_seed in seeds:
        for condition in conditions:
            name=condition['name'];cfg=copy.deepcopy(engine.cfg);cfg['project']['seed']=trial_seed
            supplied={**condition.get('parameters',{}),'seed':trial_seed}
            p=parameters(supplied)
            if p['mechanical']!='demo' or p['kind']=='wav':raise ValueError('This protocol supports explicit generated demo stimuli only')
            cfg['encoder']['gain']=p['encoder_gain']
            for k in ['w0_mv','input_weight_mv','tau_m_ms','delay_ms']:cfg['snn'][k]=p[k]
            cfg['snn']['delay_ms']=round(cfg['snn']['delay_ms']/.1)*.1
            d=mechanical_data(p)
            key=(trial_seed,p['kind'],p['frequency_hz'],p['amplitude_pa'],p['ipi_ms'],p.get('rms_match_pa'),p['encoder_gain'])
            if key not in frozen:
                frozen[key]=encode_events(d,cfg,engine.calibrations['demo'],len(engine.seed_ids))[:2]
            channels,times=[x.copy() for x in frozen[key]]
            null=condition.get('input_control','none')
            if null=='shuffle_time':channels,times=shuffle_stimulus_times(channels,times,trial_seed+200000)
            elif null=='zero_input':channels=np.empty(0,dtype=int);times=np.empty(0)
            elif null!='none':raise ValueError('Unknown input control')
            edges=engine.edges.copy();topology=condition.get('topology_control','original');topology_seed=100000+trial_seed
            if topology in ['rewired','weight_shuffled']:
                skey=(topology,topology_seed)
                if skey not in snapshots:
                    snap=out/'controls'/f'{topology}_{topology_seed}'
                    control_snapshot(engine.snapshot,snap,topology,topology_seed)
                    snapshots[skey]=snap
                edges=pd.read_parquet(snapshots[skey]/'edges.parquet')
            elif topology=='jo_only':
                edges=edges[edges.bodyId_pre.isin(engine.seed_ids)&~edges.bodyId_post.isin(engine.seed_ids)].copy()
            elif topology!='original':raise ValueError('Unknown topology control')
            trial=out/'trials'/f'{name}_{trial_seed}';trial.mkdir(parents=True)
            np.savez_compressed(trial/'input.npz',body_ids=engine.seed_ids,channels=channels,times_s=times,dt_ms=.1,duration_ms=1000)
            source_key=(p['kind'],p['frequency_hz'],p['ipi_ms'],p['amplitude_pa'],p.get('rms_match_pa'))
            if source_key not in sources:
                source=out/'stimuli'/f'source_{len(sources):02d}.h5'
                write_fem_h5(source,**dict(time_s=d['time_s'],pressure_pa=d['pressure_pa'],tm_displacement_m=d['tm_displacement_m'],stapes_velocity_m_s=d['stapes_velocity_m_s'],sample_rate_hz=d['sample_rate_hz'],fem_version=d['fem_version']))
                sources[source_key]=source
            spikes,_,_,_,_=engine.simulate(edges,channels,times,cfg,record_voltage=False)
            spikes.to_parquet(trial/'spikes.parquet',index=False)
            rms=float(np.sqrt(np.mean(d['pressure_pa'][(d['time_s']>=.2)&(d['time_s']<.8)]**2)))
            record=dict(condition=name,label=condition['label'],trial_seed=trial_seed,topology_seed=topology_seed,
                input_sha256=event_digest(channels,times),stimulus_rms_pa=rms,source_sha256=sha256(sources[source_key]),
                structural_edges=len(edges),**trial_metrics(engine,spikes,channels,times))
            write_json(trial/'metrics.json',record);write_json(trial/'config.json',cfg)
            write_json(trial/'manifest.json',manifest(list(trial.iterdir()),source='REAL_MALECNS_MODEL_TRIAL'))
            rows.append(record);progress(f'{len(rows)}/{len(seeds)*len(conditions)} {name} seed={trial_seed}: {record["network_spikes"]} spikes')
            # Partial table makes completed trials inspectable if the batch is interrupted.
            pd.DataFrame(rows).to_csv(out/'trials.csv',index=False)
    trials=pd.DataFrame(rows)
    for pair in plan['same_input_pairs']:
        for s in seeds:
            a=trials[(trials.condition==pair[0])&(trials.trial_seed==s)].iloc[0]
            b=trials[(trials.condition==pair[1])&(trials.trial_seed==s)].iloc[0]
            if a.input_sha256!=b.input_sha256:raise ValueError('Nonidentical input in a paired structural/gain control')
    if 'zero_input' in names and trials.loc[trials.condition=='zero_input','network_spikes'].any():raise ValueError('Zero-input stability failed')
    summary=summarize_trials(trials);summary.to_csv(out/'summary.csv',index=False)
    comparisons=pd.DataFrame([paired_difference(trials,pair[0],pair[1],metric) for pair in plan['comparisons'] for metric in METRICS])
    comparisons.to_csv(out/'paired_effects.csv',index=False)
    data=dict(protocol=plan,trials=rows,summary=summary.to_dict('records'),paired_effects=comparisons.to_dict('records'),
        output=str(out),dataset='male-cns:v1.0',cells=len(engine.ids),edges=len(engine.edges),
        method='10,000 percentile bootstrap samples of trial means and paired per-seed differences; exploratory, not biological replicate uncertainty',
        validation=dict(same_input_pairs=True,zero_input_stability=True))
    write_json(out/'results.json',data)
    render_report(root,out,data)
    files=list(out.glob('*.json'))+list(out.glob('*.csv'))+list(out.glob('*.html'))+list(out.glob('*.png'))+list(out.glob('*.svg'))
    write_json(out/'manifest.json',manifest(files,source='REAL_MALECNS_RESEARCH_PILOT',graph_manifest_sha256=sha256(engine.snapshot/'manifest.json'),
        source_code_sha256={str(f.relative_to(root)):sha256(f) for f in sorted((root/'src').rglob('*')) if f.is_file() and '__pycache__' not in str(f)},
        limitations=['One reconstructed graph, five stochastic seeds are not five animals.','No solved human-ear FEM or physiology fitting.','Post-onset latency is descriptive and conditioned on response.']))
    write_json(root/'outputs/research/latest.json',{'directory':str(out),'report':str(out/'index.html')})
    return out

def render_report(root,out,data):
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,5.2))
    groups=[['tone_original','tone_weight_shuffled','tone_rewired','tone_time_shuffled','tone_jo_only'],
            ['pulse15_rms','pulse36_rms','pulse72_rms'],['gain05','tone_original','gain15','gain20']]
    for ax,group,title in zip(axes,groups,['Paired structural / timing controls','Equal-RMS pulse intervals','Assumed synaptic gain sensitivity']):
        for x,name in enumerate(group):
            stat=next(r for r in data['summary'] if r['condition']==name and r['metric']=='downstream_stimulus_spikes')
            points=[r['downstream_stimulus_spikes'] for r in data['trials'] if r['condition']==name]
            ax.scatter(np.full(len(points),x)+np.linspace(-.1,.1,len(points)),points,s=20,color='#38a5c9',zorder=3,label='Stochastic trial' if x==0 else None)
            ax.errorbar(x,stat['mean'],yerr=[[stat['mean']-stat['ci95_low']],[stat['ci95_high']-stat['mean']]],fmt='o',color='#cc672d',capsize=5,label='Mean and bootstrap 95% CI' if x==0 else None)
        ax.set_xticks(range(len(group)),[n.replace('tone_','').replace('_rms','') for n in group],rotation=30,ha='right')
        ax.set_title(title,fontsize=10);ax.set_ylabel('Downstream spikes, 200–800 ms');ax.grid(axis='y',alpha=.2);ax.set_ylim(bottom=0)
    axes[1].set_xticklabels(['15','36','72'],rotation=0);axes[1].set_xlabel('IPI (ms), stimulus RMS = 0.5 Pa')
    axes[2].set_xticklabels(['0.5','1.0','1.5','2.0'],rotation=0);axes[2].set_xlabel('Assumed w0 (mV)')
    fig.suptitle(f'Connectome-constrained LIF pilot | {len(data["protocol"]["trial_seeds"])} stochastic trials per condition, one reconstructed graph',fontsize=11)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=2,frameon=False)
    fig.tight_layout(rect=[0,.06,1,.94]);fig.savefig(out/'research_summary.png',dpi=180);fig.savefig(out/'research_summary.svg');plt.close(fig)
    from .view_templates import research_html
    (out/'index.html').write_text(research_html(data,(out/'research_summary.png').read_bytes()),encoding='utf-8')


def main(argv=None):
    root=configure_storage();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=root/'configs/research_pilot.json')
    args=parser.parse_args(argv);plan=json.loads(args.protocol.read_text(encoding='utf-8'))
    print(run_protocol(root,plan,lambda s:print(s,flush=True)),flush=True)
    return 0
