"""Solid camera/laser base assembly. mm. Requires CadQuery 2.7, NumPy, Pillow."""
from pathlib import Path
import math,json
import cadquery as cq
OUT=Path(__file__).resolve().parent
(OUT/'parts').mkdir(exist_ok=True)
CX,CY,SX,SY=-45.,-45.,85.,-45.
ZOPT=82.5
TARGET=(0.,225.)
CAM_YAW=-math.degrees(math.atan2(-CX,TARGET[1]-CY))
LASER_YAW=math.degrees(math.atan2(SX,TARGET[1]-SY))
assy=cq.Assembly(name='DAVIS240C_Two_Section_Scanner_Review')
parts=[];custom=[];rows=[]
BLUE=(.15,.36,.54);ORANGE=(.93,.50,.13);DARK=(.23,.26,.29);METAL=(.70,.73,.75)

def box(w,l,h,x=0,y=0,z=0):
    return cq.Workplane('XY').box(w,l,h,centered=(True,True,False)).translate((x,y,z))
def hole(s,x,y,r,z=-1,h=150):
    return s.cut(cq.Workplane('XY').center(x,y).circle(r).extrude(h).translate((0,0,z)))
def cyl(r,h,x,y,z,d=(0,0,1)):
    return cq.Workplane('XY').newObject([cq.Solid.makeCylinder(r,h,cq.Vector(x,y,z),cq.Vector(*d))])
def camera_pose(s):return s.rotate((0,0,0),(0,0,1),CAM_YAW).translate((CX,CY,0))
def laser_pose(s):return s.rotate((0,0,0),(0,0,1),LASER_YAW).translate((SX,SY,0))
def camxy(x,y):
    t=math.radians(CAM_YAW)
    return CX+x*math.cos(t)-y*math.sin(t),CY+x*math.sin(t)+y*math.cos(t)
def add(name,s,color,kind='custom'):
    assert s.val().isValid(),name
    assy.add(s,name=name,color=cq.Color(*color));parts.append((name,s,color,kind!='custom'))
    b=s.val().BoundingBox()
    rows.append(dict(name=name,kind=kind,solids=len(s.solids().vals()),size_mm=[round(v,3) for v in [b.xlen,b.ylen,b.zlen]]))
    if kind=='custom':
        custom.append((name,s))
        cq.exporters.export(s,str(OUT/'parts'/(name+'.step')))
        # Keep geometry orientation but put the part on the slicer's Z=0 plane.
        printable=s.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
        cq.exporters.export(printable,str(OUT/'parts'/(name+'.stl')),tolerance=.06,angularTolerance=.1)

# Solid plate and the same locating-tab interface as the compact two-piece base.
base=box(240,220,8).edges('|Z').fillet(4)
for x in [-70,70]:
    base=base.union(box(28,22,4,x,119))
    base=hole(base,x,120,2.25)
    base=base.cut(cq.Workplane('XY').newObject([cq.Solid.makeCone(4.5,2.25,2.25,cq.Vector(x,120,0),cq.Vector(0,0,1))]))
foot_holes=[]
for dx in [-38,38]:
    for y in [-46,16]:foot_holes.append(camxy(-9+dx,y))
for dx in [-22,22]:
    for dy in [-20,20]:foot_holes.append((SX+dx,SY+dy))
for x,y in foot_holes:
    base=hole(base,x,y,2.2)
    base=base.cut(cq.Workplane('XY').newObject([cq.Solid.makeCone(4.5,2.2,2.3,cq.Vector(x,y,0),cq.Vector(0,0,1))]))
add('01_Solid_Base',base,BLUE)

# Upright rear frame style from reference; DAVIS uses an underside tripod shoe.
CAM_BOTTOM=49.25
# Rear upright has a large opening to leave the exposed boards and connectors clear.
cam=box(100,80,6,-9,-15,8).union(box(80,6,100,0,-23,14))
cam=cam.cut(box(64,10,62,0,-23,48))
# Shoe reaches from rear frame under the camera's mounting boss.
cam=cam.union(box(64,40,6,0,0,CAM_BOTTOM-6))
for x in [-29,29]:
    cam=cam.union(box(6,32,CAM_BOTTOM-20,x,-4,14))
for dx in [-38,38]:
    for y in [-46,16]:cam=hole(cam,-9+dx,y,2.2,z=7,h=8)
cam=hole(cam,0,-.5,3.4,z=CAM_BOTTOM-7,h=8)
cam=camera_pose(cam);add('02_DAVIS_Upright_Bracket',cam,BLUE)

# U-shaped servo support, matching the approved visual arrangement.
tower=box(60,60,6,SX,SY,8)
for dx in [-24,24]:tower=tower.union(box(6,24,35,SX+dx,SY,14))
tower=tower.union(box(60,50,5,SX,SY,49)).cut(box(23.5,12.8,8,SX+5.4,SY,48))
for dx in [-22,22]:
    for dy in [-20,20]:tower=hole(tower,SX+dx,SY+dy,2.2,z=7,h=8)
for dx in [-8.6,19.4]:tower=hole(tower,SX+dx,SY,1.1,z=48,h=8)
add('03_Servo_Bracket',tower,BLUE)

