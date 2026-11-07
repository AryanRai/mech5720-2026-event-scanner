"""Portable orthographic CAD preview with a software depth buffer."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np

def render(parts,out,cx,ty):
    triangles=[];colours=[]
    for name,shape,color,ref in parts:
        objects=[shape.val()]
        if name=='REF_PiCam_from_supplied_CAD':
            ss=shape.val().Solids();objects=[ss[i] for i in [0,1,111,112,113,114,115]]
        for obj in objects:
            vs,ts=obj.tessellate(.3,.25)
            xyz=np.array([v.toTuple() for v in vs]);fs=xyz[np.array(ts)]
            triangles.extend(fs);colours.extend([color]*len(fs))
    triangles=np.array(triangles);colours=np.array(colours)
    ns=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);ns/=np.maximum(np.linalg.norm(ns,axis=1)[:,None],1e-12)
    light=np.array([.4,-.6,1.]);light/=np.linalg.norm(light)
    shade=.48+.5*np.abs(ns@light)
    rgb=np.clip(colours*shade[:,None]*255,0,255).astype(np.uint8)

    def view(path,size,pos,focal,scale):
        w,h=size;front=np.array(pos,dtype=float)-focal;front/=np.linalg.norm(front)
        right=np.cross([0,0,1],front);right/=np.linalg.norm(right);up=np.cross(front,right)
        q=triangles-np.array(focal);px=q@right*(h/(2*scale))+w/2;py=-q@up*(h/(2*scale))+h/2;pz=q@front
        arr=np.empty((h,w,3),dtype=np.uint8);arr[:]=[242,246,250];depth=np.full((h,w),-np.inf)
        for i in range(len(triangles)):
            x=px[i];y=py[i];z=pz[i]
            xmin=max(0,int(np.floor(x.min())));xmax=min(w-1,int(np.ceil(x.max())))
            ymin=max(0,int(np.floor(y.min())));ymax=min(h-1,int(np.ceil(y.max())))
            if xmin>xmax or ymin>ymax:continue
            den=(y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2])
            if abs(den)<1e-8:continue
            xx,yy=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5)
            a=((y[1]-y[2])*(xx-x[2])+(x[2]-x[1])*(yy-y[2]))/den
            b=((y[2]-y[0])*(xx-x[2])+(x[0]-x[2])*(yy-y[2]))/den;c=1-a-b
            zz=a*z[0]+b*z[1]+c*z[2];old=depth[ymin:ymax+1,xmin:xmax+1]
            ok=(a>=-1e-7)&(b>=-1e-7)&(c>=-1e-7)&(zz>old)
            old[ok]=zz[ok];arr[ymin:ymax+1,xmin:xmax+1][ok]=rgb[i]
        Image.fromarray(arr).save(path)

    view(out/'assembly_view.png',(1100,850),(490,650,430),(0,110,40),240)
    view(out/'rear_view.png',(600,450),(-210,-360,220),(-45,-45,65),85)
    view(out/'laser_detail.png',(600,440),(230,100,150),(85,-45,65),57)
    canvas=Image.new('RGB',(1800,1140),'#f2f6fa');d=ImageDraw.Draw(canvas)
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    def txt(x,y,s,n=22,b=False,c='#15344a'):d.text((x,y),s,font=ImageFont.truetype(bold if b else font,n),fill=c)
    txt(45,27,'DAVIS240C scanner | Complete review assembly',36,True)
    txt(45,83,'Two flat base sections · upright camera bracket · raised studded object holder',23)
    canvas.paste(Image.open(out/'assembly_view.png'),(0,150))
    canvas.paste(Image.open(out/'rear_view.png'),(1150,150))
    canvas.paste(Image.open(out/'laser_detail.png'),(1150,620))
    txt(1175,118,'CAMERA BRACKET — REAR',22,True)
    txt(1175,603,'SERVO + LASER HOLDER',22,True)
    txt(45,1030,'Seven separate custom parts; purchased hardware and target shown as references.',23,True)
    txt(45,1080,'Actual CAD geometry. Camera, lens, servo, laser and LEGO interfaces require fit checks.',22)
    canvas.save(out/'DAVIS240C_Scanner_Preview.png')
