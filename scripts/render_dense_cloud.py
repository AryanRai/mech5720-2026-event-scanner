"""Render retained dense points with separate axes and colourbar spacing."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);args=parser.parse_args()
    a=np.loadtxt(args.folder/'points.csv',delimiter=',',skiprows=1)
    fig=plt.figure(figsize=(12,5.8));ax=fig.add_subplot(121,projection='3d');side=fig.add_subplot(122)
    sc=ax.scatter(a[:,3],a[:,5],-a[:,4],c=a[:,0],cmap='viridis',s=5)
    side.scatter(a[:,5],-a[:,4],c=a[:,0],cmap='viridis',s=5)
    ax.set(xlabel='Camera X (mm)',ylabel='Camera Z / depth (mm)',zlabel='−Camera Y (mm)');ax.view_init(elev=24,azim=-62)
    side.set(xlabel='Camera Z / depth (mm)',ylabel='−Camera Y (mm)',title='Retained stripe profiles')
    ax.set_position([.015,.15,.37,.71]);side.set_position([.53,.15,.34,.71])
    cax=fig.add_axes([.92,.24,.015,.5]);fig.colorbar(sc,cax=cax,label='Servo command (µs)')
    fig.suptitle('Exploratory denser shoe point cloud — interpolated laser planes',fontsize=14)
    fig.text(.5,.025,f'{len(a)} points / {len(set(a[:,0]))} positions • 3 ms APS • unvalidated intermediate planes and object accuracy',ha='center',fontsize=9)
    fig.savefig(args.folder/'point_cloud.png',dpi=180)


if __name__=='__main__':main()
