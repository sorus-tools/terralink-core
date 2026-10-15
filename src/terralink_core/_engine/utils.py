"""Interface-independent progress reporting for the extracted engine."""
def emit_progress(callback, value, message=None):
    if callback is not None:
        callback(int(max(0, min(100, value))), message)
