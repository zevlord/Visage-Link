import os
import sys
import asyncio
import unittest

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import memory
from server import chat_handler

class TestVisageLinkCore(unittest.TestCase):
    def test_sqlite_memory(self):
        test_fact = "Test fact: loves eating candy"
        memory.save_fact(test_fact, user_id="test_user")
        ctx = memory.get_memory_context(user_id="test_user")
        self.assertIn(test_fact, ctx)

    def test_autonomy_controls(self):
        chat_handler.set_autonomous(False)
        self.assertFalse(chat_handler.autonomous_enabled)
        chat_handler.set_autonomous(True)
        self.assertTrue(chat_handler.autonomous_enabled)
        chat_handler.touch_activity()

if __name__ == "__main__":
    unittest.main()
