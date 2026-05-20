from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

import sync_folders


class TempWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.output = self.root / "output"
        self.source.mkdir()
        self.target.mkdir()
        self.output.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def config(self, **overrides: object) -> sync_folders.SyncConfig:
        values = {
            "source": self.source,
            "target": self.target,
            "output_dir": self.output,
            "batch_size": 2,
            "max_retries": 3,
            "retry_batch_sizes": (3, 2, 1),
            "rsync_bin": "rsync",
        }
        values.update(overrides)
        return sync_folders.SyncConfig(**values)


class ConfigTests(TempWorkspace):
    def test_build_config_uses_env_defaults_and_validates_directories(self) -> None:
        env = {
            "SYNC_OUTPUT_DIR": str(self.output),
            "SYNC_BATCH_SIZE": "3",
            "SYNC_MAX_RETRIES": "4",
            "SYNC_RETRY_BATCH_SIZES": "4,2,1",
            "RSYNC_BIN": "custom-rsync",
        }

        config = sync_folders.build_config(self.source, self.target, env=env)

        self.assertEqual(self.source, config.source)
        self.assertEqual(self.target, config.target)
        self.assertEqual(self.output, config.output_dir)
        self.assertEqual(3, config.batch_size)
        self.assertEqual(4, config.max_retries)
        self.assertEqual((4, 2, 1), config.retry_batch_sizes)
        self.assertEqual("custom-rsync", config.rsync_bin)

    def test_build_config_rejects_missing_directories_and_bad_batch_size(self) -> None:
        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source / "missing", self.target, env={})

        missing_target = self.root / "new" / "target"
        config = sync_folders.build_config(self.source, missing_target, env={})
        self.assertEqual(missing_target, config.target)
        self.assertTrue(missing_target.is_dir())

        target_file = self.root / "target-file"
        target_file.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source, target_file, env={})

        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source, self.target, output_dir=self.root / "missing", env={})

        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source, self.target, batch_size=0, env={})

        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source, self.target, max_retries=0, env={})

        with self.assertRaises(sync_folders.SyncError):
            sync_folders.build_config(self.source, self.target, retry_batch_sizes=(3, 0), env={})

    def test_positive_int_rejects_invalid_values(self) -> None:
        self.assertEqual(5, sync_folders.positive_int("5"))
        self.assertEqual((3, 2, 1), sync_folders.positive_int_tuple("3,2,1"))

        for value in ("0", "-1", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    sync_folders.positive_int(value)

        for value in ("", "3,0", "3,abc"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    sync_folders.positive_int_tuple(value)


class DifferenceTests(TempWorkspace):
    def test_compute_differences_finds_missing_changed_and_unchanged_files(self) -> None:
        nested = self.source / "nested"
        nested.mkdir()
        target_nested = self.target / "nested"
        target_nested.mkdir()

        unchanged = self.source / "unchanged.txt"
        unchanged.write_text("same\n", encoding="utf-8")
        shutil.copy2(unchanged, self.target / "unchanged.txt")

        (nested / "missing.txt").write_text("missing\n", encoding="utf-8")
        (self.source / "changed.txt").write_text("source\n", encoding="utf-8")
        (self.target / "changed.txt").write_text("target-target\n", encoding="utf-8")

        report = sync_folders.compute_differences(self.source, self.target)

        self.assertEqual(3, report.total_files)
        self.assertEqual((Path("nested/missing.txt"),), report.missing)
        self.assertEqual((Path("changed.txt"),), report.changed)
        self.assertEqual((Path("nested/missing.txt"), Path("changed.txt")), report.sync_paths)

    def test_files_differ_uses_size_and_mtime(self) -> None:
        source_file = self.source / "file.txt"
        target_file = self.target / "file.txt"
        source_file.write_text("same\n", encoding="utf-8")

        self.assertTrue(sync_folders.files_differ(source_file, target_file))

        shutil.copy2(source_file, target_file)
        self.assertFalse(sync_folders.files_differ(source_file, target_file))

        target_file.write_text("different\n", encoding="utf-8")
        self.assertTrue(sync_folders.files_differ(source_file, target_file))

        target_file.write_text("same\n", encoding="utf-8")
        os.utime(source_file, ns=(1_704_051_060_000_000_000, 1_704_051_060_000_000_000))
        os.utime(target_file, ns=(1_704_051_120_000_000_000, 1_704_051_120_000_000_000))
        self.assertTrue(sync_folders.files_differ(source_file, target_file))

        os.utime(source_file, ns=(1_704_051_060_100_000_000, 1_704_051_060_100_000_000))
        os.utime(target_file, ns=(1_704_051_060_900_000_000, 1_704_051_060_900_000_000))
        self.assertFalse(sync_folders.files_differ(source_file, target_file))

    def test_diff_report_formats_empty_and_populated_sections(self) -> None:
        report = sync_folders.DifferenceResult(
            total_files=2,
            missing=(Path("missing.txt"),),
            changed=(Path("nested/changed.txt"),),
        )

        sync_folders.write_diff_report(report, self.output / "diff_files.txt")

        contents = (self.output / "diff_files.txt").read_text(encoding="utf-8")
        self.assertIn("Missing files (1):", contents)
        self.assertIn("missing.txt", contents)
        self.assertIn("Changed files (1):", contents)
        self.assertIn("nested/changed.txt", contents)
        self.assertEqual("(none)", sync_folders.format_path_list(()))


class SyncExecutionTests(TempWorkspace):
    def logger(self) -> sync_folders.Logger:
        logger = sync_folders.Logger(self.output / "sync_folders.log", stream=StringIO())
        logger.reset()
        return logger

    def test_batch_helpers_create_expected_files_and_commands(self) -> None:
        batch_file = self.output / "batch.txt"
        paths = (Path("one.txt"), Path("nested/two.txt"))
        config = self.config(rsync_bin="custom-rsync")

        sync_folders.write_batch_file(paths, batch_file)

        self.assertEqual(b"one.txt\0nested/two.txt\0", batch_file.read_bytes())
        self.assertEqual([(Path("one.txt"), Path("nested/two.txt"))], list(sync_folders.batched(paths, 2)))
        command = sync_folders.rsync_command(config, batch_file)
        self.assertEqual("custom-rsync", command[0])
        self.assertIn(f"--files-from={batch_file}", command)
        self.assertIn(f"{self.source}/", command)

    def test_run_batch_success_and_empty_batch(self) -> None:
        config = self.config()
        logger = self.logger()

        self.assertTrue(sync_folders.run_batch(config, 1, (), logger))

        with mock.patch("sync_folders.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(sync_folders.run_batch(config, 1, (Path("one.txt"),), logger))

        self.assertEqual(1, run.call_count)
        self.assertIn("[Batch 1] Success", config.log_file.read_text(encoding="utf-8"))
        self.assertFalse(config.failed_list.exists())

    def test_run_batch_failure_records_failed_files(self) -> None:
        config = self.config()
        logger = self.logger()

        with mock.patch("sync_folders.subprocess.run", return_value=subprocess.CompletedProcess([], 23)):
            self.assertFalse(sync_folders.run_batch(config, 1, (Path("bad.txt"),), logger))

        self.assertEqual((Path("bad.txt"),), sync_folders.read_failed_paths(config.failed_list))

    def test_failed_file_helpers_refresh_live_unresolved_list(self) -> None:
        config = self.config()
        (self.source / "synced.txt").write_text("same\n", encoding="utf-8")
        shutil.copy2(self.source / "synced.txt", self.target / "synced.txt")
        (self.source / "missing.txt").write_text("missing\n", encoding="utf-8")

        sync_folders.write_failed_paths(
            config.failed_list,
            (Path("synced.txt"), Path("missing.txt"), Path("missing.txt")),
        )

        unresolved = sync_folders.refresh_failed_paths(
            config,
            sync_folders.read_failed_paths(config.failed_list),
        )

        self.assertEqual((Path("missing.txt"),), unresolved)
        self.assertEqual("missing.txt\n", config.failed_list.read_text(encoding="utf-8"))

    def test_retry_failed_files_removes_files_that_sync_on_retry(self) -> None:
        config = self.config()
        logger = self.logger()
        (self.source / "flaky.txt").write_text("eventually copied\n", encoding="utf-8")
        sync_folders.write_failed_paths(config.failed_list, (Path("flaky.txt"),))

        def copy_then_report_failure(
            config: sync_folders.SyncConfig,
            paths: tuple[Path, ...],
            logger: sync_folders.Logger,
        ) -> int:
            for path in paths:
                shutil.copy2(config.source / path, config.target / path)
            return 23

        with mock.patch("sync_folders.run_rsync", side_effect=copy_then_report_failure) as run_rsync:
            self.assertEqual((), sync_folders.retry_failed_files(config, logger))

        self.assertEqual(1, run_rsync.call_count)
        self.assertFalse(config.failed_list.exists())

    def test_retry_failed_files_exhausts_retries_and_keeps_unresolved_file(self) -> None:
        config = self.config(max_retries=3)
        logger = self.logger()
        (self.source / "stuck.txt").write_text("still missing\n", encoding="utf-8")
        sync_folders.write_failed_paths(config.failed_list, (Path("stuck.txt"),))

        with (
            mock.patch("sync_folders.run_rsync", return_value=23) as run_rsync,
            mock.patch("sync_folders.time.sleep") as sleep,
        ):
            self.assertEqual((Path("stuck.txt"),), sync_folders.retry_failed_files(config, logger))

        self.assertEqual(3, run_rsync.call_count)
        self.assertEqual(2, sleep.call_count)
        self.assertEqual("stuck.txt\n", config.failed_list.read_text(encoding="utf-8"))

    def test_retry_failed_files_uses_configured_batch_size_schedule(self) -> None:
        config = self.config(max_retries=3, retry_batch_sizes=(3, 2, 1))
        logger = self.logger()
        paths = tuple(Path(f"file-{index}.txt") for index in range(4))
        for path in paths:
            (self.source / path).write_text(path.name, encoding="utf-8")
        sync_folders.write_failed_paths(config.failed_list, paths)

        with (
            mock.patch("sync_folders.run_rsync", return_value=23) as run_rsync,
            mock.patch("sync_folders.time.sleep"),
        ):
            self.assertEqual(paths, sync_folders.retry_failed_files(config, logger))

        retried_groups = [call.args[1] for call in run_rsync.call_args_list]
        self.assertEqual(
            [
                paths[0:3],
                paths[3:4],
                paths[0:2],
                paths[2:4],
                paths[0:1],
                paths[1:2],
                paths[2:3],
                paths[3:4],
            ],
            retried_groups,
        )

    def test_sync_files_batches_success_and_failure(self) -> None:
        config = self.config(batch_size=2)
        logger = self.logger()
        paths = (Path("one.txt"), Path("two.txt"), Path("three.txt"))

        with mock.patch("sync_folders.run_batch", return_value=True) as run_batch:
            self.assertEqual(0, sync_folders.sync_files(config, paths, logger))

        self.assertEqual(2, run_batch.call_count)
        self.assertFalse(config.failed_list.exists())

        logger.reset()

        def fail_first_batch(
            config: sync_folders.SyncConfig,
            batch_number: int,
            paths: tuple[Path, ...],
            logger: sync_folders.Logger,
        ) -> bool:
            sync_folders.append_failed_paths(config.failed_list, paths)
            return False

        with (
            mock.patch("sync_folders.run_batch", side_effect=fail_first_batch),
            mock.patch("sync_folders.retry_failed_files", return_value=(Path("bad.txt"),)),
        ):
            self.assertEqual(1, sync_folders.sync_files(config, (Path("bad.txt"),), logger))

        self.assertIn("bad.txt", config.failed_list.read_text(encoding="utf-8"))

        with (
            mock.patch("sync_folders.run_batch", side_effect=fail_first_batch),
            mock.patch("sync_folders.retry_failed_files", return_value=()),
        ):
            self.assertEqual(0, sync_folders.sync_files(config, (Path("bad.txt"),), logger))

        self.assertFalse(config.failed_list.exists())

    def test_sync_folders_no_work_and_real_rsync_copy(self) -> None:
        unchanged = self.source / "same.txt"
        unchanged.write_text("same\n", encoding="utf-8")
        shutil.copy2(unchanged, self.target / "same.txt")

        config = self.config()
        self.assertEqual(0, sync_folders.sync_folders(config, stream=StringIO()))
        self.assertIn("No missing or changed files", config.log_file.read_text(encoding="utf-8"))

        (self.source / "missing.txt").write_text("hello\n", encoding="utf-8")
        self.assertEqual(0, sync_folders.sync_folders(config, stream=StringIO()))
        self.assertEqual("hello\n", (self.target / "missing.txt").read_text(encoding="utf-8"))


class CliTests(TempWorkspace):
    def test_main_handles_validation_error_and_success(self) -> None:
        with mock.patch("sys.stderr") as stderr:
            self.assertEqual(1, sync_folders.main([str(self.source / "missing"), str(self.target)]))

        self.assertTrue(stderr.write.called)

        with mock.patch("sync_folders.sync_folders", return_value=0) as sync:
            result = sync_folders.main(
                [
                    str(self.source),
                    str(self.target),
                    "--output-dir",
                    str(self.output),
                    "--batch-size",
                    "4",
                    "--max-retries",
                    "5",
                    "--retry-batch-sizes",
                    "4,2,1",
                    "--rsync-bin",
                    "custom-rsync",
                ]
            )

        self.assertEqual(0, result)
        config = sync.call_args.args[0]
        self.assertEqual(4, config.batch_size)
        self.assertEqual(5, config.max_retries)
        self.assertEqual((4, 2, 1), config.retry_batch_sizes)
        self.assertEqual("custom-rsync", config.rsync_bin)

    def test_parse_args_rejects_missing_arguments(self) -> None:
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                sync_folders.parse_args([])


if __name__ == "__main__":
    unittest.main()
