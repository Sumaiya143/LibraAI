import datetime as dt
import hashlib
import tempfile
import unittest
from pathlib import Path
from backup_retention import plan_retention


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = dt.datetime(2026, 10, 15, tzinfo=dt.timezone.utc)

    def create(self, day, checksum=True):
        name = f'libraai-202610{day:02d}T010000Z.db'
        file = self.root / name
        file.write_bytes(f'db-{day}'.encode())
        if checksum:
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            (self.root / (name + '.sha256')).write_text(f'{digest}  {name}\n')
        return file

    def test_keeps_newest(self):
        for day in range(1, 7): self.create(day)
        self.assertEqual([f.name for f, _ in plan_retention(self.root, 3, self.now)],
                         [f'libraai-202610{day:02d}T010000Z.db' for day in (3, 2, 1)])

    def test_missing_sidecar_aborts_all_deletions(self):
        for day in range(1, 5): self.create(day)
        self.create(5, False)
        with self.assertRaisesRegex(ValueError, 'Unverified backup'):
            plan_retention(self.root, 2, self.now)

    def test_rejects_too_low_retention(self):
        with self.assertRaises(ValueError): plan_retention(self.root, 1, self.now)

    def test_ignores_symlinks_and_unexpected_names(self):
        for day in range(1, 5): self.create(day)
        try:
            (self.root / 'libraai-20261007T010000Z.db').symlink_to(self.root / 'libraai-20261001T010000Z.db')
        except OSError:
            pass
        (self.root / 'other.db').write_bytes(b'x')
        self.assertEqual(len(plan_retention(self.root, 2, self.now)), 2)

    def test_future_dated_files_not_pruned(self):
        for day in range(1, 5): self.create(day)
        future = self.create(30)
        self.assertNotIn(future, [f for f, _ in plan_retention(self.root, 2, self.now)])

    def test_tampered_backup_aborts(self):
        for day in range(1, 5): self.create(day)
        self.create(4).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'Unverified backup'):
            plan_retention(self.root, 2, self.now)

    def test_malformed_checksum_aborts(self):
        for day in range(1, 5): self.create(day)
        (self.root / 'libraai-20261004T010000Z.db.sha256').write_text('bad digest')
        with self.assertRaises(ValueError): plan_retention(self.root, 2, self.now)


if __name__ == '__main__': unittest.main()
