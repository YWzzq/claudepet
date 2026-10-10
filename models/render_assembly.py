#!/usr/bin/env python3
"""Generate V5.3 static and interactive previews from the actual CAD meshes."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Rectangle, Circle
import build_case as B

font = '/System/Library/Fonts/Hiragino Sans GB.ttc'
if B.Path(font).exists():
    fm.fontManager.addfont(font)
    plt.rcParams['font.sans-serif'] = ['Hiragino Sans GB']
plt.rcParams.update({'text.color':'#e9edf4', 'axes.titlecolor':'#e9edf4',
                     'font.size':11, 'figure.facecolor':'#141b24', 'savefig.facecolor':'#141b24'})
parts = B.assembly_parts()
B.verify(parts)
data=[]
for k,m in parts.items():
    data.append(dict(name=k, color=B.COLORS.get(k, '#66e0d0' if k.startswith('eye') else '#a6b0bd'),
                     vertices=m.vertices.round(4).tolist(),faces=m.faces.tolist(),
                     normals=m.face_normals.round(4).tolist()))
template=(B.OUT/'assembly_viewer.template.html').read_text()
(B.OUT/'assembly_preview.html').write_text(template.replace('__MODEL_DATA__',json.dumps(data,separators=(',',':'))))


def group(k):
    if k=='front': return 'front'
    if k=='back' or k.startswith('back_screw'): return 'back'
    return 'board' if k.startswith('board_') else 'screen'


def render(ax, title, hidden=(), exploded=False, azim=62):
    # Per-pixel depth testing. Sorting triangles cannot correctly hide hardware
    # behind a perforated front wall, particularly at oblique viewing angles.
    offsets={'front':[0,75,0],'back':[0,-75,0],'screen':[0,0,0],'board':[0,-31,0]}
    yaw=np.deg2rad(90-azim); pitch=np.deg2rad(20)
    cy,sy,cp,sp=np.cos(yaw),np.sin(yaw),np.cos(pitch),np.sin(pitch)
    image_w,image_h=1100,850
    bg=np.array([25,35,47],dtype=np.uint8)
    image=np.broadcast_to(bg,(image_h,image_w,3)).copy()
    depth=np.full((image_h,image_w),-np.inf)
    projected=[]
    for k,m in parts.items():
        if group(k) in hidden: continue
        v=m.vertices.copy()
        if exploded: v+=offsets[group(k)]
        v[:,2]-=37
        p=np.column_stack((v[:,0]*cy-v[:,1]*sy,
            -v[:,0]*sy*sp-v[:,1]*cy*sp+v[:,2]*cp,
            v[:,0]*sy*cp+v[:,1]*cy*cp+v[:,2]*sp))
        projected.append((k,m,p))
    allp=np.concatenate([p for _,_,p in projected])
    low,high=allp[:,:2].min(axis=0),allp[:,:2].max(axis=0)
    scale=.84*min(image_w/(high[0]-low[0]),image_h/(high[1]-low[1]))
    centre=(low+high)/2
    for k,m,p in projected:
        p[:,0]=(p[:,0]-centre[0])*scale+image_w/2
        p[:,1]=image_h/2-(p[:,1]-centre[1])*scale
        rgb=np.array(matplotlib.colors.to_rgb(B.COLORS.get(k,'#66e0d0' if k.startswith('eye') else '#a6b0bd')))
        for f,n in zip(m.faces,m.face_normals):
            if n[0]*sy*cp+n[1]*cy*cp+n[2]*sp<=1e-7: continue
            t=p[f]
            x0=max(0,int(np.floor(t[:,0].min())));x1=min(image_w-1,int(np.ceil(t[:,0].max())))
            y0=max(0,int(np.floor(t[:,1].min())));y1=min(image_h-1,int(np.ceil(t[:,1].max())))
            if x0>x1 or y0>y1: continue
            x,y=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
            den=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(den)<1e-9: continue
            a=((t[1,1]-t[2,1])*(x-t[2,0])+(t[2,0]-t[1,0])*(y-t[2,1]))/den
            b=((t[2,1]-t[0,1])*(x-t[2,0])+(t[0,0]-t[2,0])*(y-t[2,1]))/den
            c=1-a-b
            z=a*t[0,2]+b*t[1,2]+c*t[2,2]
            region=depth[y0:y1+1,x0:x1+1]
            mask=(a>=-1e-8)&(b>=-1e-8)&(c>=-1e-8)&(z>region)
            light=.68+.35*max(0,n[0]*.25+n[1]*.5+n[2]*.7)
            image[y0:y1+1,x0:x1+1][mask]=np.clip(rgb*light*255,0,255).astype(np.uint8)
            region[mask]=z[mask]
    ax.imshow(image)
    ax.set_title(title,fontsize=14,pad=10);ax.axis('off')


fig=plt.figure(figsize=(14,11),dpi=150)
render(fig.add_subplot(221),'① 完整外观 · 屏幕就是脸')
render(fig.add_subplot(222),'② 背面打开 · 屏幕在前，主控在底层',hidden=('back',),azim=-63)
render(fig.add_subplot(223),'③ 零件展开 · 屏幕先装，主控后装',exploded=True,azim=8)
ax=fig.add_subplot(224);ax.set_facecolor('#19232f')
ax.add_patch(Rectangle((B.PCB_X0,B.SCREEN_Z0),B.SCREEN_L,B.SCREEN_W,color='#24629b'))
ax.add_patch(Rectangle((-B.WINDOW/2,B.FACE_Z-B.WINDOW/2),B.WINDOW,B.WINDOW,color='#111920'))
for x in B.SCREEN_HOLES_X:
    for z in B.SCREEN_HOLES_Z:
        ax.add_patch(Circle((x,z),1.0,color='#dce4ee'))
for z in B.PIN_ZS:
    ax.add_patch(Rectangle((B.PIN_X-B.PIN_PAD_SIZE/2,z-B.PIN_PAD_SIZE/2),
                          B.PIN_PAD_SIZE,B.PIN_PAD_SIZE,color='#d9c69b'))
for x in (-6.5,6.5):
    ax.add_patch(Rectangle((x-1.2,B.FACE_Z-4),2.4,8,color='#66e0d0'))
ax.annotate('',xy=(B.SCREEN_HOLES_X[0],B.SCREEN_Z0-4),xytext=(B.SCREEN_HOLES_X[1],B.SCREEN_Z0-4),arrowprops=dict(arrowstyle='<->',color='#dce4ee'))
ax.text(B.PCB_CX,B.SCREEN_Z0-7,'孔距 38.72 mm',ha='center',color='#dce4ee')
ax.annotate('',xy=(B.PCB_X1+6,B.SCREEN_HOLES_Z[0]),xytext=(B.PCB_X1+6,B.SCREEN_HOLES_Z[1]),arrowprops=dict(arrowstyle='<->',color='#dce4ee'))
ax.text(B.PCB_X1+9,B.FACE_Z,'孔距 27 mm',rotation=90,ha='center',va='center',color='#dce4ee')
ax.text(0,B.FACE_Z-18,'方窗 27.2 mm · 遮住玻璃边缘',ha='center',color='#dce4ee',fontsize=11)
ax.set_xlim(-33,38);ax.set_ylim(20,74);ax.set_aspect('equal');ax.axis('off')
ax.set_title('④ 屏幕定位 · 四孔固定，排针朝右',fontsize=14)
fig.suptitle('AgentPet V5.3  |  方块造型 + 可拆后盖',fontsize=23,y=.965)
fig.text(.5,.032,'商品尺寸图驱动 · 连接器为预留包络 · 先打印小型屏幕试装片核对实物',ha='center',color='#aab8c9',fontsize=12)
plt.subplots_adjust(left=.03,right=.96,top=.90,bottom=.08,wspace=.04,hspace=.16)
fig.savefig(B.OUT/'assembly_steps.png')
fig.savefig(B.OUT/'case_preview4.png')
plt.close(fig)

# Compare locator outlines at the corner identified by the print shop.
# Reconstruct only the previous circular-cut lip for the comparison image.
from matplotlib.collections import PolyCollection
lw,lh=2*(B.INNER_X-B.CLEARANCE),B.CEILING-B.FLOOR-2*B.CLEARANCE
old_lip=B.subtract(B.box(lw,B.LIP_D+.02,lh,y=B.REAR+B.LIP_D/2-.01,
                         z=B.FLOOR+B.CLEARANCE),
    [B.box(lw-2*B.LIP_T,B.LIP_D+2,lh-2*B.LIP_T,y=B.REAR+1,
           z=B.FLOOR+B.CLEARANCE+B.LIP_T)])
old_lip=B.subtract(old_lip,[B.cylinder_y(x,B.REAR+1,z,4,4)
                          for x in B.BACK_HOLES_X for z in B.BACK_HOLES_Z])
fig,axes=plt.subplots(1,2,figsize=(11,6),dpi=160)
for ax,lip,title in zip(axes,[old_lip,B.build_back_lip()],
    ['V5.2 圆形避让 · 残留小凸块','V5.3 方形避让 · 平头定位边']):
    ax.set_facecolor('#19232f')
    ax.add_patch(Rectangle((-B.W/2,B.LEG_H),B.W,B.H-B.LEG_H,
                           color='#465360'))
    faces=lip.triangles[lip.face_normals[:,1]>.99]
    ax.add_collection(PolyCollection(faces[:,:,[0,2]],facecolor='#f7a44c',
                                     edgecolor='none'))
    ax.add_patch(Circle((32.5,67.5),1.15,color='#141b24'))
    ax.set_xlim(26.5,38.5);ax.set_ylim(61.5,74.5)
    ax.set_aspect('equal');ax.set_title(title,fontsize=14,pad=15)
    ax.set_xlabel('X / mm',color='#aab8c9');ax.set_ylabel('Z / mm',color='#aab8c9')
    ax.tick_params(colors='#aab8c9')
axes[0].annotate('1.61 × 0.95 mm',xy=(34.9,70.9),xytext=(28,73),
                 color='#ffffff',fontsize=11,
                 arrowprops=dict(arrowstyle='->',color='#ff7979'))
axes[1].annotate('定位边宽 1.4 mm\n端部平直',xy=(28.5,70.6),xytext=(29.5,72.2),
                 color='#ffffff',fontsize=11,
                 arrowprops=dict(arrowstyle='->',color='#90dfbc'))
axes[1].annotate('小凸块已移除',xy=(34.9,70.9),xytext=(30,63),
                 color='#ffffff',fontsize=11,
                 arrowprops=dict(arrowstyle='->',color='#90dfbc'))
fig.suptitle('后盖定位边修正 · 局部放大',fontsize=19,y=.98)
fig.text(.5,.025,'橙色：凸起定位边  |  灰色：后盖底板  |  四个螺丝孔及单边 0.30 mm 配合间隙不变',
         ha='center',fontsize=10,color='#aab8c9')
fig.subplots_adjust(left=.07,right=.96,bottom=.15,top=.86,wspace=.26)
fig.savefig(B.OUT/'rear_lip_revision.png');plt.close(fig)
fig=plt.figure(figsize=(9,8),dpi=160)
render(fig.add_subplot(111),'AgentPet V5.3 · 方块桌宠')
plt.subplots_adjust(left=0,right=1,top=.94,bottom=0)
fig.savefig(B.OUT/'case_preview.png')
print('Saved assembly_preview.html, assembly_steps.png, case_preview.png, case_preview4.png')

# Dimensioned section schematic: glass and header occupy different areas of
# the PCB. Their heights are shown together here to explain the shared glass and pin clearance.
fig,ax=plt.subplots(figsize=(10,6),dpi=160)
ax.set_facecolor('#19232f')
ax.add_patch(Rectangle((B.PCB_BACK,0),B.PCB_T,17,color='#24629b'))
ax.add_patch(Rectangle((B.PCB_FRONT,2),B.GLASS_RISE,7,color='#303b49'))
ax.add_patch(Rectangle((B.PCB_FRONT,12),B.PIN_FRONT_HEIGHT,1.8,color='#d9c69b'))
ax.add_patch(Rectangle((B.FRONT-B.WALL,0),B.WALL,17,color='#f18329'))
ax.text(B.PCB_BACK+.6,16,'PCB',ha='center',color='#dce4ee')
ax.text(B.PCB_FRONT+1,6,'玻璃',rotation=90,ha='center',va='center')
ax.text(B.FRONT-.6,8,'前壳',rotation=90,ha='center',va='center',color='#1c242d')
ax.text(B.PCB_FRONT,14.4,'短针脚 / 焊点：上限按玻璃高 2.0 mm',fontsize=11)
def dim(left,right,y,label):
    ax.annotate('',xy=(left,y),xytext=(right,y),
                arrowprops=dict(arrowstyle='<->',color='#e9edf4'))
    ax.text((left+right)/2,y+.45,label,ha='center',fontsize=11)
dim(B.PCB_FRONT+B.PIN_FRONT_HEIGHT,B.FRONT-B.WALL,10,'余量 0.6 mm')
dim(B.PCB_FRONT,B.FRONT-B.WALL,19,'现有可用高度 2.6 mm')
dim(B.PCB_BACK,B.GLASS_FRONT,-2,'屏幕总厚 3.2 mm')
ax.text(B.PCB_FRONT,1,'玻璃高 2.0 mm · PCB 厚 1.2 mm',fontsize=10)
ax.text(B.FRONT-B.WALL/2,18,'前壁厚度\n2.4 mm',ha='center',fontsize=10)
ax.set_xlim(B.PCB_BACK-1,B.FRONT+1);ax.set_ylim(-4,21)
ax.set_aspect(.25);ax.axis('off')
ax.set_title('V5.3 · 玻璃与短针脚间隙（局部剖面示意）',fontsize=17,pad=15)
fig.text(.5,.035,'用户确认针脚低于玻璃面；按玻璃高度核对，共用已有 0.6 mm 间隙。',
         ha='center',color='#aab8c9',fontsize=10)
fig.subplots_adjust(left=.06,right=.96,top=.86,bottom=.12)
fig.savefig(B.OUT/'screen_pin_clearance.png')
plt.close(fig)
