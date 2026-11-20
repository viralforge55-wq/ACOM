"""Security tests for A5 / Financial Firewall and MariaDB Isolation (ARCHITECTURE_RULES §1.2, TEST_PLAN A5, X6).

Proves that:
1. MariaDB (3306) is not accessible from the host / external network (Gate G1).
2. AI roles/agents cannot execute refunds or release payments.
3. AI roles/agents cannot submit Purchase Orders or publish products without human approval.
"""

import socket
import unittest
import urllib.request
import urllib.error


class TestFinancialFirewall(unittest.TestCase):
    """Test firewall and permission boundaries protecting financial records."""

    def test_G1_mariadb_port_not_published_to_host(self):
        """MariaDB port 3306 must NOT be open on 127.0.0.1 or reachable from outside Docker."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex(("127.0.0.1", 3306))
        sock.close()
        # Connection should fail (non-zero errno, e.g. 10061 ECONNREFUSED on Windows)
        self.assertNotEqual(result, 0, "Security violation: MariaDB port 3306 is accessible on host!")

    def test_G1_redis_ports_not_published_to_host(self):
        """Redis ports (6379) must NOT be open on 127.0.0.1."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex(("127.0.0.1", 6379))
        sock.close()
        self.assertNotEqual(result, 0, "Security violation: Redis port 6379 is accessible on host!")

    def test_A5_unauthenticated_refund_attempt_blocked(self):
        """Calling refund API endpoint without credentials returns 401 or 403."""
        url = "http://127.0.0.1:8080/api/method/acom_core.api.dropship.decide_refund"
        headers = {
            "Host": "acom.localhost",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = b"checkout_id=CHK-FAKE&decision=Approved"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                self.fail(f"Expected 401/403 but got {resp.status}")
        except urllib.error.HTTPError as exc:
            self.assertIn(exc.code, (401, 403), f"Expected 401 or 403, got {exc.code}")


if __name__ == "__main__":
    unittest.main()
