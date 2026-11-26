import pytest
from plotnote.printer_state import require_plot_ready

def state(flag):
    return dict(gcode_state="FINISH", print_error=0, hms=[], nozzle_target_temper=0, bed_target_temper=0, home_flag=flag)

@pytest.mark.parametrize("flag", [847070608, 847070609, 847070611, 0, None, True])
def test_refuses_missing_or_partial_homing(flag):
    with pytest.raises(ValueError, match="homing"):
        require_plot_ready(state(flag))

def test_all_axes_homed():
    require_plot_ready(state(847070615))

def test_missing_home_flag():
    value=state(None)
    del value["home_flag"]
    with pytest.raises(ValueError, match="homing"):
        require_plot_ready(value)

@pytest.mark.parametrize("change", [dict(gcode_state="RUNNING"), dict(print_error=1), dict(hms=[{}]), dict(nozzle_target_temper=75), dict(bed_target_temper=60)])
def test_existing_refusals_preserved(change):
    value=state(847070615)
    value.update(change)
    with pytest.raises(ValueError):
        require_plot_ready(value)
