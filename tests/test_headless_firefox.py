#!/usr/bin/env python3
"""Stock Firefox smoke using Selenium/geckodriver; optional test dependencies."""
import os,time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from test_headless_mvp import HeadlessTests
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo');driver=None
try:
    options=Options();options.add_argument('-headless')
    options.set_preference('gfx.webrender.all',False)
    options.set_preference('layers.acceleration.disabled',True)
    if os.environ.get('FIREFOX_BINARY'):options.binary_location=os.environ['FIREFOX_BINARY']
    driver=webdriver.Firefox(options=options,service=Service(executable_path=os.environ.get('GECKODRIVER','geckodriver'),log_output='/tmp/midi-geckodriver.log'))
    wait=WebDriverWait(driver,12)
    def connected():wait.until(lambda d:'CONNECTED' in d.find_element(By.ID,'connection').text and not d.find_element(By.ID,'connection').text.startswith('DISCONNECTED'))
    def button(text,scope=None):
        root=scope or driver
        return root.find_element(By.XPATH,f".//button[text()='{text}']")
    driver.get(HeadlessTests.base);connected()
    assert len(driver.find_elements(By.CSS_SELECTOR,'.phrase'))==16
    assert len(driver.find_elements(By.CSS_SELECTOR,'.instrument'))==3
    sw=driver.find_element(By.CSS_SELECTOR,'[data-switch-id="1"]')
    button('TEST TAP',sw).click();wait.until(lambda d:api.call()['activeNotes']>0)
    button('PANIC').click();wait.until(lambda d:api.call()['activeNotes']==0)
    button('SAVE PATCH').click();wait.until(lambda d:d.find_element(By.ID,'patch-status').text=='PATCH SAVED')
    button('LOAD PATCH').click();wait.until(lambda d:d.find_element(By.ID,'patch-status').text=='PATCH LOADED')
    button('PLAY',driver.find_element(By.CSS_SELECTOR,'.phrase')).click();wait.until(lambda d:api.call()['activeNotes']>0)
    before=api.call();HeadlessTests.stop_web()
    wait.until(lambda d:d.find_element(By.ID,'connection').text.startswith('DISCONNECTED'))
    HeadlessTests.start_web();connected();after=api.call()
    assert after['engineSessionId']==before['engineSessionId'] and after['sampleClock']>before['sampleClock']
    driver.set_window_size(440,900)
    assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
    driver.save_screenshot('/tmp/midi-firefox-first-test.png')
    driver.quit();driver=None;before=api.call();time.sleep(.6);after=api.call()
    assert after['midiCount']>before['midiCount']
    api.command('panic');print('PASS stock Firefox: authoritative state, TEST, phrase PLAY, PANIC, SAVE/LOAD, WebSocket reconnect, responsive layout and browser closure')
finally:
    if driver:driver.quit()
    HeadlessTests.tearDownClass()
