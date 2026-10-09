#!/usr/bin/env python3
"""Hardware models and virtual assembly, using the supplied seller drawings.

Dimensioned outlines/pitches come from build_case.py. Unspecified pin sections,
connector housings and component heights are visual approximations. Connector
heights use the same allowances as the existing enclosure fit audit.
"""
import json
import numpy as np
import trimesh
import build_case as B

OUT = B.OUT


def combined(meshes):
    return trimesh.util.concatenate(list(meshes))


def hardware():
    screen = B.screen_parts()
    screen.pop('screen_connector')
    screen.pop('screen_pin_tips')
    # 11.30 mm is the full header span in the side drawing, not the Dupont body.
    back_pin_length = 11.30 - B.PCB_T - B.GLASS_RISE
    screen['screen_pins'] = combined(B.box(.64,11.30,.64,B.PIN_X,
        (B.PCB_BACK-back_pin_length+B.PCB_FRONT+B.GLASS_RISE)/2,z-.32)
        for z in B.PIN_ZS)
    screen['screen_header_plastic'] = combined(B.box(2.54,2.5,2.54,B.PIN_X,
        B.PCB_BACK-1.25,z-1.27) for z in B.PIN_ZS)
    screen['screen_solder'] = combined(B.cylinder_y(B.PIN_X,B.PCB_FRONT+.25,z,.9,.5)
                                         for z in B.PIN_ZS)
    screen['screen_dupont'] = combined(B.box(2.44,11,2.44,B.PIN_X,
        B.PCB_BACK-10.5,z-1.22) for z in B.PIN_ZS)

    board = B.board_parts()
    board.pop('board_leads')
    # 53.34 / 2.54 = 21 intervals, hence 22 pins per row, 44 total.
    pcb_left = B.BOARD_X+B.BOARD_L/2-B.BOARD_PCB_L
    xs = pcb_left+(B.BOARD_PCB_L-53.34)/2+np.arange(22)*2.54
    ys = [B.BOARD_Y-12.7,B.BOARD_Y+12.7]
    centers = [(float(x),y) for x in xs for y in ys]
    holes = [trimesh.creation.cylinder(radius=.5,height=B.BOARD_T+.2,
        transform=trimesh.transformations.translation_matrix([x,y,B.BOARD_Z+B.BOARD_T/2]))
        for x,y in centers]
    board['board_pcb'] = B.subtract(board['board_pcb'],holes)
    board['board_pins'] = combined(B.box(.64,.64,B.PIN_BELOW+B.BOARD_T+8,
        x,y,B.BOARD_Z-B.PIN_BELOW) for x,y in centers)
    board['board_header_plastic'] = combined(B.box(2.44,2.54,2.5,
        x,y,B.BOARD_Z+B.BOARD_T) for x,y in centers)
    # These purple strips represent available female-plug space,
    # not a claim that every one of the board's 44 pins has a wire attached.
    board['board_plug_space'] = combined(B.box(53.34+2.54,2.54,5.8,
        B.BOARD_X+(B.BOARD_L-B.BOARD_PCB_L)/2,y,B.BOARD_Z+B.BOARD_T+8.2) for y in ys)
    sockets=[]
    for sign in (-1,1):
        x=B.BOARD_X+B.BOARD_L/2-3.5; y=B.BOARD_Y+sign*6
        sockets.append(B.subtract(B.box(7,9,3.2,x,y,B.BOARD_Z+B.BOARD_T),
            [B.box(7,6.8,2.2,x+1,y,B.BOARD_Z+B.BOARD_T+.5)]))
    board['board_usb'] = combined(sockets)
    colors = dict(B.COLORS, screen_pins='#d9c69b', screen_solder='#c9cdd3',
        screen_header_plastic='#20242c', screen_dupont='#383c46',
        board_pins='#d9c69b', board_header_plastic='#20242c',board_plug_space='#766496')
    return screen,board,colors


def save_glb(name, parts, colors, centered=False):
    scene=trimesh.Scene()
    scene.metadata['units']='mm'
    for key,mesh in parts.items():
        m=mesh.copy()
        m.visual.vertex_colors=trimesh.visual.color.hex_to_rgba(colors.get(key,'#a6b0bd'))
        scene.add_geometry(m,geom_name=key,node_name=key)
    if centered:
        scene.apply_translation(-scene.bounds.mean(axis=0))
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    scene.export(OUT/name)
    loaded=trimesh.load(OUT/name)
    assert len(loaded.geometry)==len(parts)
    assert all(m.is_volume for m in loaded.geometry.values())


