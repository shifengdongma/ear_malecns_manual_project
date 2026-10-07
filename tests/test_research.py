import numpy as np
import pandas as pd
import pytest
from ear_malecns.signal_workbench import source_wave,parameters,Engine
from ear_malecns.research import shuffle_stimulus_times,event_digest,interval,paired_difference
from ear_malecns.config import load_config
from pathlib import Path

@pytest.mark.parametrize('ipi',[15,36,72])
def test_equal_rms_controls_preserve_window_and_target_energy(ipi):
    t,x=source_wave(parameters({'kind':'pulse','ipi_ms':ipi,'rms_match_pa':.5}))
    active=(t>=.2)&(t<.8)
    assert np.sqrt(np.mean(x[active]**2))==pytest.approx(.5,abs=1e-12)
    assert np.all(x[~active]==0)


def test_time_null_preserves_each_channel_count_and_outside_events():
    c=np.array([0,0,0,1,1,1]);t=np.array([.01,.21,.36,.05,.22,.91])
    cc,tt=shuffle_stimulus_times(c,t,77)
    for ch in [0,1]:
        assert np.sum(cc==ch)==np.sum(c==ch)
        assert np.sum((cc==ch)&(tt>=.2)&(tt<.8))==np.sum((c==ch)&(t>=.2)&(t<.8))
    assert set(zip(cc[(tt<.2)|(tt>=.8)],tt[(tt<.2)|(tt>=.8)]))==set(zip(c[(t<.2)|(t>=.8)],t[(t<.2)|(t>=.8)]))
    assert len(set(zip(cc,np.rint(tt/.0001).astype(int))))==len(cc)
    assert event_digest(cc,tt)==event_digest(*shuffle_stimulus_times(c,t,77))
    assert np.array_equal(c,[0,0,0,1,1,1])


def test_paired_bootstrap_uses_differences_not_unpaired_se():
    trials=pd.DataFrame({'condition':['a','a','b','b'],'trial_seed':[1,2,1,2],'m':[12,102,10,100]})
    r=paired_difference(trials,'a','b','m')
    assert r['mean']==r['ci95_low']==r['ci95_high']==2
    with pytest.raises(ValueError):paired_difference(trials.iloc[:-1],'a','b','m')
    with pytest.raises(ValueError):interval([1])


def test_invalid_rms_and_imported_rescaling_rejected():
    for p in [{'rms_match_pa':0},{'rms_match_pa':float('inf')},{'mechanical':'imported','rms_match_pa':.5},{'topology_seed':1.5}]:
        with pytest.raises(ValueError):parameters(p)
    with pytest.raises(ValueError):source_wave(parameters({'amplitude_pa':0,'rms_match_pa':.5}))


def test_compact_mode_preserves_spike_times():
    e=Engine.__new__(Engine);e.ids=[1,2];e.seed_ids=[1]
    e.nodes=pd.DataFrame({'bodyId':[1,2],'consensusNt':['acetylcholine','gaba']})
    edges=pd.DataFrame({'bodyId_pre':[1],'bodyId_post':[2],'weight':[10]})
    cfg=load_config(Path(__file__).parents[1]/'configs/pipeline_real_demo.yaml')
    cfg['snn'].update(simulation_ms=25,input_weight_mv=12)
    full=e.simulate(edges,np.array([0]),np.array([.005]),cfg)
    compact=e.simulate(edges,np.array([0]),np.array([.005]),cfg,record_voltage=False)
    pd.testing.assert_frame_equal(full[0],compact[0])
    assert full[4]==compact[4] and compact[2].shape==(2,0)


@pytest.mark.parametrize('duration',[0,.4,2.01,float('nan')])
def test_empty_or_invalid_analysis_window_rejected(duration):
    from ear_malecns.signal_workbench import analysis_window
    with pytest.raises(ValueError):analysis_window(duration)


def test_valid_imported_analysis_window():
    from ear_malecns.signal_workbench import analysis_window
    assert analysis_window(.5)==pytest.approx((.2,.3))
    assert analysis_window(1)==pytest.approx((.2,.8))
