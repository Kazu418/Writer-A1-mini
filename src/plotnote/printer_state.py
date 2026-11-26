"""Preflight checks for direct contact plotting."""

def require_plot_ready(state):
    # BambuStudio DeviceCore/DevAxis.h: X/Y/Z are home_flag bits 0/1/2.
    # Fail closed for missing/zero reports, rather than Studio's UI fallback.
    flag = state.get("home_flag")
    if type(flag) is not int or flag < 0 or flag & 7 != 7:
        raise ValueError("XYZ homing is not confirmed; remove the pen and home before plotting")
    if state.get("gcode_state") not in ("IDLE", "FINISH", "FAILED") or state.get("print_error", 0):
        raise ValueError("Printer is not idle/error-free")
    if state.get("hms"):
        raise ValueError("Printer has active HMS diagnostics")
    if state.get("nozzle_target_temper", -1) != 0 or state.get("bed_target_temper", -1) != 0:
        raise ValueError("Heater targets are not zero")
