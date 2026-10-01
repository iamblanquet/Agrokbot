import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(server, "DATA", Path(self.temp.name)),
            patch.object(server, "DB", Path(self.temp.name) / "security.sqlite3"),
            patch.object(server, "ERP_MODE", "demo"),
            patch.object(server, "TG_MODE", "demo"),
        ]
        for item in self.patches:
            item.start()
        server.initialize()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def add_user(self, username, pin, employee, assignment, active=1):
        with server.connection() as db:
            db.execute(
                "INSERT INTO app_users VALUES (?,?,?,?,?,?,?)",
                (username, server.pin_hash(pin), employee, employee, assignment, active, server.now()),
            )
            db.execute(
                "INSERT INTO user_profiles VALUES (?,?,?,?,?)",
                (username, employee, employee, assignment, server.now()),
            )

    def test_pin_is_salted_and_verifiable(self):
        first = server.pin_hash("1234")
        second = server.pin_hash("1234")
        self.assertTrue(first.startswith("scrypt$"))
        self.assertNotEqual(first, second)
        self.assertTrue(server.verify_pin("1234", first))
        self.assertFalse(server.verify_pin("9999", first))

    def test_catalog_is_limited_to_the_session_assignment(self):
        self.add_user("abner", "1234", "AGROKOOL-0003", "assign-abner")
        data = {
            "projects": [{"id": "p1"}, {"id": "p2"}],
            "tasks": [
                {"id": "t1", "projectId": "p1", "responsible": {"assignmentId": "assign-abner", "employeeNumber": "AGROKOOL-0003", "fullName": "Abner"}},
                {"id": "t2", "projectId": "p2", "responsible": {"assignmentId": "assign-javier", "employeeNumber": "AGROKOOL-0004", "fullName": "Javier"}},
            ],
            "employees": [],
            "fetchedAt": server.now(),
        }
        visible = server.catalog_for_user(data, "abner")
        self.assertEqual([task["id"] for task in visible["tasks"]], ["t1"])
        self.assertEqual([project["id"] for project in visible["projects"]], ["p1"])

    def test_catalog_is_empty_without_employee_relation(self):
        data = {
            "projects": [{"id": "p1"}],
            "tasks": [{"id": "t1", "projectId": "p1", "responsible": {"assignmentId": "a1", "employeeNumber": "e1"}}],
            "employees": [],
            "fetchedAt": server.now(),
        }
        visible = server.catalog_for_user(data, "unregistered")
        self.assertEqual(visible["projects"], [])
        self.assertEqual(visible["tasks"], [])
        self.assertEqual(visible["fetchedAt"], data["fetchedAt"])

    def test_catalog_can_match_by_employee_number(self):
        self.add_user("employee-only", "1234", "AGROKOOL-0003", "")
        data = {
            "projects": [{"id": "p1"}, {"id": "p2"}],
            "tasks": [
                {"id": "t1", "projectId": "p1", "responsible": {"assignmentId": "other", "employeeNumber": "AGROKOOL-0003"}},
                {"id": "t2", "projectId": "p2", "responsible": {"assignmentId": "other", "employeeNumber": "AGROKOOL-0004"}},
            ],
            "employees": [],
            "fetchedAt": server.now(),
        }
        visible = server.catalog_for_user(data, "employee-only")
        self.assertEqual([task["id"] for task in visible["tasks"]], ["t1"])
        self.assertEqual([project["id"] for project in visible["projects"]], ["p1"])

    def test_admin_is_global_but_unmapped_telegram_is_empty(self):
        data = {"projects": [{"id": "p1"}], "tasks": [{"id": "t1", "projectId": "p1"}], "employees": [], "fetchedAt": server.now()}
        self.assertEqual(server.catalog_for_user(data, server.USER), data)
        visible = server.catalog_for_user(data, "telegram:123")
        self.assertEqual(visible["projects"], [])
        self.assertEqual(visible["tasks"], [])

    def test_user_cannot_create_a_report_for_another_assignment(self):
        self.add_user("abner", "1234", "AGROKOOL-0003", "assign-abner")
        data = {
            "projects": [{"id": "p2"}],
            "tasks": [{"id": "t2", "projectId": "p2", "code": "T2", "name": "Otra tarea", "progressBps": 0, "responsible": {"assignmentId": "assign-javier", "employeeNumber": "AGROKOOL-0004", "fullName": "Javier"}}],
            "employees": [],
            "fetchedAt": server.now(),
        }
        payload = {"id": "a" * 16, "taskId": "t2", "baseProgressBps": 0, "progressBps": 100, "notes": "Prueba", "operationDate": "2026-01-01"}
        with patch.object(server, "catalog", return_value=data):
            with self.assertRaises(server.Problem) as error:
                server.create_report(payload, "abner")
        self.assertEqual(error.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
