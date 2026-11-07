"""Synthetic native-format round trip; no hardware or physical claims."""
import gc
import dv_processing as dv
import numpy as np

def test_aedat_event_roundtrip(tmp_path):
    path=tmp_path/'synthetic.aedat4'
    config=dv.io.MonoCameraWriter.EventOnlyConfig('synthetic',(240,180))
    w=dv.io.MonoCameraWriter(str(path),config)
    events=dv.EventStore()
    for i in range(100): events.push_back(1000000+i*100,i%240,i%180,bool(i%2))
    w.writeEvents(events); del w; gc.collect()
    r=dv.io.MonoCameraRecording(str(path)); arrays=[]
    while True:
        batch=r.getNextEventBatch()
        if batch is None: break
        arrays.append(batch.numpy().copy())
    got=np.concatenate(arrays)
    assert len(got)==100
    np.testing.assert_array_equal(got['timestamp'],1000000+np.arange(100)*100)
    np.testing.assert_array_equal(got['polarity'],np.arange(100)%2)
