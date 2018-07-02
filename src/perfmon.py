import time
import logging

logger = logging.getLogger("perfmon")


class PerfRecord(object):
    def __init__(self, op, name):
        self.op = op
        self.name = name
        self.starttime = time.time()
        self.stoptime = None

    def stop(self):
        self.stoptime = time.time()

    def time(self):
        if self.stoptime is None:
            return None
        return self.stoptime - self.starttime

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "%s:%s %.3fs" % (self.op, self.name, self.time())


class PerfStat(object):
    def __init__(self, op, name):
        self.op = op
        self.name = name
        self.min = None
        self.max = None
        self.total = 0.0
        self.count = 0

    def add_record(self, record: PerfRecord):
        self.count += 1
        t = record.time()
        self.total += t
        if self.min is None or t < self.min:
            self.min = t
        if self.max is None or t > self.max:
            self.max = t

    def avg(self):
        if self.count == 0:
            return -1
        return self.total / self.count

    def __str__(self):
        return "%9.3fs ~%6.3f %8s:%s %.3f-%.3f (%d)" % (self.total, self.avg(), self.op,
                                                        self.name, self.min, self.max,
                                                        self.count)


op_info = {}
op_history = []
last_entry = {}
stats = {}


def record_start(op, name):
    record_stop("global", "uncounted")
    record = PerfRecord(op, name)
    op_info["%s_%s" % (op, name)] = record


def record_stop(op, name):
    key = "%s_%s" % (op, name)
    record = op_info.get(key, None)
    if record is None:
        return 0.0
    del op_info[key]
    if record is not None:
        record.stop()
    last_entry[key] = len(op_history)
    op_history.append(record)
    if key not in stats:
        stats[key] = PerfStat(op, name)
    stats[key].add_record(record)
    if op_info == {}:
        record_start("global", "uncounted")
    return record.time()


def find_last(op, name):
    key = "%s_%s" % (op, name)
    if key in last_entry:
        return op_history[last_entry[key]]
    else:
        return None


def get_avg_time(op, name):
    key = "%s_%s" % (op, name)
    if key in stats:
        ret = stats[key].avg()
        if ret == -1:
            return None
        else:
            return ret
    else:
        return None


def print_stat():
    for stat in sorted(stats):
        logger.info("%s", stats[stat])


def op(op, nameformat="%r", showtime=False):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            if '%' in nameformat:
                name = nameformat % args[0]
            else:
                name = nameformat
            record_start(op, name)
            ret = f(*args, **kwargs)
            used = record_stop(op, name)
            if showtime:
                logger.info("%s %s used %.3fs", op, name, used)
            return ret
        return wrapped_f
    return wrap


if __name__ == "__main__":
    @op("test", "%s")
    def testf(name, length):
        time.sleep(length)

    testf("name", 1)
    testf("name", 0.5)

    print(find_last("test", "name"))
    print_stat()
    assert(op_info == {})
