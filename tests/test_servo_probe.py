"""Trace integrity and real diagnostic C++ logic with simulated hardware."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('servo_probe',ROOT/'scripts/analyse_servo_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def operation():
    return {'id':'probe','state':'done','result':{'stop_confirmed':True,
        'final_status':'OK status armed=0 laser=0 attached=0',
        'lines':['E,4294967200,PROBE_RELEASED,1500,1500,1510',
                 'F,4294967250,4294967260,1500,310,4960,16,4,0,0',
                 'E,20,PROBE_TARGET_HOLD,1510,1000,0',
                 'F,50,60,1510,320,5120,16,4,1,0',
                 'E,200,PROBE_DONE,1510,0,0']}}


def test_wrap_and_units():
    summary,samples=probe.analyse(operation())
    assert summary['status']=='VALID_DIAGNOSTIC'
    assert samples[1]['t_us']==146
    assert samples[0]['block_mean_raw']==310
    assert samples[0]['feedback_scaled']==1240
    assert samples[0]['adc_duration_us']==10


@pytest.mark.parametrize('damage',['abort','laser','reset','truncated','release','empty'])
def test_bad_trace_rejected(damage):
    op=operation(); r=op['result']
    if damage=='abort':r['lines'][-1]='E,200,PROBE_ABORTED,1510,0,0'
    if damage=='laser':r['lines'][1]=r['lines'][1][:-1]+'1'
    if damage=='reset':r['lines'].insert(-1,'F,40,41,1510,320,5120,16,4,1,0')
    if damage=='truncated':r['log_truncated']=True
    if damage=='release':r['final_status']='OK status armed=0 laser=0 attached=1'
    if damage=='empty':r['lines']=[]
    assert probe.analyse(op)[0]['status']=='INVALID'


def test_controller_deadline_abort_release_and_wrap(tmp_path):
    compiler=shutil.which('g++')
    if not compiler:pytest.skip('g++ unavailable for simulated controller logic')
    source=(ROOT/'firmware/feedback_controller/scanner_controller/scanner_controller.ino').read_text()
    diagnostic=source[source.index('const uint32_t PROBE_PERIOD_US'):source.index('\nvoid printStatus()')]
    harness=r'''
#include <cstdint>
#include <string>
#include <sstream>
#include <cassert>
#include <vector>
#define F(x) x
const int PIN_FEEDBACK=0, ADC_OVERSAMPLE=16, ADC_DIVIDE=4, HAS_FEEDBACK=1, SLEW_US_PER_S=800;
uint32_t clockTick=0, elapsedTicks=0, abortAt=0; bool armed=false,laserOn=false,abortRun=false,busy=false;
int currentCmd=1500, moves=0, stops=0;
struct Servo { bool on=false; bool attached(){return on;} } servo;
struct Output { std::ostringstream text; template<class T> void print(T x){text<<x;}
 void print(uint8_t x){text<<int(x);} template<class T>void println(T x){print(x);text<<'\n';} } Serial;
uint32_t micros(){clockTick+=100;elapsedTicks+=100;return clockTick;}
uint16_t analogRead(int){return 310;}
void emergencyStop(){armed=laserOn=false;servo.on=false;abortRun=true;stops++;}
void serviceRun(){if(abortAt && elapsedTicks>=abortAt)emergencyStop();}
void moveCmd(int command){assert(!laserOn&&!armed);assert(command>=1100&&command<=1900);servo.on=true;currentCmd=command;moves++;}
void logEvent(uint32_t t,const char* name,long a=0,long b=0,long c=0){Serial.print("E,");Serial.print(t);Serial.print(',');Serial.print(name);Serial.print(',');Serial.println(a);}
'''+diagnostic+r'''
void reset(uint32_t start=0){clockTick=start;elapsedTicks=abortAt=0;armed=laserOn=abortRun=busy=false;currentCmd=1500;moves=stops=0;servo.on=false;Serial.text.str("");Serial.text.clear();}
int main(){
 reset();runProbe(1500,1510,1000);assert(!servo.on&&!armed&&!laserOn&&!busy);assert(stops==2);assert(Serial.text.str().find("PROBE_DONE")!=std::string::npos);assert(Serial.text.str().find("F,")!=std::string::npos);assert(elapsedTicks<8000000);
 reset();runProbe(1099,1510,1000);assert(moves==0);assert(Serial.text.str().find("ERR probe")!=std::string::npos);
 reset();abortAt=800000;runProbe(1500,1510,1000);assert(!servo.on&&!busy);assert(Serial.text.str().find("PROBE_ABORTED")!=std::string::npos);
 reset(UINT32_MAX-100000);runProbe(1510,1500,1000);assert(!servo.on);assert(Serial.text.str().find("PROBE_DONE")!=std::string::npos);
 reset();probeStart=0;probeNext=0;clockTick=8000001;servo.on=true;probeTick();assert(abortRun); // caller cleanup still mandatory
 reset();armed=laserOn=true;runProbe(1500,1510,100);assert(!armed&&!laserOn&&!servo.on);
}
'''
    src=tmp_path/'probe.cpp';src.write_text(harness)
    exe=tmp_path/'probe.exe'
    subprocess.run([compiler,'-std=c++17',str(src),'-o',str(exe)],check=True,capture_output=True,text=True)
    subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=10)