def audit(parts,screen,board):
    s=B.union(list(screen.values())); b=B.union(list(board.values()))
    checks=[]
    def check(label,value):
        checks.append(dict(check=label,passed=value<1e-3,intersection_mm3=round(value,6)))
    for shell in ('front','back'):
        for name,meshes in [('screen',screen),('board',board)]:
            for key,m in meshes.items():
                check(f'{shell} / {key}',B.overlap(parts[shell],m))
    check('screen / board',B.overlap(s,b))
    for name,moving,obstacles in [('screen first',s,[parts['front']]),
        ('board second',b,[parts['front'],s]),
        ('back last',parts['back'],[parts['front'],s,b])]:
        worst=0.
        for dy in np.linspace(-80,0,81):
            m=moving.copy();m.apply_translation([0,dy,0])
            worst=max(worst,*(B.overlap(m,o) for o in obstacles))
        check(name+' insertion sweep',worst)
    report=dict(all_checks_pass=all(c['passed'] for c in checks),checks=checks,
        units='mm',dimensions=dict(screen_pcb=[43.72,32,1.2],screen_glass_rise=2.,
        screen_hole_pitch=[38.72,27],screen_hole_diameter=2.,screen_pins=8,
        screen_pin_pitch=2.54,board_pcb=[57.15,27.94],board_with_antenna=[B.BOARD_L,27.94],
        board_pin_row_pitch=25.4,board_pin_length_span=53.34,board_pins_per_row=22),
        clearances_mm=dict(glass_to_front_wall=.6,board_right_to_wall=round(B.INNER_X-B.BOARD_X-B.BOARD_L/2,3),
        board_lower_pins_to_floor=round(B.BOARD_Z-B.PIN_BELOW-B.FLOOR,3),
        board_plug_to_screen_plug_z=2.64,usb_recess=round(B.W/2-B.BOARD_X-B.BOARD_L/2,3)),
        approximations=['Pin section, pad/hole diameter for board visualisation.',
        'Board PCB thickness 1.2 mm is assumed; not specified in supplied board drawing.',
        'USB socket shape/spacing, RF shield and antenna widths/heights are illustrative.',
        'Dupont body geometry and cable bend are not dimensioned in the supplied drawings.',
        'Side drawing 3.2 mm screen thickness used; seller table says 2.58 mm.',
        'PCB contact with a mounting post is intentional; screws self-tap into pilot holes.'],
        physical_fit_verified=False)
    (OUT/'hardware_fit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    assert report['all_checks_pass'], 'Detailed hardware collision detected'
    return report


def preview(parts,colors,report):
    template=(OUT/'assembly_viewer.template.html').read_text()
    template=template.replace('V5.2 装配预览','硬件尺寸与试拼').replace('方块桌宠 · 装配预览','屏幕与主控 · 虚拟试拼')
    template=template.replace('把屏幕、主控与外壳放在同一个模型里。拖动查看位置，展开查看每个零件。',
        '按你提供的尺寸图生成：屏幕四孔、8 针排针、主控 22 × 2 针排针与双 USB。可分步试拼。')
    template=template.replace('<h2>查看方式</h2>',
        '<h2>分步试拼</h2><div class="buttons"><button data-fit="0">散件</button><button data-fit="1">装屏幕</button><button data-fit="2">放主控</button><button data-fit="3">合后盖</button></div><h2>单独看硬件</h2><div class="buttons"><button id="onlyScreen">屏幕模型</button><button id="onlyBoard">开发板模型</button></div><h2>查看方式</h2>')
    template=template.replace('商品图与实物尺寸可能有差别，先打印屏幕试装片，核对四孔、窗口和短螺丝，再打印整壳。',
        'PCB 外形、屏幕孔位和排针间距来自尺寸图；USB 口细节、元件高度与杜邦母头为示意。紫色长条表示主控插头空间。此模型用于试拼，不需要打印电子件。')
    template=template.replace('const offsets={','let fitStage=null;\nconst offsets={')
    template=template.replace("document.getElementById('explode').oninput=e=>{explosion",
                              "document.getElementById('explode').oninput=e=>{fitStage=null;explosion")
    template=template.replace('function project(v,g){let o=offsets[g],',
        '''function displacement(g){if(fitStage===null)return offsets[g].map(v=>v*explosion);
return {front:[0,0,0],screen:[0,fitStage<1?-45:0,0],board:[0,fitStage<2?-70:0,0],back:[0,fitStage<3?-100:0,0]}[g];}
function project(v,g){let o=displacement(g),''')
    template=template.replace('o[0]*explosion','o[0]').replace('o[1]*explosion','o[1]').replace('o[2]*explosion','o[2]')
    template=template.replace('const o=offsets[m.group]','const o=displacement(m.group)')
    template=template.replace("function setMode(mode){","function setMode(mode){fitStage=null;")
    extra='''
for(const el of document.querySelectorAll('[data-fit]'))el.onclick=()=>{
setMode('exploded');fitStage=Number(el.dataset.fit);yaw=2.55;pitch=.35;zoom=.75;
document.getElementById('viewTitle').textContent=['散件 · 从后面装入','① 屏幕已装入','② 主控已放入','③ 后盖已合拢'][fitStage];
document.getElementById('badge').textContent=document.getElementById('viewTitle').textContent;
document.getElementById('caption').textContent='蓝色屏幕四孔与前壳螺柱对齐，绿色主控横放底层，双 USB 朝右；先屏幕、再主控、后盖最后。';draw();};
function hardwareOnly(key){setMode('inside');for(const g of Object.keys(groups))groups[g].visible=g===key;
for(const el of document.querySelectorAll('[data-group]'))el.checked=groups[el.dataset.group].visible;
yaw=key==='screen'?.3:2.2;pitch=key==='screen'?.22:1.05;zoom=1.65;
document.getElementById('viewTitle').textContent=key==='screen'?'屏幕 · 32 × 43.72 mm PCB':'主控 · 含天线 63.39 × 27.94 mm';
document.getElementById('badge').textContent=document.getElementById('viewTitle').textContent;draw();}
document.getElementById('onlyScreen').onclick=()=>hardwareOnly('screen');
document.getElementById('onlyBoard').onclick=()=>hardwareOnly('board');
setMode('rear');
'''
    template=template.replace('resize();\n</script>',extra+'resize();\n</script>')
    template=template.replace('<h2>打印与模型文件</h2>',
        '<h2>硬件模型下载</h2><div class="downloads"><a class="file" download href="screen_hardware.glb">屏幕 GLB</a><a class="file" download href="esp32_s3_hardware.glb">开发板 GLB</a><a class="file" download href="hardware_fit_assembly.glb">试拼装配 GLB</a><a class="file" href="hardware_fit_report.json">试拼检查报告</a></div><h2>打印与模型文件</h2>')
    data=[dict(name=k,color=colors.get(k,'#a6b0bd'),vertices=m.vertices.round(4).tolist(),
               faces=m.faces.tolist(),normals=m.face_normals.round(4).tolist()) for k,m in parts.items()]
    (OUT/'hardware_fit_preview.html').write_text(template.replace('__MODEL_DATA__',json.dumps(data,separators=(',',':'))))


def images(parts,screen,board,colors):
    # Reuse the enclosure preview's depth renderer; no new hand-drawn 3D shapes.
    import render_assembly as R
    import matplotlib.pyplot as plt
    R.parts=parts;B.COLORS.update(colors)
    fig=plt.figure(figsize=(15,10),dpi=150)
    R.parts=screen;R.render(fig.add_subplot(221),'① 屏幕 · 32 × 43.72 mm，8 针，玻璃面凸出 2 mm',azim=68)
    R.parts=board;R.render(fig.add_subplot(222),'② 主控 · 含天线 63.39 × 27.94 mm，双 USB',azim=45)
    R.parts=parts;R.render(fig.add_subplot(223),'③ 试拼 · 屏幕四孔对齐，主控横放，USB 朝右',hidden=('back',),azim=-63)
    R.render(fig.add_subplot(224),'④ 展开 · 先屏幕，再主控，最后后盖',exploded=True,azim=8)
    fig.suptitle('按商品尺寸图生成的硬件模型与虚拟装配',fontsize=21,y=.97)
    fig.text(.5,.025,'PCB / 孔距 / 排针间距来自尺寸图；接插件外形与元件高度为示意，导线未建模。',ha='center',color='#aab8c9')
    fig.subplots_adjust(left=.02,right=.98,top=.91,bottom=.07,hspace=.2,wspace=.04)
    fig.savefig(OUT/'hardware_fit_overview.png');plt.close(fig)


def main():
    screen,board,colors=hardware()
    parts=B.assembly_parts()
    parts={k:v for k,v in parts.items() if not k.startswith(('screen_','board_')) or 'screw' in k}
    parts.update(screen);parts.update(board)
    report=audit(parts,screen,board)
    save_glb('screen_hardware.glb',screen,colors,centered=True)
    save_glb('esp32_s3_hardware.glb',board,colors,centered=True)
    save_glb('hardware_fit_assembly.glb',parts,colors)
    preview(parts,colors,report)
    images(parts,screen,board,colors)
    print(f'Hardware models saved; {len(report["checks"])} collision/path checks passed.')


if __name__=='__main__':
    main()
