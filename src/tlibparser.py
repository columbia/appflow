import re
import logging

import microtest
import condition
import operation

logger = logging.getLogger("tlibparser")


feature_re = re.compile("Feature:\s+(.*)")
scenario_re = re.compile("Scenario:\s+([^\(]*)(\(.+\))?")
#change_re = re.compile("@change_(.+)\((.*)\)")
#expect_re = re.compile("@expect_(.+)\((.+)\)")
#cond_re = re.compile("@(.+)\((.*)\)")
change_re = re.compile("set ([^ ]+) to ([^ ]+)")
cond_re = re.compile("([^ ]+) is ([^ ]+)")
neg_cond_re = re.compile("([^ ]+) is not ([^ ]+)")
tag_re = re.compile("@([^(]+)")
stmt_re = re.compile("(When|Given|Then|And) (.+)")


def try_parse_condition(stmt):
    if neg_cond_re.match(stmt):
        (name, value) = neg_cond_re.match(stmt).groups()
        name = '!' + name
    elif cond_re.match(stmt):
        (name, value) = cond_re.match(stmt).groups()
    else:
        return None
    return parse_condition(name, value)


def parse_feature_file(filename):
    tests = []
    curr_test = None
    feature_name = ''
    tags = set()
    last_verb = None
    for line in open(filename).read().split('\n'):
        line = line.strip()
        if line == '' or line.startswith('#'):
            continue

        if feature_re.match(line):
            feature_name = feature_re.match(line).group(1)
            logger.debug("Feature: %s", feature_name)
        elif scenario_re.match(line):
            (scenario_name, args) = scenario_re.match(line).groups()

            if curr_test is not None:
                tests.append(curr_test)
            tags.add(feature_name)
            curr_test = microtest.MicroTest(filename=filename, name=scenario_name,
                                            tags=tags, args=args,
                                            feature_name=feature_name)

            # no custom test can run on init
            curr_test.add_cond(condition.Condition("notequal", {"screen": "init"}))
            last_verb = None
            tags = set()

            logger.debug("Scenario: %s", scenario_name)
        elif stmt_re.match(line):
            (verb, stmt) = stmt_re.match(line).groups()
            if verb == 'And':
                if last_verb is None:
                    raise Exception("Fresh And stmt")
                verb = last_verb
            else:
                last_verb = verb

            if verb == 'Given':
                cond = try_parse_condition(stmt)
                if cond is None:
                    raise Exception("Unknown condition %s" % line)

                curr_test.add_cond(cond)
            elif verb == 'When' or verb == 'Then':
                cond = try_parse_condition(stmt)
                if cond is not None:
                    curr_test.add_expect(cond)
                elif change_re.match(stmt):
                    (name, value) = change_re.match(stmt).groups()
                    curr_test.add_change(name, value)
                else:
                    op = operation.parse_line(stmt)
                    if op is not None:
                        curr_test.add_step(op)
                    else:
                        raise Exception("unknown line: %s" % line)
            else:
                raise Exception("unknown verb: %s" % verb)
        elif tag_re.match(line):
            tag = tag_re.match(line).group(1)
            tags.add(tag)
        else:
            raise Exception("unknown line: %s" % line)

    if curr_test is not None:
        tests.append(curr_test)

    return tests


def parse_condition(name, value):
    if name.startswith('!'):
        return condition.Condition("notequal", {name[1:]: value})
    else:
        return condition.Condition('equal', {name: value})
