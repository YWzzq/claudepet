#!/usr/bin/env python3
"""Generate V5.1 static and interactive previews from the actual CAD meshes."""
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
for x in (-6.5,6.5):
    ax.add_patch(Rectangle((x-1.2,B.FACE_Z-4),2.4,8,color='#66e0d0'))
ax.annotate('',xy=(B.SCREEN_HOLES_X[0],B.SCREEN_Z0-4),xytext=(B.SCREEN_HOLES_X[1],B.SCREEN_Z0-4),arrowprops=dict(arrowstyle='<->',color='#dce4ee'))
ax.text(B.PCB_CX,B.SCREEN_Z0-7,'孔距 38.72 mm',ha='center',color='#dce4ee')
ax.annotate('',xy=(B.PCB_X1+6,B.SCREEN_HOLES_Z[0]),xytext=(B.PCB_X1+6,B.SCREEN_HOLES_Z[1]),arrowprops=dict(arrowstyle='<->',color='#dce4ee'))
ax.text(B.PCB_X1+9,B.FACE_Z,'孔距 27 mm',rotation=90,ha='center',va='center',color='#dce4ee')
ax.text(0,B.FACE_Z-18,'方窗 27.2 mm · 遮住玻璃边缘',ha='center',color='#dce4ee',fontsize=11)
ax.set_xlim(-33,38);ax.set_ylim(20,74);ax.set_aspect('equal');ax.axis('off')
ax.set_title('④ 屏幕定位 · 四孔固定，排针朝右',fontsize=14)
fig.suptitle('AgentPet V5.1  |  方块造型 + 可拆后盖',fontsize=23,y=.965)
fig.text(.5,.032,'商品尺寸图驱动 · 连接器为预留包络 · 先打印小型屏幕试装片核对实物',ha='center',color='#aab8c9',fontsize=12)
plt.subplots_adjust(left=.03,right=.96,top=.90,bottom=.08,wspace=.04,hspace=.16)
fig.savefig(B.OUT/'assembly_steps.png')
fig.savefig(B.OUT/'case_preview4.png')
plt.close(fig)
fig=plt.figure(figsize=(9,8),dpi=160)
render(fig.add_subplot(111),'AgentPet V5.1 · 方块桌宠')
plt.subplots_adjust(left=0,right=1,top=.94,bottom=0)
fig.savefig(B.OUT/'case_preview.png')
print('Saved assembly_preview.html, assembly_steps.png, case_preview.png, case_preview4.png')
