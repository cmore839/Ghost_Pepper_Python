# utils.py
def ramp_value(current_val, target_val, rate, dt):
    """
    Linearly ramps a value towards a target at a given rate.
    `dt` is the delta-time or time step.
    """
    if current_val == target_val:
        return target_val

    error = target_val - current_val
    step = rate * dt
    
    if abs(error) < step:
        return target_val
    
    return current_val + (step if error > 0 else -step)