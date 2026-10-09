// V5.1 viewer, mm. Dimension source: build_case.py; run it to regenerate meshes.
// part = "layout" | "assembly" | "front" | "back" | "coupon".
part = "layout";
if (part == "layout") import("agentpet_case_both.stl");
if (part == "assembly") {
  color("DarkOrange") import("agentpet_case_front.stl");
  color("Wheat") import("agentpet_case_back.stl");
}
if (part == "front") import("agentpet_case_front.stl");
if (part == "back") import("agentpet_case_back.stl");
if (part == "coupon") import("screen_fit_coupon.stl");

if (part == "usb-coupon") import("usb_fit_coupon.stl");
