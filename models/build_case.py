#!/usr/bin/env python3
"""AgentPet 外壳 V3.1 —— 屏幕横置 + 螺丝孔精确定位版。

依据屏幕官方尺寸图:
- PCB 43.72(长)×31.52(宽), 厚2.0, 排针在长边一端(全长11.3含针)
- 显示区 AA 27.72×27.72, 距非排针端 6.0/距两侧 2.14
- 4×Ø2.0 安装孔, 距边 2.5 → 孔距 38.72 × 26.52
布局(站立小方碑 50×38.8×36):
- 前窗 28.2 方孔, 只露显示区(边缘压0.2)
- 屏幕横置贴前壁内侧: 下边缘插进底板卡槽(定位), 上方2孔锁M2自攻(固定)
- 板子横卧底层(热熔胶/双面胶粘底板), USB 朝右壁开口
- 背板从顶部沿背面插入(通风缝), 顶面开放兼散热
"""
import numpy as np
import trimesh

wall = 2.4
inner_w, inner_d = 58.0, 34.0
floor = 2.4
total_h = 36.0
corner_r = 9.0

# 屏幕(横置)
spcb_l, spcb_h, spcb_t = 43.72, 31.52, 2.0     # 长(横)×高(竖)×厚
view_w = 27.72
win_size = view_w + 0.5                         # 28.22, 每边压显示区0.25
win_cx = -2.0                                   # AA 中心(偏非排针端)
pcb_cz = 1.2 + spcb_h / 2                       # 屏下缘沉入底板槽1.2 → 中心z 17.2
win_cz = 1.2 + 2.14 + view_w / 2                # 18.26
hole_dx = spcb_l / 2 - 2.5                      # ±19.36 (左右孔)
hole_dz = spcb_h / 2 - 2.5                      # ±13.26 (上下孔)
# 上方两孔锁螺丝(下方两孔由底板槽定位)
post_z = pcb_cz + hole_dz                       # 30.46
post_len = 6.0

board_l, board_d, board_t = 53.34, 27.94, 1.8
board_cy = -0.8                                 # 板中心(背板与屏幕之间)

usb_slot_w, usb_slot_h = 12.0, 6.0
usb_cz = floor + board_t + 1.8                  # USB座中心高度

ow, od = inner_w + 2 * wall, inner_d + 2 * wall
SEG = 64


def rounded_box(w, d, h, r, z0=0.0, cx=0.0, cy=0.0):
    meshes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            meshes.append(trimesh.creation.cylinder(
                radius=r, height=h, sections=SEG,
                transform=trimesh.transformations.translation_matrix(
                    [cx + sx * (w / 2 - r), cy + sy * (d / 2 - r), z0 + h / 2])))
    meshes.append(trimesh.creation.box(
        extents=[max(w - 2 * r, 0.1), d, h],
        transform=trimesh.transformations.translation_matrix([cx, cy, z0 + h / 2])))
    meshes.append(trimesh.creation.box(
        extents=[w, max(d - 2 * r, 0.1), h],
        transform=trimesh.transformations.translation_matrix([cx, cy, z0 + h / 2])))
    return trimesh.util.concatenate(meshes).convex_hull


def box_at(w, d, h, x, y, z):
    return trimesh.creation.box(
        extents=[w, d, h],
        transform=trimesh.transformations.translation_matrix([x, y, z + h / 2]))


def cyl_y(x, y0, y1, r):
    return trimesh.creation.cylinder(
        radius=r, height=abs(y1 - y0), sections=SEG,
        transform=trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0],
                                                          [x, 0, (y0 + y1) / 2]))


def build_front():
    outer = rounded_box(ow, od, total_h, corner_r)
    cuts = []
    # 内腔(顶部开放)
    cuts.append(rounded_box(inner_w, inner_d, total_h - floor + 1,
                            corner_r - wall, z0=floor))
    # 屏窗: 打穿前壁, 中心 (win_cx, win_cz)
    cuts.append(rounded_box(win_size, wall + 6, win_size, 3,
                            z0=win_cz - win_size / 2, cx=win_cx, cy=od / 2 - 2))
    # USB 侧口: 打穿右壁(+X), 板子USB座中心 (board_cy, usb_cz)
    cuts.append(box_at(wall + 6, usb_slot_w, usb_slot_h,
                       ow / 2 - 2, board_cy, usb_cz - usb_slot_h / 2))
    # 底板屏幕卡槽: 屏下缘插入定位(深1.2, y 13.5~17.1 覆盖屏位)
    cuts.append(box_at(spcb_l + 1, 3.6, 1.2, 0, 15.3, 1.2))
    f = outer.difference(cuts)

    # 上方两孔的螺柱(自屏窗向后), 带 M2 底孔 Ø1.7
    for sx in (-1, 1):
        post = cyl_y(sx * hole_dx, inner_d / 2 - wall, inner_d / 2 - wall - post_len, 3.0)
        pilot = cyl_y(sx * hole_dx, inner_d / 2 - wall - post_len - 0.5,
                      inner_d / 2 - wall + 0.5, 0.85)
        f = f.union(post).difference(pilot)

    # 板子限位小凸台(1.5mm 高, 前后各二, 兼作胶粘定位)
    for sx in (-1, 1):
        for sy in (-1, 1):
            f = f.union(box_at(4, 3, 1.5, sx * 25.5, board_cy + sy * 13.2, floor))
    return f


def build_back():
    """插板: 厚1.6, 从顶部沿背面滑入, 三条竖通风缝。"""
    plate_d = 1.6
    h = total_h - floor - 2.0
    plate = rounded_box(inner_w - 3.0, plate_d, h, 5.0,
                        z0=floor, cy=-(inner_d / 2 - plate_d / 2 - 0.1))
    slots = []
    for x in (-15, 0, 15):
        slots.append(box_at(2.0, plate_d + 2, 18, x, 0, floor + 6))
    plate = plate.difference(slots)
    return plate


def simple_board():
    pcb = box_at(board_l, board_d, board_t, 0, board_cy, floor)
    usb = box_at(3.5, 9, 3.5, board_l / 2 - 2.2, board_cy, floor + board_t)
    usb.visual.face_colors = [40, 40, 40, 255]
    return [pcb, usb]


def simple_screen():
    """横置屏: PCB 竖板(长边水平) + 显示区亮面板。"""
    pcb_z0 = floor - 1.2                       # 下缘沉入槽 1.2
    pcb = box_at(spcb_l, spcb_t, spcb_h, 0, inner_d / 2 - spcb_t / 2 - 0.1, pcb_z0)
    disp = box_at(view_w, 0.4, view_w,
                  win_cx, inner_d / 2 - spcb_t / 2 - 0.1 + spcb_t / 2 + 0.3,
                  win_cz - view_w / 2)
    pcb.visual.face_colors = [25, 30, 40, 255]
    disp.visual.face_colors = [70, 160, 230, 255]
    return [pcb, disp]


def main():
    front, back = build_front(), build_back()
    front.export("agentpet_case_front.stl")
    back.export("agentpet_case_back.stl")
    for name, m in (("front", front), ("back", back)):
        print(f"{name}: faces={len(m.faces)} watertight={m.is_watertight} "
              f"size={np.round(m.extents, 1)}")


if __name__ == "__main__":
    main()
