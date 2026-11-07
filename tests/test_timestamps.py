from event_camera.timestamps import assess_timestamps

def test_timestamp_assessment():
 good={'events':{'count':100,'first_us':1000000,'last_us':5000000},'frames':{'count':40,'first_us':1020000,'last_us':4990000},'imu':{'count':1000,'first_us':1001000,'last_us':5001000}}
 result=assess_timestamps(good); assert result['status']=='PASS' and result['stream_overlap_us']==3970000
 bad={'events':good['events'],'frames':{'count':40,'first_us':100,'last_us':4990000,'jumps_over_10s':1}}
 assert assess_timestamps(bad)['status']=='FAIL'
 assert assess_timestamps({'events':good['events']})['status']=='INCONCLUSIVE'
