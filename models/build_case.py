#!/usr/bin/env python3
"""AgentPet 外壳 V4 —— 像素风 Clawd 吉祥物造型(站立小方蟹)。

剪影: 8×8 像素格(格 10mm) → 80×80×38.8mm
  z0-10 双腿 | z10-20 身体 | z20-40 两侧钳臂 | z40-60 身体 | z60-80 顶部呆毛
内部(从背面像素大开口装配):
  板子横卧底层(热熔胶粘底, USB 朝右壁开口)
  屏幕横置: 下缘坐托架, 4 孔对准 4 条侧壁托臂, M2×6 自攻锁死
  窗口 28.22mm 只露显示区(27.72), PCB 边缘全隐藏
背板: 同剪影像素盖板(带 2 个像素通风孔), 背面嵌入
"""
import numpy as np
import trimesh

CELL = 10.0
D = 38.8
wall = 2.4

# 像素剪影: 行自底向上(z), 每行 = 填充列号(0~7, x 自 -40 起)
ROWS = [
    {1, 6},                      # z 0-10   双腿
    set(range(1, 7)),            # z 10-20  身体下段
    set(range(0, 8)),            # z 20-30  钳臂
    set(range(0, 8)),            # z 30-40  钳臂
    set(range(1, 7)),            # z 40-50  身体
    set(range(1, 7)),            # z 50-60  身体
    {6},                         # z 60-70  呆毛
    {6},                         # z 70-80  呆毛尖
]
NCOLS = 8
TOTAL_H = len(ROWS) * CELL                  # 80
X0 = -CELL * NCOLS / 2                      # -40

# 内腔(顶部开放, 背面由像素开口盖板封闭)
cav_x0, cav_x1 = -27.6, 27.6
cav_y0, cav_y1 = -17.0, 17.0
cav_z0 = CELL + floor_t if (floor_t := 2.4) else 12.4   # 12.4
cav_z1 = TOTAL_H - 3.0                                   # 77

# 屏幕(横置, 官方尺寸)
spcb_l, spcb_h, spcb_t = 43.72, 31.52, 2.0
view_w = 27.72
pcb_x0 = cav_x0 + (cav_x1 - cav_x0 - spcb_l) / 2        # 6.14
pcb_x1 = pcb_x0 + spcb_l                                 # 49.86
screen_z0 = 16.2                                         # 屏底(坐托架上)
pcb_cz = screen_z0 + spcb_h / 2                          # 31.96

# 显示区 AA 与窗口(AA 偏向非排针端: 端部6.0, 两侧2.14)
aa_x0, aa_x1 = pcb_x0 + 6.0, pcb_x0 + 6.0 + view_w       # -10.14..17.58? 见下
aa_x0 = pcb_x0 + 6.0                                     # 12.14
aa_x1 = aa_x0 + view_w                                   # 39.86
aa_z0, aa_z1 = screen_z0 + 2.14, screen_z0 + 2.14 + view_w  # 18.34..46.06
win_size = view_w + 0.5                                  # 28.22
win_cx = (aa_x0 + aa_x1) / 2 - 0.25                      # 25.75
win_cz = (aa_z0 + aa_z1) / 2                             # 32.2
win_z0 = win_cz - win_size / 2                           # 18.09

# 螺丝孔位(横置后): 沿长度 ±19.36, 沿高度 ±13.26
hole_xs = (pcb_x0 + 2.5, pcb_x1 - 2.5)                   # 8.64 / 47.36
hole_zs = (pcb_cz - (spcb_h / 2 - 2.5), pcb_cz + (spcb_h / 2 - 2.5))  # 18.7 / 45.22

# 板子
board_l, board_d, board_t = 53.34, 27.94, 1.8
board_cx, board_cy = 0.0, 0.0
board_z0 = cav_z0                                        # 12.4
usb_cz = board_z0 + board_t + 1.8                        # 15.7
usb_slot_w, usb_slot_h = 12.0, 7.0


def box_at(w, d, h, x, y, z):
    """中心(x,y), 底(z)的长方体。"""
    return trimesh.creation.box(
        extents=[w, d, h],
        transform=trimesh.transformations.translation_matrix([x, y, z + h / 2]))


