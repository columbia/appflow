_state = {}

def init(filename):
    _state['file'] = open(filename, 'a')

def report_progress(s):
    print(s)
    if 'file' in _state:
        _state['file'].write(s)
        _state['file'].write('\n')
        _state['file'].flush()
