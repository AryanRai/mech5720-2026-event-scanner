"""Cross-stream timestamp checks. This checks plausibility, not physical clock accuracy."""

def assess_timestamps(streams, tolerance_us=500000):
    issues=[]; populated={name:s for name,s in streams.items() if s.get('count',0)>0}
    if not populated: issues.append('No timestamped samples were read')
    for name,s in streams.items():
        if not s.get('count',0): issues.append(f'{name}: stream delivered no samples')
    for name,s in populated.items():
        if s.get('backward',0) or s.get('backward_batches',0): issues.append(f'{name}: timestamps move backwards')
        if s.get('jumps_over_10s',0): issues.append(f'{name}: timestamp jump over 10 seconds')
        if s.get('first_us') is None or s.get('last_us') is None: issues.append(f'{name}: missing timestamp bounds')
    ranges=[(s['first_us'],s['last_us']) for s in populated.values() if s.get('first_us') is not None and s.get('last_us') is not None]
    overlap=max(0,min(e for _,e in ranges)-max(b for b,_ in ranges)) if ranges else 0
    if len(ranges)>1:
        starts=[x[0] for x in ranges]; ends=[x[1] for x in ranges]
        if max(starts)-min(starts)>tolerance_us: issues.append('Stream starts differ by more than tolerance; check missing startup data or clock scale')
        if max(ends)-min(ends)>tolerance_us: issues.append('Stream ends differ by more than tolerance; check missing data or clock scale')
        if not overlap: issues.append('Stream time ranges do not overlap')
    return {'status':'FAIL' if issues else 'PASS' if len(ranges)>=2 else 'INCONCLUSIVE','stream_overlap_us':overlap,'tolerance_us':tolerance_us,'issues':issues,'limitation':'Matching timestamp ranges does not measure physical timing offsets, exposure timing, or drift.'}