servo=box(22.9,12.2,28.5,SX+5.4,SY,30).union(box(33.4,12.2,2,SX+5.4,SY,54))
servo=servo.union(cyl(2.5,4,SX,SY,58.5))
for dx in [-8.6,19.4]:servo=hole(servo,SX+dx,SY,1.1,z=53,h=4)
add('REF_Servo_Provisional',servo,DARK,'hardware')
horn=cyl(8,3,0,0,62.5)
for dy in [-6,6]:horn=hole(horn,0,dy,1.1,z=62,h=5)
horn=hole(horn,0,0,1.3,z=62,h=5)
add('REF_Servo_Horn_Provisional',laser_pose(horn),(.85,.85,.79),'hardware')

plate=box(70,50,4,z=65.5).edges('|Z').fillet(4)
plate=hole(plate,0,0,3,z=65,h=6)
for dy in [-6,6]:
    plate=hole(plate,0,dy,1.1,z=65,h=6)
    plate=hole(plate,0,dy,1.9,z=67.5,h=2.1)
for dx in [-12,12]:plate=hole(plate,dx,0,1.7,z=65,h=6)
add('04_Rotating_Laser_Cradle',laser_pose(plate),ORANGE)
bore=cyl(6.05,40,0,-20,ZOPT,(0,1,0))
lower=box(34,32,4,z=69.5).union(box(30,32,8.7,z=73.5)).cut(bore)
upper=box(30,32,10,z=82.8).cut(bore)
for dx in [-12,12]:
    lower=hole(lower,dx,0,1.7,z=69,h=25)
    upper=hole(upper,dx,0,1.7,z=69,h=25)
add('05_Laser_Clamp_Lower',laser_pose(lower),ORANGE)
add('06_Laser_Clamp_Upper',laser_pose(upper),(.98,.66,.24))
add('REF_Laser_Provisional',laser_pose(cyl(6,40,0,-20,ZOPT,(0,1,0))),DARK,'hardware')
add('REF_Laser_Aperture',laser_pose(cyl(3,.5,0,20,ZOPT,(0,1,0))),(.60,.10,.08),'hardware')

# DAVIS reference geometry: published overall envelope, simplified internal arrangement.
# H56 x W62 x D28, optical axis approximately 33.25 above underside.
# Detailed ports, lens and exact mount engagement must be checked on actual unit.
front=box(55,8,56,0,10,CAM_BOTTOM)
boss=box(14,20,8,0,-.5,CAM_BOTTOM)
boss=hole(boss,0,-.5,2.8,z=CAM_BOTTOM-.1,h=6.1)
body=front.union(boss)
add('REF_DAVIS240C_Housing_Simplified',camera_pose(body),DARK,'reference')
rear=box(62,1.75,56,0,-13.125,CAM_BOTTOM)
mid=box(55,1.6,45,0,-4,CAM_BOTTOM+11)
add('REF_DAVIS240C_Boards_Simplified',camera_pose(rear.union(mid)),(.10,.36,.22),'reference')
lens=cyl(15.5,6,0,14,ZOPT,(0,1,0)).union(cyl(16,29,0,20,ZOPT,(0,1,0)))
add('REF_Lens_Envelope_TBC',camera_pose(lens),(.13,.15,.17),'reference')
add('REF_Lens_Front_Glass',camera_pose(cyl(11,.3,0,49,ZOPT,(0,1,0))),(.12,.28,.36),'reference')
camera=camera_pose(body.union(rear).union(mid).union(lens))
# Object half is one printed solid: lower base, pedestal and printed studs.
GREEN=(.18,.57,.43)
obj=box(240,220,8,y=220).edges('|Z').fillet(4)
for x in [-70,70]:
    obj=obj.cut(box(28.6,20.6,4.4,x,120,-.1))
    obj=hole(obj,x,120,2.25,z=-1,h=10)
obj=obj.union(box(18,18,50.5,0,225,8))
for x in [-4,4]:
    for y in [221,229]:obj=obj.union(cyl(2.4,1.8,x,y,58.5))
add('07_Object_Base_With_Studded_Pedestal',obj,GREEN)
# Real plate has simplified underside sockets to show how it engages the printed studs.
plate=box(15.8,15.8,3.2,0,225,58.5)
for x in [-4,4]:
    for y in [221,229]:
        plate=hole(plate,x,y,2.45,z=58.4,h=2)
        plate=plate.union(cyl(2.4,1.8,x,y,61.7))
add('REF_Real_LEGO_Plate_Approximate',plate,(.64,.66,.67),'reference')
# Simple 40 mm target mannequin only; not an accurate minifigure CAD reproduction.
feet=box(6.5,7.8,12, -4,225,61.7).union(box(6.5,7.8,12,4,225,61.7))
for x in [-4,4]:feet=hole(feet,x,225,2.5,z=61.6,h=2.1)
# Back-row plate studs carry feet. Target faces toward the camera (negative Y).
feet=feet.translate((0,4,0))
add('REF_Minifigure_Legs_Approximate',feet,(.13,.30,.68),'reference')
torso=box(15,8,14,0,229,73.7)
for x in [-10.5,10.5]:torso=torso.union(cyl(2.8,12,x,229,75.7))
add('REF_Minifigure_Torso_Approximate',torso,(.8,.13,.10),'reference')
head=cyl(5,10,0,229,87.7).union(cyl(2.4,1.8,0,229,97.7))
for x in [-10.5,10.5]:head=head.union(cyl(2.7,3,x,229,72.7))
add('REF_Minifigure_Head_Hands_Approximate',head,(.98,.74,.10),'reference')

