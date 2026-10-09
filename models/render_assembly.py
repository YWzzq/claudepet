#!/usr/bin/env python3
"""装配步骤可视化（像素外壳 V4）：4 步 = 空壳 → 装板 → 贴屏 → 插背板。"""
import trimesh, numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
fm.fontManager.addfont("/System/Library/Fonts/Hiragino Sans GB.ttc")
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB"]

import build_case as B

front = B.build_shell()
back = B.build_back()
front.export("agentpet_case_front.stl")
back.export("agentpet_case_back.stl")

board_meshes = trimesh.util.concatenate(B.simple_board())
screen_meshes = trimesh.util.concatenate(B.simple_screen())

ELEV, AZIM = 14, 118


def render(ax, items, title, azim=AZIM, alpha_case=1.0):
    for m, c, a in items:
        ax.plot_trisurf(m.vertices[:, 0], m.vertices[:, 1], m.vertices[:, 2],
                        triangles=m.faces, color=c, edgecolor="none",
                        alpha=a, shade=True)
    ax.view_init(elev=ELEV, azim=azim)
    ax.set_box_aspect((1.3, 0.5, 1))
    ax.set_title(title, fontsize=13, pad=0)
    ax.axis("off")
    ax.set_xlim(-52, 92); ax.set_ylim(-30, 30); ax.set_zlim(0, 84)


fig = plt.figure(figsize=(13, 9.5), dpi=105)

render(fig.add_subplot(2, 2, 1, projection="3d"),
       [(front, "#E8862E", 1.0)],
       "① 像素前壳: 中间方孔=屏幕窗口, 右侧缺口=USB线, 顶上呆毛")

render(fig.add_subplot(2, 2, 2, projection="3d"),
       [(front, "#E8862E", 0.35), (board_meshes, "#3E9E5A", 1.0)],
       "② 板子横躺滑进底层(绿色), USB口对准右侧开口")

render(fig.add_subplot(2, 2, 3, projection="3d"),
       [(front, "#E8862E", 0.35), (board_meshes, "#3E9E5A", 1.0),
        (screen_meshes, "#2A3548", 1.0)],
       "③ 屏幕竖插: 下缘坐托架, 显示区对准窗口, 4孔对4臂")

back_shift = back.copy()
back_shift.apply_translation([0, -10, 0])
render(fig.add_subplot(2, 2, 4, projection="3d"),
       [(front, "#E8862E", 1.0), (back_shift, "#F2F4F7", 1.0)],
       "④ 像素背板沿背面滑到底=完成! (白色, 通风孔朝后)")

plt.tight_layout()
plt.savefig("assembly_steps.png", bbox_inches="tight", facecolor="#1a1d23")
print("saved")
