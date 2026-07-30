import re
import tempfile
import unittest
from pathlib import Path

from app.class_cube_logging import (
    ClassCubeLogStore,
    create_class_cube_logger,
)


class ClassCubeLoggingTest(unittest.TestCase):
    def test_writes_timestamped_file_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "class_cube.log"
            store = ClassCubeLogStore()
            logger = create_class_cube_logger(store, path)

            logger.info("任务开始")

            line = store.snapshot(1)[0]
            self.assertRegex(
                line,
                r"^\d{4}-\d{2}-\d{2} .+ \[INFO\] 任务开始$",
            )
            self.assertIn(
                "任务开始",
                path.read_text(encoding="utf-8"),
            )
            for handler in tuple(logger.handlers):
                handler.close()
    def test_redacts_sensitive_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "class_cube.log"
            logger = create_class_cube_logger(
                ClassCubeLogStore(),
                path,
            )

            logger.info(
                "cookie=secret password=123456 "
                "remember_student_abc=token-value"
            )

            content = path.read_text(encoding="utf-8")
            self.assertNotIn("secret", content)
            self.assertNotIn("123456", content)
            self.assertNotIn("token-value", content)
            self.assertTrue(re.search(r"cookie=\*+", content))
            for handler in tuple(logger.handlers):
                handler.close()
