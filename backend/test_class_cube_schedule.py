import unittest
from datetime import date, datetime

from app.class_cube_schedule import (
    due_schedule_key,
    normalize_schedule_times,
)


class ClassCubeScheduleTest(unittest.TestCase):
    def test_normalizes_sorts_and_deduplicates_times(self):
        self.assertEqual(
            normalize_schedule_times(
                ["18:00:00", "08:00:00", "08:00:00"]
            ),
            ["08:00:00", "18:00:00"],
        )

    def test_due_key_respects_date_range(self):
        task = {
            "schedule_times": ["08:00:00"],
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 8, 31),
            "last_schedule_key": "",
        }
        self.assertEqual(
            due_schedule_key(task, datetime(2026, 8, 1, 8, 0, 30)),
            "2026-08-01T08:00:00",
        )
        self.assertIsNone(
            due_schedule_key(task, datetime(2026, 9, 1, 8, 0, 10))
        )

    def test_old_task_without_times_is_never_due(self):
        self.assertIsNone(
            due_schedule_key(
                {"schedule_times": []},
                datetime(2026, 8, 1, 8, 0, 0),
            )
        )

