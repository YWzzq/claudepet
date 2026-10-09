#!/usr/bin/env python3
"""AgentPet 外壳 STL 生成器（与 agentpet_case.scad 同一套参数）。

用法: python3 build_case.py   → 输出 agentpet_case_front.stl / _back.stl + 预览图
"""
import numpy as np
import trimesh

# ── 参数（与 .scad 保持一致）──
wall, inner_w, inner_d, inner_h = 2.4, 74, 30, 18
corner_r = 10
screen_w, screen_r = 27.6, 2.5
mount_dx, mount_dy, mount_d = 63.2 / 2, 20.8 / 2, 2.2
usb_w, usb_h, led_d = 10, 5, 4

ow, od, oh = inner_w + 2 * wall, inner_d + 2 * wall, inner_h + wall
SEG = 64


def rbox(w, d, h, r, z0=0.0):
    """圆角长方体：角圆柱 + 中部两个长方体，取凸包。"""
    meshes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            meshes.append(trimesh.creation.cylinder(
                radius=r, height=h, sections=SEG,
                transform=trimesh.transformations.translation_matrix(
                    [sx * (w / 2 - r), sy * (d / 2 - r), z0 + h / 2])))
    meshes.append(trimesh.creation.box(
        extents=[max(w - 2 * r, 0.1), d, h],
        transform=trimesh.transformations.translation_matrix([0, 0, z0 + h / 2])))
    meshes.append(trimesh.creation.box(
        extents=[w, max(d - 2 * r, 0.1), h],
        transform=trimesh.transformations.translation_matrix([0, 0, z0 + h / 2])))
    combined = trimesh.util.concatenate(meshes)
    return combined.convex_hull


rounded_box = rbox


def rect_window(w, d, r, z0, h):
    """圆角矩形柱（屏幕窗/开口用）。"""
    return rounded_box(w, d, h, r, z0=z0)


def cylinder_at(x, y, z0, d, h):
    return trimesh.creation.cylinder(
        radius=d / 2, height=h, sections=SEG,
        transform=trimesh.transformations.translation_matrix([x, y, z0 + h / 2]))


def build_front():
    outer = rounded_box(ow, od, oh, corner_r)
    cavity = rounded_box(inner_w, inner_d, inner_h + 1, corner_r - wall, z0=wall)
    window = rect_window(screen_w, screen_w, screen_r, -0.5, wall + 1.5)
    front = outer.difference([cavity, window])
    # 四角螺柱（减去自攻孔）
    for sx in (-1, 1):
        for sy in (-1, 1):
            boss = cylinder_at(sx * mount_dx, sy * mount_dy, wall, mount_d + 4.5, inner_h - wall - 1.2)
            hole = cylinder_at(sx * mount_dx, sy * mount_dy, wall - 1, mount_d, inner_h)
            post = boss.difference(hole)
            front = front.union(post)
    return front


def build_back():
    lip = 2.2                                   # 盖沿插入深度
    cap = rounded_box(ow, od, wall + lip, corner_r)
    # 掏空: 只留底板 + 短沿
    cavity = rounded_box(inner_w, inner_d, inner_h + 1, corner_r - wall, z0=wall)
    back = cap.difference(cavity)
    # USB-C 开口（底侧居中）
    usb = trimesh.creation.box(
        extents=[usb_w, wall + 2, usb_h],
        transform=trimesh.transformations.translation_matrix([0, -od / 2 - 1, oh - usb_h - 4 - (wall + lip - oh)]))
    usb = trimesh.creation.box(
        extents=[usb_w, wall + 2, usb_h],
        transform=trimesh.transformations.translation_matrix([0, -od / 2 - 1, wall + lip - usb_h - 3.5]))
    back = back.difference(usb)
    # RGB 导光孔（顶面中央）: 沿 Y 打穿
    led = trimesh.creation.cylinder(
        radius=led_d / 2, height=od + 2, sections=SEG,
        transform=trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0],
                                                          [0, 0, wall + lip - 5]))
    back = back.difference(led)
    # 散热缝（底侧）
    slots = []
    for x in (-20, -10, 0, 10, 20):
        slots.append(trimesh.creation.box(
            extents=[1.6, wall + 2, inner_h - 8],
            transform=trimesh.transformations.translation_matrix([x, -od / 2 - 1, wall + 3])))
    back = back.difference(slots)
    return back


def main():
    front = build_front()
    back = build_back()
    front.export("agentpet_case_front.stl")
    back.export("agentpet_case_back.stl")
    print("front:", len(front.faces), "faces | watertight:", front.is_watertight)
    print("back :", len(back.faces), "faces | watertight:", back.is_watertight)
    # 预览图：前后壳并排
    scene = trimesh.Scene()
    front.visual.face_colors = [222, 226, 230, 255]
    back.apply_translation([ow + 16, 0, 0])
    back.visual.face_colors = [250, 250, 250, 255]
    scene.add_geometry([front, back])
    png = scene.save_image(resolution=[1000, 700])
    if png:
        open("case_preview.png", "wb").write(png)
        print("case_preview.png saved")


if __name__ == "__main__":
    main()
