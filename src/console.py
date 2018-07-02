import threading
import logging
import readline
import cmd

logger = logging.getLogger("console")


class Console(cmd.Cmd):
    def __init__(self, cb, prompt="> ", daemon=False, after_cb=None, init_env={}):
        cmd.Cmd.__init__(self)
        self.prompt = prompt
        self.cb = cb
        self.thread = None
        self.daemon = daemon
        self.after_cb = after_cb
        self.env = init_env
        self.exited = False

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=self.daemon)
        self.thread.start()

    def wait(self):
        self.thread.join()

    def set_prompt(self, prompt):
        self.prompt = prompt

    def run(self):
        self.cmdloop()

    def postcmd(self, stop, line):
        if self.after_cb is not None:
            try:
                self.after_cb(self, self.env)
            except:
                logger.exception("error running after cb")

        return self.exited

    def default(self, line):
        try:
            self.cb(self, line, self.env)
        except SystemExit:
            self.exited = True
        except:
            logger.exception("error handling cmd")
