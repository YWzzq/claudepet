// AgentPet V0.8 外壳 —— 小方脸桌面摆件
// 硬件: ESP32-S3 DevKitC-1 (69.7×26.4mm 带 USPSDT 通孔) + 1.54" ST7789 模块 (约 32×42mm 屏+PCB)
// 打印: 前后壳分离, 四角 M3 自攻螺柱, PLA 0.2mm 层高, 无支撑(前壳屏窗朝上打印)

/* ── 可调参数 ─────────────────────────────── */
// 内腔需容纳: 板厚(排针高~11mm) + 屏模块(约 3.5mm) + 屏排针 → 取内深 18mm
wall      = 2.4;    // 壁厚
inner_w   = 74;     // 内腔宽 (板 69.7 + 两侧间隙)
inner_d   = 30;     // 内腔厚 (板 26.4 + 线材余量)
inner_h   = 18;     // 内腔深 (排针 + 屏 + 间隙)
corner_r  = 10;     // 外观圆角(小方脸, 圆润但不圆)

screen_w  = 27.6;   // 屏幕可视区宽 240×240 = 27.6mm (1.54")
screen_r  = 2.5;    // 屏窗圆角

// 板子固定: DevKitC-1 四角安装孔, 间距 63.2×20.8, 孔径 2.2 (M2 自攻)
mount_dx  = 63.2/2;
mount_dy  = 20.8/2;
mount_d   = 2.2;    // 螺柱孔(自攻 M2)

usb_w    = 10;     // USB-C 口开口
usb_h    = 5;
led_d    = 4;      // RGB 灯导光孔

/* ── 派生 ─────────────────────────────────── */
ow = inner_w + 2*wall;   // 外宽
od = inner_d + 2*wall;   // 外厚
oh = inner_h + wall;     // 外深(前壳底 + 腔)

$fn = 64;

module shell_body(h=oh) {
  // 圆角长方体
  hull() for (sx=[-1,1], sy=[-1,1])
    translate([sx*(ow/2-corner_r), sy*(od/2-corner_r), 0])
      cylinder(r=corner_r, h=h);
}

/* ── 前壳(带屏窗): 主件 ─────────────────── */
module front() {
  difference() {
    shell_body();
    // 内腔
    translate([0, 0, wall])
      hull() for (sx=[-1,1], sy=[-1,1])
        translate([sx*(inner_w/2-corner_r+wall), sy*(inner_d/2-corner_r+wall), 0])
          cylinder(r=corner_r-wall, h=inner_h+1);
    // 屏幕窗口
    translate([0, 0, -0.5])
      linear_extrude(wall+1)
        offset(r=screen_r) square([screen_w, screen_w], center=true);
  }
  // 螺柱: 四角安装孔位置 (内腔底面起)
  for (sx=[-1,1], sy=[-1,1])
    translate([sx*mount_dx, sy*mount_dy, wall]) {
      difference() {
        cylinder(d=mount_d+4.5, h=inner_h-wall-1.2);
        translate([0,0,-0.5]) cylinder(d=mount_d, h=inner_h);
      }
    }
}

/* ── 后盖(带 USB 口 + 灯孔): 盖板 ─────────── */
module back() {
  difference() {
    shell_body(wall+2.2);                 // 盖沿插入前壳
    translate([0, 0, wall]) shell_body(inner_h+1);  // 掏空(仅留盖沿)
    // USB-C 开口(居中, 底侧)
    translate([-usb_w/2, -od/2-0.5, oh-usb_h-4])
      cube([usb_w, wall+1, usb_h]);
    // RGB 灯导光孔(板载灯在 GPIO48, 板顶边中央 → 后盖上部)
    translate([0, 0, oh-6]) rotate([90,0,0]) cylinder(d=led_d, h=od+1);
    // 散热缝
    for (x=[-20,-10,0,10,20])
      translate([x, -od/2-0.5, wall+3]) cube([1.6, wall+1, inner_h-8]);
  }
}

/* ── 打印摆位 ─────────────────────────────── */
front();
translate([ow+16, 0, 0]) back();

/* 装配说明(注释):
 1. 板子用 4×M2×6 自攻螺钉固定在前壳螺柱上(USB 朝后盖 USB 口方向)
 2. 屏幕模块用双面胶贴在板子顶面, 屏幕对准前壳窗口
 3. 杜邦线在腔内走线, 后盖按压扣合
 4. RGB 灯对准后盖导光孔(不在一线时挪 led_d 位置参数) */
