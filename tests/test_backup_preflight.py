import socket
import tempfile
import unittest
from pathlib import Path

from backup import BrokenChain, default_jobs, dir_is_populated, host_is_up, preflight
from tests.helpers import HOST_248, HOST_249, make_layout, probe_with


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def jobs(self, **kw):
        return default_jobs(*make_layout(self.base, **kw))

    def test_preflight_all_up_runs_all_three_jobs(self):
        jobs = self.jobs()
        runnable, messages = preflight(jobs, probe=probe_with(set()))
        self.assertEqual(runnable, jobs)
        self.assertEqual(len(runnable), 3)
        self.assertEqual(messages, [])

    def test_preflight_colder_down_runs_only_hot_to_cold(self):
        jobs = self.jobs()
        runnable, messages = preflight(jobs, probe=probe_with({HOST_249}))
        self.assertEqual(runnable, [jobs[0]])
        self.assertEqual(jobs[0].name, "primary hot -> cold")
        self.assertEqual(messages, [
            "192.168.1.249 is powered off, skipping primary hot -> colder",
            "192.168.1.249 is powered off, skipping advocate cold -> colder",
        ])

    def test_preflight_colder_down_never_touches_colder_paths(self):
        jobs = self.jobs()
        seen = []

        def populated(p):
            seen.append(p)
            return dir_is_populated(p)

        preflight(jobs, probe=probe_with({HOST_249}), populated=populated)
        colder = self.base / "colder"
        self.assertTrue(seen)
        self.assertFalse([p for p in seen if p.is_relative_to(colder)])

    def test_preflight_248_down_is_broken_chain(self):
        with self.assertRaises(BrokenChain):
            preflight(self.jobs(), probe=probe_with({HOST_248}))

    def test_preflight_empty_source_is_broken_chain(self):
        with self.assertRaises(BrokenChain):
            preflight(self.jobs(empty=("hot/backup",)), probe=probe_with(set()))

    def test_preflight_missing_cold_advocate_is_broken_chain(self):
        with self.assertRaises(BrokenChain):
            preflight(self.jobs(missing=("cold/advocate",)), probe=probe_with({HOST_249}))

    def test_preflight_empty_dest_on_up_host_is_broken_chain(self):
        with self.assertRaises(BrokenChain):
            preflight(self.jobs(empty=("colder/backup",)), probe=probe_with(set()))

    def test_preflight_probes_each_host_once(self):
        probe = probe_with(set())
        preflight(self.jobs(), probe=probe)
        self.assertEqual(sorted(probe.calls), [HOST_248, HOST_249])

    def test_host_is_up_false_on_refused_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        self.assertFalse(host_is_up("127.0.0.1", port=port, timeout=0.5))


if __name__ == "__main__":
    unittest.main()