def silhouette_prism(depth, inset=0.0, y_center=0.0):
    """像素剪影沿 Y 挤出(逐行合并连续列)。inset<0 = 外扩。"""
    parts = []
    for ri, cols in enumerate(ROWS):
        runs, start = [], None
        for c in range(NCOLS + 1):
            filled = c in cols
            if filled and start is None:
                start = c
            if not filled and start is not None:
                runs.append((start, c))
                start = None
        for c0, c1 in runs:
            x0 = X0 + c0 * CELL - inset
            x1 = X0 + c1 * CELL + inset
            z0 = ri * CELL - inset
            parts.append(box_at(x1 - x0, depth, CELL + 2 * inset,
                                (x0 + x1) / 2, y_center, z0))
    return trimesh.util.concatenate(parts)


SEG = 48


def cyl_y(x, y_center, z, r, length):
    return trimesh.creation.cylinder(
        radius=r, height=length, sections=SEG,
        transform=trimesh.transformations.rotation_matrix(
            np.pi / 2, [1, 0, 0], [x, y_center, z]))


def build_shell():
    outer = silhouette_prism(D)
    cavity = box_at(cav_x1 - cav_x0, cav_y1 - cav_y0, cav_z1 - cav_z0 + 2,
                    (cav_x0 + cav_x1) / 2, (cav_y0 + cav_y1) / 2, cav_z0 - 1)
    back_cut = silhouette_prism(2.2, inset=-0.4, y_center=-D / 2 + 1.1)
    shell = outer.difference([cavity, back_cut])

    cuts = [
        # 屏窗(打穿前壁)
        box_at(win_size, wall + 6, win_size, win_cx, D / 2 - 2, win_z0),
        # USB 口(打穿右壁)
        box_at(wall + 14, usb_slot_w, usb_slot_h,
               cav_x1 + wall / 2 + 5, board_cy, usb_cz - usb_slot_h / 2),
    ]
    shell = shell.difference(cuts)

    # 4 条屏幕托臂: 从左右内壁伸到孔位, 前:
    #   y 9.8~13.8 (前缘抵住屏幕背面), M2 底孔 Ø1.7 对准孔位
    for hx in hole_xs:
        for hz, th in ((hole_zs[1], 6.0), (hole_zs[0], 4.4)):
            side = 1 if hx > 0 else -1
            arm_len = (cav_x1 - abs(hx)) + 2.0          # 从壁到孔位再过 2mm
            arm_cx = side * (cav_x1 - arm_len / 2)
            shell = shell.union(box_at(arm_len, 4.0, th, arm_cx, D / 2 - wall - 4.0, hz - th / 2))
            shell = shell.difference(cyl_y(abs(hx), D / 2 - wall - 5.0, hz, 0.85, 8.0))

    # 屏幕托架(前壁悬伸, 托住屏幕下缘)
    shell = shell.union(box_at(spcb_l + 2, 4.0, 2.0,
                               (pcb_x0 + pcb_x1) / 2, D / 2 - wall - 2.0, screen_z0 - 2.0))

    # 板子限位凸台
    for sx in (-1, 1):
        shell = shell.union(box_at(4, 3, 1.5, board_cx + sx * 25.0, board_cy, cav_z0))
    return shell


def build_back():
    plate = silhouette_prism(1.7, inset=0.5, y_center=-D / 2 + 0.85)
    vents = [
        box_at(7, 3.4, 7, -CELL * 1.5, 0, 24),
        box_at(7, 3.4, 7, CELL * 1.5, 0, 24),
    ]
    return plate.difference(vents)


def simple_board():
    return [box_at(board_l, board_d, board_t, board_cx, board_cy, board_z0)]


def simple_screen():
    pcb = box_at(spcb_l, spcb_t, spcb_h,
                 (pcb_x0 + pcb_x1) / 2, D / 2 - wall - spcb_t / 2 - 0.1, screen_z0)
    disp = box_at(view_w, 0.4, view_w, win_cx, D / 2 - wall - 0.2, win_cz - view_w / 2)
    pcb.visual.face_colors = [25, 30, 40, 255]
    disp.visual.face_colors = [70, 160, 230, 255]
    return [pcb, disp]


def main():
    front, back = build_shell(), build_back()
    front.export("agentpet_case_front.stl")
    back.export("agentpet_case_back.stl")
    for name, m in (("front", front), ("back", back)):
        print(f"{name}: faces={len(m.faces)} watertight={m.is_watertight} "
              f"size={np.round(m.extents, 1)}")


if __name__ == "__main__":
    main()
