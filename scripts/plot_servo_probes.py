"""Reproduce an ADC/command trace figure from retained probe exports (offline)."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories',type=Path,nargs='+')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        p.error('Output already exists; retain previous figures')
    fig,axes=plt.subplots(len(a.directories),2,figsize=(11,3.5*len(a.directories)),squeeze=False)
    for i,directory in enumerate(a.directories):
        summary=json.loads((directory/'summary.json').read_text())
        with (directory/'samples.csv').open(newline='') as f:
            samples=list(csv.DictReader(f))
        marker=next(e['t_us'] for e in summary['events'] if e['name']=='PROBE_TARGET_HOLD')
        t=[(float(s['t_us'])-marker)/1e6 for s in samples]
        ax,command=axes[i]
        ax.plot(t,[float(s['raw_first']) for s in samples],'.',ms=2,alpha=.6,label='First raw ADC read')
        ax.plot(t,[float(s['block_mean_raw']) for s in samples],lw=.8,label='Mean of ADC block (raw units)')
        ax.set_ylabel('Feedback (raw ADC counts)')
        ax.legend(fontsize=8)
        command.step(t,[int(s['cmd_us']) for s in samples],where='post',label='Command')
        released=[s for s in samples if s['attached']=='0']
        if released:
            left=(float(released[0]['t_us'])-marker)/1e6
            right=(float(released[-1]['t_us'])-marker)/1e6
            for panel in (ax,command):panel.axvspan(left,right,color='grey',alpha=.15)
        command.set_ylabel('Command (µs)')
        for panel in (ax,command):
            panel.axvline(0,color='k',ls='--',lw=.8)
            panel.set_xlabel('Time from target command reached (s)')
            panel.grid(alpha=.2)
        ax.set_title(f'{directory.name}\n{summary["status"]}',fontsize=9)
        command.set_title('Grey: released baseline; dashed: target command reached',fontsize=9)
    fig.suptitle('Laser-off servo diagnostic — ADC variation is not independently measured shaft motion',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.96))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(a.output,dpi=170)
    print(a.output.resolve())


if __name__=='__main__':main()
