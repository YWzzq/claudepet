#!/usr/bin/env python3
"""装配步骤可视化 V2：正面视角 + 半透明壳体（内部可见）。"""
import trimesh, numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
fm.fontManager.addfont("/System/Library/Fonts/Hiragino Sans GB.ttc")
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB"]

import build_case as B

front = B.build_front()
back = B.build_back()
front.export("agentpet_case_front.stl")
back.export("agentpet_case_back.stl")

board_meshes = trimesh.util.concatenate(B.simple_board())
screen_meshes = trimesh.util.concatenate(B.simple_screen())

ELEV = 14
CASE_ALPHA = 0.30   # 半透明: 能看见内部


def render(ax, items, title, azim):
    for m, c, a in items:
        ax.plot_trisurf(m.vertices[:, 0], m.vertices[:, 1], m.vertices[:, 2],
                        triangles=m.faces, color=c, edgecolor="none",
                        alpha=a, shade=True)
    ax.view_init(elev=ELEV, azim=azim)
    ax.set_box_aspect((1, 0.65, 0.85))
    ax.set_title(title, fontsize=13, pad=0)
    ax.axis("off")
    ax.set_xlim(-45, 45); ax.set_ylim(-35, 35); ax.set_zlim(0, 55)


fig = plt.figure(figsize=(13, 9.5), dpi=105)

# ① 空前壳(不透明, 正面看屏窗)
render(fig.add_subplot(2, 2, 1, projection="3d"),
       [(front, "#C9D2DC", 1.0)],
       "① 前壳: 中间方孔=屏幕窗口, 右下小口=USB线出口", azim=105)

# ② 半透明: 板子横躺进底层
render(fig.add_subplot(2, 2, 2, projection="3d"),
       [(front, "#C9D2DC", CASE_ALPHA), (board_meshes, "#3E9E5A", 1.0)],
       "② 板子横躺滑进底层(绿色), USB口对准右侧开口", azim=105)

# ③ 屏幕竖贴窗口内侧
render(fig.add_subplot(2, 2, 3, projection="3d"),
       [(front, "#C9D2DC", CASE_ALPHA), (board_meshes, "#3E9E5A", 1.0),
        (screen_meshes, "#2A3548", 1.0)],
       "③ 屏幕竖着贴在窗口内侧(蓝面=显示区, 朝外发光)", azim=105)

# ④ 背板插入(背面视角)
render(fig.add_subplot(2, 2, 4, projection="3d"),
       [(front, "#C9D2DC", CASE_ALPHA), (back, "#F2F4F7", 1.0),
        (board_meshes, "#3E9E5A", 1.0), (screen_meshes, "#2A3548", 1.0)],
       "④ 背板沿背面滑到底=完成! 顶面开孔兼散热和插线", azim=-75)

plt.tight_layout()
plt.savefig("assembly_steps.png", bbox_inches="tight", facecolor="#1a1d23")
print("saved")