# Visible generic fastener envelopes; no threads, tool recesses or certification.
def nut_z(x,y,z,across_flats,thick,bore_r):
    n=cq.Workplane('XY').center(x,y).polygon(6,across_flats/math.cos(math.pi/6)).extrude(thick).translate((0,0,z))
    return hole(n,x,y,bore_r,z=z-.1,h=thick+.2)
for i,(x,y) in enumerate(foot_holes,1):
    screw=cyl(1.95,17.7,x,y,2.3).union(cq.Workplane('XY').newObject([cq.Solid.makeCone(4.4,1.95,2.3,cq.Vector(x,y,0),cq.Vector(0,0,1))]))
    washer=hole(cyl(4.5,.8,x,y,14),x,y,2.2,z=13.9,h=1)
    nut=nut_z(x,y,14.8,7.,3.2,2.1)
    add(f'REF_Base_Fixing_{i:02}',cq.Workplane('XY').newObject([cq.Compound.makeCompound([screw.val(),washer.val(),nut.val()])]),METAL,'fastener')
# Short camera tripod screw envelope; verify thread/engagement on physical unit.
tripod=cyl(3.05,9,0,-.5,CAM_BOTTOM-6).union(cyl(6,4,0,-.5,CAM_BOTTOM-10))
add('REF_Camera_Quarter_Inch_Screw_TBC',camera_pose(tripod),METAL,'fastener')
for i,x in enumerate([-70,70],1):
    screw=cyl(1.95,10.75,x,120,2.25).union(cq.Workplane('XY').newObject([cq.Solid.makeCone(4.4,1.95,2.25,cq.Vector(x,120,0),cq.Vector(0,0,1))]))
    washer=hole(cyl(4.5,.8,x,120,8),x,120,2.2,z=7.9,h=1)
    nut=nut_z(x,120,8.8,7,3.2,2.1)
    add(f'REF_Joining_M4_Fixing_{i}',cq.Workplane('XY').newObject([cq.Compound.makeCompound([screw.val(),washer.val(),nut.val()])]),METAL,'fastener')
for i,dx in enumerate([-8.6,19.4],1):
    screw=cyl(.95,8,SX+dx,SY,48).union(cyl(1.9,1.5,SX+dx,SY,56))
    add(f'REF_Servo_Ear_Screw_{i:02}_TBC',screw,METAL,'fastener')
for i,dx in enumerate([-12,12],1):
    screw=cyl(1.45,30,dx,0,62.8).union(cyl(2.75,3,dx,0,92.8))
    nut=nut_z(dx,0,63.1,5.5,2.4,1.6)
    add(f'REF_Clamp_M3_Fixing_{i:02}',laser_pose(cq.Workplane('XY').newObject([cq.Compound.makeCompound([screw.val(),nut.val()])])),METAL,'fastener')
for i,dy in enumerate([-6,6],1):
    screw=cyl(.95,5,0,dy,62.5).union(cyl(1.8,1.8,0,dy,67.5))
    add(f'REF_Horn_to_Cradle_Screw_{i:02}_TBC',laser_pose(screw),METAL,'fastener')
centre_screw=cyl(1.15,6,0,0,59.5).union(cyl(2.1,1.5,0,0,65.5))
add('REF_Horn_Centre_Screw_TBC',laser_pose(centre_screw),METAL,'fastener')

camera_overlap=cam.val().intersect(camera.val()).Volume()
assert camera_overlap<.01
clashes=[]
for i,(n,s) in enumerate(custom):
    for m,t in custom[i+1:]:
        overlap=s.val().intersect(t.val()).Volume()
        if overlap>.01:clashes.append([n,m,overlap])
assert not clashes,clashes
assy.save(str(OUT/'DAVIS240C_Scanner_Review.step'))
check=cq.importers.importStep(str(OUT/'DAVIS240C_Scanner_Review.step'))
assert check.val().isValid()
expected=sum(len(s.solids().vals()) for _,s,_,_ in parts)
assert len(check.solids().vals())==expected
report=dict(valid=True,solid_count=expected,custom_part_count=len(custom),camera_mount_overlap_mm3=camera_overlap,custom_part_clashes=clashes,camera_yaw_deg=CAM_YAW,laser_yaw_deg=LASER_YAW,reference_target_xy_mm=TARGET,base_footprint_mm=[240,440],camera_envelope_mm=[62,28,56],provisional_lens_front_distance_mm=round(math.hypot(CX,TARGET[1]-CY)-49,2),components=rows)
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
from render_review import render
render(parts,OUT,0,0)
print(json.dumps({'valid':True,'solids':expected,'custom_parts':len(custom)}))
