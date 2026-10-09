#!/usr/bin/env python3
"""AgentPet 外壳 V3-final —— 按商品页实测尺寸 + 装配可达性修正。

坐标系: X=宽(左右), Y=厚(前+Y/后-Y), Z=高。前窗在 +Y 面, 背板插在 -Y 面。
布局: 板子横卧底层(USB朝右壁), 屏幕竖贴前壁内侧, 顶面开放(装配/散热)。
"""
import numpy as np
import trimesh

wall = 2.4
inner_w, inner_d = 58.0, 33.0
floor = 2.4
total_h = 50.0
corner_r = 9.0

screen_pcb_w, screen_pcb_h, screen_pcb_t = 32.0, 43.7, 3.2
view_w = 27.72
win_z0, win_h = 10.0, view_w + 2.5          # 屏窗: z 10~40.2, 打穿前壁
usb_slot_w, usb_slot_h = 12.0, 6.0          # 右壁开口
board_l, board_d, board_t = 53.34, 27.94, 1.8
board_cy = -1.0                              # 板中心后移1mm, 给屏幕让位
screen_cy = inner_d / 2 - screen_pcb_t / 2 - 0.1   # 屏贴前壁内侧 = 14.85

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


def build_front():
    outer = rounded_box(ow, od, total_h, corner_r)
    cuts = []
    # 内腔(顶部开放)
    cuts.append(rounded_box(inner_w, inner_d, total_h - floor + 1,
                            corner_r - wall, z0=floor))
    # 屏窗: 打穿前壁(+Y)。切割体沿 Y 加深并中心放在前壁上
    cuts.append(rounded_box(view_w + 4, wall + 6, win_h, 3,
                            z0=win_z0 - 1.5, cy=od / 2 - 2))
    # USB 侧口: 打穿右壁(+X)。板子 USB 连接器在 y=board_cy
    cuts.append(box_at(wall + 6, usb_slot_w, usb_slot_h,
                       ow / 2 - 2, board_cy, floor + board_t - 0.5))
    f = outer.difference(cuts)

    # 板子限位凸台: 四角小凸台(避开屏幕 x±16 区域)
    for sx in (-1, 1):
        for sy in (-1, 1):
            stop = box_at(4, 3, 2.5, sx * 25, board_cy + sy * 13.0, floor)
            f = f.union(stop)
    return f


def build_back():
    """插板式背板: 厚1.6, 从顶部沿背壁(-Y)滑入, 摩擦固定, 带竖向通风缝。"""
    plate_d = 1.6
    plate = rounded_box(inner_w - 3.0, plate_d, total_h - floor - 2.0, 5.0,
                        z0=floor, cy=-(inner_d / 2 - plate_d / 2 - 0.1))
    slots = []
    for x in (-15, 0, 15):
        slots.append(box_at(2.0, plate_d + 2, 24, x, 0, floor + 8))
    plate = plate.difference(slots)
    return plate


def simple_board():
    """简化板子: 绿PCB横卧 + 黑USB座(+X短边, 朝右壁开口)。"""
    pcb = box_at(board_l, board_d, board_t, 0, board_cy, floor)
    usb = box_at(3.5, 9, 3.5, board_l / 2 - 2.2, board_cy, floor + board_t)
    usb.visual.face_colors = [40, 40, 40, 255]
    return [pcb, usb]


def simple_screen():
    """简化屏幕: 深色PCB竖贴前壁内侧 + 显示区(亮面板朝前壁窗口)。"""
    pcb = box_at(screen_pcb_w, screen_pcb_t, screen_pcb_h, 0, screen_cy, floor)
    disp = box_at(view_w, 0.4, view_w,
                  0, screen_cy + screen_pcb_t / 2 + 0.3, win_z0 + 0.5)
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
