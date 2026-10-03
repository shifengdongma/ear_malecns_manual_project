import numpy as np
import pandas as pd
import pytest
from ear_malecns.signal_workbench import Engine, DEFAULTS, parameters, source_wave, mechanical_data, fit_reference_calibration
from ear_malecns.config import load_config
from pathlib import Path


def test_stimulus_amplitude_and_silence():
    _, x = source_wave(parameters({}))
    _, y = source_wave(parameters({'amplitude_pa': .25}))
    assert np.allclose(y, x*.25)
    _, z = source_wave(parameters({'amplitude_pa': 0}))
    assert not np.any(z)
    assert not np.any(x[:2000]) and not np.any(x[8000:])


def test_shared_calibration_is_deterministic_and_not_test_fitted():
    first = fit_reference_calibration('demo')
    assert first == fit_reference_calibration('demo')
    assert first['q_high'] > first['q_low']
    assert mechanical_data(parameters({}))['fem_version'].startswith('SYNTHETIC_')
    assert mechanical_data(parameters({'mechanical':'direct'}))['fem_version'].startswith('ACOUSTIC_DIRECT_')


@pytest.mark.parametrize('values', [{'delay_ms':0}, {'amplitude_pa':float('nan')}, {'seed':1.5}, {'kind':'unknown'}, {'waveform':[0]*9999, 'kind':'wav'}, {'surprise':True}])
def test_invalid_experiment_rejected(values):
    with pytest.raises(ValueError):
        parameters(values)


def test_delayed_excitation_and_inhibition_have_correct_recorded_voltages():
    # A small fixture verifies the mechanism independently of the real graph.
    engine=Engine.__new__(Engine)
    engine.ids=[1,2,3]
    engine.seed_ids=[1]
    engine.nodes=pd.DataFrame({'bodyId':[1,2,3], 'consensusNt':['acetylcholine','gaba','acetylcholine']})
    cfg=load_config(Path(__file__).parents[1]/'configs/pipeline_real_demo.yaml')
    cfg['snn'].update(simulation_ms=25, input_weight_mv=12, w0_mv=1, delay_ms=1.5)
    edges=pd.DataFrame({'bodyId_pre':[1,2], 'bodyId_post':[2,3], 'weight':[10,10]})
    spikes,vt,v,connections,arrivals=engine.simulate(edges,np.array([0]),np.array([.005]),cfg)
    assert v.shape==(3,len(vt))
    pre=spikes.loc[spikes.bodyId==1,'time_ms'].to_numpy()
    assert len(pre)==1
    assert arrivals==[[round(float(pre[0]+1.5),3),0]]
    assert connections[0][2]>0 and connections[1][2]<0
    arrival=arrivals[0][0]
    before=np.flatnonzero(vt<arrival)[-1]
    after=np.flatnonzero(vt>=arrival)[0]
    assert v[1,before]==pytest.approx(-60)
    assert v[1,after]>-60
    assert np.allclose(v[2],-60) # No spike in neuron 2, so its GABA edge never delivers.

    engine.seed_ids=[2]
    _,vt,v,connections,arrivals=engine.simulate(edges,np.array([0]),np.array([.005]),cfg)
    assert len(arrivals)==1 and arrivals[0][1]==1
    assert v[2].min() < -60 # A monitored GABA spike actually hyperpolarizes neuron 3.
