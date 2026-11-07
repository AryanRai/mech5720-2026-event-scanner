"""Exercise actual static controller logic with simulated clock/ADC/interlock."""
from pathlib import Path
import shutil
import subprocess
import pytest
from event_camera.rig_control import validate

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('action',['static','observe'])
def test_static_request_bounds_and_authorization(action):
    request=dict(id='static_test',action=action,us=1500,arm=True,contained=True)
    assert validate(request)==request
    for changes in ({'arm':False},{'contained':False},{'us':1099},{'us':1901},{'us':1500.0}):
        with pytest.raises(ValueError):validate(request|changes)


def test_real_static_controller_gates_and_cleanup(tmp_path):
    compiler=shutil.which('g++')
    if not compiler:pytest.skip('g++ unavailable')
    source=(ROOT/'firmware/feedback_controller/scanner_controller/scanner_controller.ino').read_text()
    code=source[source.index('const uint8_t STATIC_N'):source.index('\nvoid handleCommand(')]
    harness=r'''
#include <cstdint>
#include <sstream>
#include <cassert>
#define F(x) x
const int ADC_OVERSAMPLE=16, ADC_DIVIDE=4, PIN_FEEDBACK=0, HAS_FEEDBACK=1;
uint32_t tick=0, elapsed=0, stopAt=0, openAt=0;
bool armed=true,laserOn=false,abortRun=false,busy=false,manualLaser=false,closed=true,noise=false;
int currentCmd=1500,moves=0,emissions=0,reads=0;uint32_t litStart=0,litDuration=0;
struct Servo {bool on=false;bool attached(){return on;}}servo;
struct Output {std::ostringstream text;template<class T>void print(T x){text<<x;}
void print(uint8_t x){text<<int(x);}template<class T>void println(T x){print(x);text<<'\n';}}Serial;
uint32_t micros(){tick+=100;elapsed+=100;return tick;}
bool interlockClosed(){return closed;}
void writeLaser(bool on,const char*){if(on){emissions++;litStart=elapsed;}else if(laserOn)litDuration=elapsed-litStart;laserOn=on;}
void emergencyStop(){writeLaser(false,"");armed=false;servo.on=false;abortRun=true;}
void serviceRun(){if(openAt && elapsed>=openAt)closed=false;if(!closed || (stopAt && elapsed>=stopAt))emergencyStop();}
uint16_t analogRead(int){reads++;return noise?310+((reads/16)%2)*4:310;}
void moveCmd(int x){assert(x==currentCmd);assert(!laserOn);servo.on=true;moves++;}
bool laserRequest(bool on){assert(servo.on);if(!armed||!closed||abortRun)return false;writeLaser(on,"");return true;}
void logEvent(uint32_t,const char* name,long=0,long=0,long=0){Serial.println(name);}
'''+code+r'''
void reset(uint32_t start=0){tick=start;elapsed=stopAt=openAt=0;armed=closed=true;laserOn=abortRun=busy=manualLaser=noise=false;servo.on=false;currentCmd=1500;moves=emissions=reads=0;litDuration=0;Serial.text.str("");Serial.text.clear();}
void clean(){assert(!armed&&!laserOn&&!servo.on&&!busy);}
int main(){
 reset();runStatic(1500);clean();assert(emissions==1&&moves==1);assert(litDuration>=1000000&&litDuration<1010000);assert(elapsed<6000000);assert(Serial.text.str().find("STATIC_DONE")!=std::string::npos);
 reset();noise=true;runStatic(1500);clean();assert(emissions==0);assert(Serial.text.str().find("STATIC_UNSTABLE")!=std::string::npos);
 reset();runStatic(1510);assert(moves==0&&emissions==0);
 reset();armed=false;runStatic(1500);assert(moves==0&&emissions==0);
 reset();openAt=3200000;runStatic(1500);clean();assert(emissions==1&&litDuration<1000000);
 reset();stopAt=1000000;runStatic(1500);clean();assert(emissions==0);
 reset(UINT32_MAX-100000);runStatic(1500);clean();assert(emissions==1);assert(Serial.text.str().find("STATIC_DONE")!=std::string::npos);
 reset();staticStart=0;tick=6000001;staticTick();assert(abortRun);
 reset();staticCount=50;staticLargestGap=30001;assert(!staticFeedbackReady());
 // Observation mode retains noise warning rather than a false stability pass.
 reset();noise=true;runStatic(1500,true);clean();assert(emissions==1);assert(Serial.text.str().find("STATIC_SCREEN_WARN")!=std::string::npos);assert(Serial.text.str().find("STATIC_OBSERVE")!=std::string::npos);
 reset();noise=true;openAt=3200000;runStatic(1500,true);clean();assert(emissions==1&&litDuration<1000000);
 reset();noise=true;stopAt=1000000;runStatic(1500,true);clean();assert(emissions==0);
 reset();armed=false;runStatic(1500,true);assert(moves==0&&emissions==0);
 reset();runStatic(1510,true);assert(moves==0&&emissions==0);
 // Direct boundary/shape checks for the exploratory v1.6 screen.
 reset();staticCount=50;staticIndex=0;staticLargestGap=10000;
 for(int i=0;i<50;i++)staticSums[i]=4960;
 staticSums[0]+=48;assert(staticFeedbackReady()); // isolated3-count spike, no trimming
 staticSums[0]=4960+64;assert(!staticFeedbackReady()); // excessive maximum
 for(int i=0;i<50;i++)staticSums[i]=4960+(i%2?8:-8);
 assert(staticFeedbackReady()); // RMS exactly0.5
 for(int i=0;i<50;i++)staticSums[i]=4960+(i%2?9:-9);
 assert(!staticFeedbackReady()); // RMS above0.5
 for(int i=0;i<50;i++)staticSums[i]=4960+(i<25?-5:5);
 assert(!staticFeedbackReady()); // drift0.625 despite low RMS
 staticIndex=37;
 for(int i=0;i<50;i++)staticSums[(staticIndex+i)%50]=4960+(i<25?-5:5);
 assert(!staticFeedbackReady()); // ring chronological ordering

}
'''
    src=tmp_path/'static.cpp';src.write_text(harness)
    exe=tmp_path/'static.exe'
    subprocess.run([compiler,'-std=c++17',str(src),'-o',str(exe)],check=True,capture_output=True,text=True)
    subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=10)
