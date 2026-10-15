#!/usr/bin/env python3
"""Positive and negative browser fixtures for the screenshot layout guard."""
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from screenshots import AUDIT
from playwright.sync_api import sync_playwright

class LayoutAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        args=dict(headless=True,args=['--no-sandbox'])
        browser=os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
        if browser: args['executable_path']=browser
        cls.browser=cls.pw.chromium.launch(**args)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()
    def audit(self,html):
        page=self.browser.new_page(viewport=dict(width=320,height=240))
        try:
            page.set_content(html)
            return page.evaluate(AUDIT)
        finally:page.close()
    def test_overflow_is_rejected(self):
        self.assertTrue(self.audit('<button style="width:500px">Wide</button>'))
    def test_clipped_control_is_rejected(self):
        self.assertTrue(self.audit('<div style="height:10px;overflow:hidden"><button>Tall</button></div>'))
    def test_keyboard_inaccessible_control_is_rejected(self):
        self.assertTrue(self.audit('<button tabindex="-1">Unreachable</button>'))
    def test_vertical_scrolling_and_closed_details_are_allowed(self):
        self.assertEqual(self.audit('<div style="height:500px"></div><button>Reachable</button><details><summary>Closed</summary><button style="width:500px">Hidden</button></details>'),[])
    def test_fixed_content_that_cannot_be_scrolled_is_rejected(self):
        self.assertTrue(self.audit('<button style="position:fixed;top:300px">Hidden</button>'))
    def test_clipped_button_label_is_rejected(self):
        self.assertTrue(self.audit('<button style="width:30px;white-space:nowrap;overflow:hidden">Long label</button>'))
    def test_modal_background_is_inert(self):
        self.assertEqual(self.audit('<button tabindex="-1">Background</button><dialog id="d"><button>Close</button></dialog><script>d.showModal()</script>'),[])

if __name__=='__main__':unittest.main()
