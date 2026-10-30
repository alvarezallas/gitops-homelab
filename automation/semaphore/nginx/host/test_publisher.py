"""Behavioral tests: candidates, rollback, no-op and crash recovery; no host mutations."""
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

P=pathlib.Path
spec=importlib.util.spec_from_file_location('publisher',P(__file__).with_name('homelab-nginx-deploy.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OLD='a'*40
NEW='b'*40

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=P(self.tmp.name)
        self.patches=[patch.object(m,'BASE',self.base),patch.object(m,'RELEASES',self.base/'releases'),
                      patch.object(m,'CURRENT',self.base/'current'),patch.object(m,'STATE',self.base/'state.json'),
                      patch.object(m,'JOURNAL',self.base/'pending.json'),patch.object(m,'AUDIT',self.base/'audit.jsonl'),
                      patch('sys.stdout',io.StringIO())]
        for p in self.patches:p.start()
        m.RELEASES.mkdir()
        for sha in [OLD,NEW]:
            d=m.RELEASES/sha;d.mkdir();(d/'default.conf').write_text('same')
        m.switch(OLD)
        m.write_json(m.STATE,{'applied':OLD})

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_same_sha_does_not_reload_or_probe(self):
        with patch.object(m,'reload_nginx') as reload,patch.object(m,'probes') as probe:
            m.deploy(OLD)
            reload.assert_not_called();probe.assert_not_called()
        self.assertEqual(m.current_sha(),OLD)

    def test_invalid_candidate_never_promoted(self):
        with patch.object(m,'archive',side_effect=RuntimeError('nginx test failed')),patch.object(m,'reload_nginx') as reload:
            with self.assertRaises(RuntimeError):m.deploy(NEW)
            reload.assert_not_called()
        self.assertEqual(m.current_sha(),OLD)
        self.assertEqual(json.loads(m.STATE.read_text())['rejected'],NEW)
        self.assertFalse(m.JOURNAL.exists())

    def test_static_change_publishes_without_reload(self):
        with patch.object(m,'archive'),patch.object(m,'run'),patch.object(m,'probes',return_value={'ok':200}),patch.object(m,'reload_nginx') as reload:
            m.deploy(NEW)
            reload.assert_not_called()
        self.assertEqual(m.current_sha(),NEW)
        self.assertFalse(m.JOURNAL.exists())

    def test_config_change_requires_reload(self):
        (m.RELEASES/NEW/'default.conf').write_text('changed')
        with patch.object(m,'archive'),patch.object(m,'run'),patch.object(m,'probes',return_value={'ok':200}),patch.object(m,'reload_nginx') as reload:
            m.deploy(NEW)
            reload.assert_called_once()
        self.assertEqual(m.current_sha(),NEW)

    def test_failed_https_restores_disk_state_and_reloads_old(self):
        def probe(sha):
            if sha==NEW:raise RuntimeError('new upstream unavailable')
            return {'ok':200}
        with patch.object(m,'archive'),patch.object(m,'run'),patch.object(m,'probes',side_effect=probe),patch.object(m,'reload_nginx') as reload,patch.object(m.time,'sleep'):
            with self.assertRaises(RuntimeError):m.deploy(NEW)
            reload.assert_called_once()
        self.assertEqual(m.current_sha(),OLD)
        self.assertEqual(json.loads(m.STATE.read_text())['applied'],OLD)
        self.assertFalse(m.JOURNAL.exists())

    def test_boot_recovery_reverts_before_nginx_start(self):
        m.switch(NEW);m.write_json(m.JOURNAL,{'previous':OLD,'candidate':NEW})
        with patch.object(m,'run'),patch.object(m,'reload_nginx') as reload,patch.object(m,'probes') as probe:
            m.recover(boot=True)
            reload.assert_not_called();probe.assert_not_called()
        self.assertEqual(m.current_sha(),OLD)
        self.assertFalse(m.JOURNAL.exists())

    def test_rejected_commit_not_retried_every_minute(self):
        m.write_json(m.STATE,{'applied':OLD,'rejected':NEW})
        with patch.object(m,'archive') as archive:
            with self.assertRaises(RuntimeError):m.deploy(NEW)
            archive.assert_not_called()

    def test_explicit_root_retry_can_revalidate_rejected_commit(self):
        m.write_json(m.STATE,{'applied':OLD,'rejected':NEW})
        with patch.object(m,'archive'),patch.object(m,'run'),patch.object(m,'probes',return_value={'ok':200}):
            m.deploy(NEW,explicit=True)
        self.assertEqual(m.current_sha(),NEW)

if __name__=='__main__':unittest.main(verbosity=2)
