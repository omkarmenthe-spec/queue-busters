import importlib.util
import json
import secrets
import shutil
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier

from werkzeug.security import generate_password_hash


PROJECT_FOLDER = Path(__file__).resolve().parents[1]


class QueueReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Copy only application code and templates.
        # Never copy the real database or staff configuration.
        cls.temp_folder = tempfile.TemporaryDirectory(
            prefix="queue_busters_tests_"
        )
        cls.addClassCleanup(cls.temp_folder.cleanup)

        test_folder = Path(cls.temp_folder.name)

        shutil.copy2(
            PROJECT_FOLDER / "app.py",
            test_folder / "app.py",
        )

        shutil.copytree(
            PROJECT_FOLDER / "templates",
            test_folder / "templates",
        )

        instance_folder = test_folder / "instance"
        instance_folder.mkdir()

        # These credentials exist only in the temporary test app.
        cls.test_password = secrets.token_urlsafe(24)

        configuration = {
            "secret_key": secrets.token_hex(32),
            "password_hash": generate_password_hash(cls.test_password),
        }

        (instance_folder / "staff_config.json").write_text(
            json.dumps(configuration),
            encoding="utf-8",
        )

        module_name = "queue_busters_isolated_test"

        spec = importlib.util.spec_from_file_location(
            module_name,
            test_folder / "app.py",
        )

        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = cls.module
        cls.addClassCleanup(sys.modules.pop, module_name, None)

        spec.loader.exec_module(cls.module)

        cls.app = cls.module.app
        cls.app.config["TESTING"] = True

        cls.database = Path(cls.module.DATABASE).resolve()

        # Stop immediately if the app points outside the temporary folder.
        if not cls.database.is_relative_to(test_folder.resolve()):
            raise RuntimeError(
                "Test stopped: the app is not using the temporary database."
            )

    def setUp(self):
        # Clear only the isolated test queue before each test.
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DELETE FROM tokens")
            connection.commit()

    def read_tokens(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row

            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM tokens ORDER BY id"
                ).fetchall()
            ]

    def create_token(self, service="fees"):
        client = self.app.test_client()

        response = client.post(
            "/tokens",
            data={"service": service},
        )

        self.assertEqual(response.status_code, 303)

        return int(
            response.headers["Location"].rstrip("/").split("/")[-1]
        )

    def staff_login(self):
        client = self.app.test_client()

        response = client.get("/staff/login")
        self.assertEqual(response.status_code, 200)

        with client.session_transaction() as state:
            csrf = state["csrf_token"]

        response = client.post(
            "/staff/login",
            data={
                "password": self.test_password,
                "csrf_token": csrf,
            },
        )

        self.assertEqual(response.status_code, 303)

        with client.session_transaction() as state:
            self.assertTrue(state.get("staff"))
            csrf = state["csrf_token"]

        return client, csrf

    def test_simultaneous_requests_create_unique_tokens(self):
        """Twelve overlapping requests must create twelve unique tokens."""
        request_count = 12
        barrier = Barrier(request_count)

        services = [
            "bonafide",
            "fees",
            "exam",
            "verification",
        ]

        def submit(index):
            client = self.app.test_client()
            barrier.wait(timeout=15)

            response = client.post(
                "/tokens",
                data={"service": services[index % len(services)]},
            )

            return (
                response.status_code,
                response.headers.get("Location", ""),
            )

        with ThreadPoolExecutor(
            max_workers=request_count
        ) as executor:
            results = list(executor.map(submit, range(request_count)))

        self.assertTrue(
            all(status == 303 for status, _ in results),
            f"Some requests failed: {results}",
        )

        locations = [location for _, location in results]

        self.assertEqual(
            len(set(locations)),
            request_count,
            "Different requests received the same token.",
        )

        tokens = self.read_tokens()

        self.assertEqual(len(tokens), request_count)
        self.assertEqual(
            len({token["id"] for token in tokens}),
            request_count,
        )
        self.assertTrue(
            all(token["status"] == "waiting" for token in tokens)
        )

    def test_simultaneous_staff_calls_serve_only_one_token(self):
        """Repeated concurrent Call next actions must not serve two tokens."""
        token_ids = [
            self.create_token("fees"),
            self.create_token("exam"),
            self.create_token("bonafide"),
        ]

        staff, csrf = self.staff_login()

        cookie_name = self.app.config["SESSION_COOKIE_NAME"]
        cookie = staff.get_cookie(cookie_name)
        self.assertIsNotNone(cookie)

        request_count = 6
        barrier = Barrier(request_count)

        clients = [
            self.app.test_client()
            for _ in range(request_count)
        ]

        for client in clients:
            client.set_cookie(cookie_name, cookie.value)

        def call_next(client):
            barrier.wait(timeout=15)

            return client.post(
                "/staff/call-next",
                data={"csrf_token": csrf},
            ).status_code

        with ThreadPoolExecutor(
            max_workers=request_count
        ) as executor:
            statuses = list(executor.map(call_next, clients))

        self.assertTrue(
            all(status == 303 for status in statuses),
            f"Unexpected responses: {statuses}",
        )

        tokens = self.read_tokens()

        serving = [
            token for token in tokens
            if token["status"] == "serving"
        ]

        waiting = [
            token for token in tokens
            if token["status"] == "waiting"
        ]

        self.assertEqual(
            len(serving),
            1,
            "More than one token is being served.",
        )

        self.assertEqual(
            serving[0]["id"],
            min(token_ids),
            "The earliest waiting token was not called.",
        )

        self.assertEqual(len(waiting), 2)

    def test_invalid_services_do_not_create_tokens(self):
        """Missing or unknown services must be rejected."""
        client = self.app.test_client()

        for data in [
            {},
            {"service": ""},
            {"service": "unknown-service"},
        ]:
            with self.subTest(data=data):
                response = client.post("/tokens", data=data)
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.read_tokens(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)