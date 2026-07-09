from util.cli import cli, formatting


class Result:
    def __init__(self, result=None, **kwargs):
        self._result = result

        meta = kwargs.get("meta")

        if meta is None:
            meta = kwargs

        self._meta = meta if meta else {}
        self._success = False
        self._timeouted = False

        if meta is not None:
            self._success = meta.get("success", False)
            self._timeouted = meta.get("timeout", False)

    @property
    def success(self):
        return self._success

    @property
    def timeouted(self):
        return self._timeouted

    @property
    def result(self):
        return self._result

    @property
    def meta(self):
        return self._meta

    def add_time(self, name, time):
        if time:
            self.meta["times"][name] = time

    def add_meta(self, key, value):
        self.meta[key] = value

    @property
    def time_total(self):

        time = sum([x for x in self.meta["times"].values() if x])
        time = f"{time:.2f}s" if time else ""

        if time is not None:
            return f"{formatting.bold(time)}"

    @property
    def time_split(self):

        if len(self.meta["times"]) <= 1:
            return self.time_total

        time = sum([x for x in self.meta["times"].values() if x])
        time = f"{time:.2f}s" if time else ""

        time_kc = self.meta["times"].get("time_kc")
        time_kc = f"{time_kc:.3f}s" if time_kc else time_kc

        time_pre = self.meta["times"].get("time_pre")
        time_pre = f"{time_pre:.3f}s" if time_pre else time_pre

        time_export = self.meta["times"].get("time_export")
        time_export = f"{time_export:.3f}s" if time_export else time_export

        times = [
            f"PRE: {time_pre}" if time_pre else "",
            f"KC: {time_kc}" if time_kc else "",
            f"EXPORT: {time_export}" if time_export else "",
        ]
        times = ", ".join([x for x in times if x])

        return f"{formatting.bold(time)} ({times})"

    def __str__(self):
        meta = self.meta

        if self.result is not None:
            return f'Result[Success: {self.success}, Timout: {self.timeout} {meta.get("file_in")} -> {meta.get("file_out")}'
        elif meta.get("timeout", False) is True:
            return f'Timeout ({meta.get("file_in")})'
        elif self.success:
            return f'Success {meta.get("file_in")} -> {meta.get("file_out")} ({self.time_split})'
        else:
            return (
                f'Emtpy Result (error: {meta.get("error", "")}) ({meta.get("file_in")})'
            )

    def render(self):

        if self.success:
            cli.say(formatting.check(), self.time_split)


class ResultIterable(Result):

    def __len__(self):
        return len(self.result)

    def __iter__(self):
        return iter(self.result)

    def __str__(self):
        meta = self.meta

        if self.result is not None:
            return f'Result[{len(self.result)}] {meta.get("file_in")} -> {meta.get("file_out")}'
        elif self.timeouted:
            return f'Emtpy Result (t/o) ({meta.get("file_in")})'
        else:
            return (
                f'Emtpy Result (error: {meta.get("error", "")}) ({meta.get("file_in")})'
            )


class BDDResult(Result):

    def render(self):

        if self.success:
            cli.say(
                formatting.check(),
                f'{self.time_split}, Size: {self.meta.get("size"):,} nodes',
            )
        elif self.timeouted:
            cli.say(
                f'Compilation {formatting.warn("timed out")} ({formatting.h(self.meta.get("file_in"))}, {formatting.h(self.meta.get("compiler"))})'
            )
        else:
            cli.warn(self.meta.get("error"))
