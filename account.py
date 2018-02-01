#!/usr/bin/env python
# -*- coding:utf-8 -*-

import base64
import json
import os
import sys
import time
import traceback

from datetime import tzinfo, timedelta, datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from utils import randomSleep, reprDict, findElement, inputElement

class Inputter:

    def __init__(self, inputPath=None, outputPath=None, retries=100):

        self.inputPath = inputPath
        self.outputPath = outputPath

        self.retries = retries

        self.reset()

    def reset(self):

        self.content = None

    def getInput(self, notice=None, msg=None, prompt=None, length=0):

        if self.inputPath is not None:
            self.getInputFromFile(notice, msg, prompt, length)
        else:
            self.getInputFromStdin(notice, msg, prompt, length)

        if isinstance(self.content, str):
            self.content = self.content.decode('utf-8', 'ignore')

        return self.content

    def getInputFromFile(self, notice, msg, prompt, length):

        with open(self.outputPath, 'w') as fp:

            content = dict()

            content['notice'] = notice
            content['msg'] = msg
            content['prompt'] = prompt

            fp.write(reprDict(content))

        for i in range(self.retries):

            time.sleep(1)

            try:
                with open(self.inputPath) as fp:

                    content = fp.read()
                    content = content.strip()

                    if ((length is not 0 and len(content) is length) or (length is 0 and len(content) > 0)) \
                        and self.content != content:

                        self.content = content
                        break

            except IOError as e:
                pass

        return self.content

    def getInputFromStdin(self, notice, msg, prompt, length):

        for i in range(self.retries):

            print 'Notice:', notice
            print 'Message:', msg

            content = raw_input('{}:\n'.format(prompt))
            content = content.strip()

            if (length is not 0 and len(content) is length) or (length is 0 and len(content) > 0):
                self.content = content
                break

        return self.content

class Account:

    def __init__(self, db, userId):

        self.db = db
        self.userId = userId

        self.initUserConfig()

    def initUserConfig(self):

        sql = ''' SELECT
                      config
                  FROM
                      `configs`
                  WHERE
                      userId = {} '''.format(self.userId)

        result = self.db.query(sql)

        config = None

        for row in result:
            config = row['config']

        if config is None:
            raise Exception('Config is invalid for user {}'.format(self.userId))

        try:
            configObj = json.loads(config.decode('utf-8', 'ignore'))
        except ValueError as e:
            raise Exception('Config is invalid for user {}'.format(self.userId))

        ## Login
        obj = configObj.pop('login')

        self.username = obj.pop('username')
        password = obj.pop('password')
        self.password = base64.b64decode(password)

    def login(self, inputPath=None, outputPath=None, config='templates/login.json', retries=100):

        if config is None:
            config='templates/login.json'

        with open(config) as fp:
            content = fp.read()

        try:
            configObj = json.loads(content.decode('utf-8', 'ignore'))
        except ValueError as e:
            raise Exception('{} is not valid config file.'.format(config))

        obj = configObj.pop('config')

        driverType = obj.pop('driver')

        loginUrl = obj.pop('login-url')
        verificationUrl = obj.pop('verification-url')

        if 'firefox' == driverType:

            # https://github.com/mozilla/geckodriver/releases
            driver = webdriver.Firefox()

        else: # Chrome

            # https://chromedriver.storage.googleapis.com/index.html
            driver = webdriver.Chrome()

        try:

            driver.get(loginUrl)
            driver.set_script_timeout(10)

            # Username and password
            randomSleep(1, 2)
            inputElement(driver.find_element_by_id('username'), self.username)

            randomSleep(1, 2)
            inputElement(driver.find_element_by_id('password'), self.password)

            # Submit
            buttonElement = driver.find_element_by_id('loginBtn')

            randomSleep(1, 2)
            buttonElement.click()

            verificationInputter = Inputter(inputPath, outputPath)

            for i in range(retries):

                if loginUrl != driver.current_url:
                    break

                time.sleep(1)

                # Need code
                if self.needCode(driver):
                    continue

                # Verification
                if self.verify(driver, verificationInputter):
                    continue

            codeInputter = Inputter(inputPath, outputPath)

            for i in range(retries):

                if verificationUrl != driver.current_url:
                    break

                time.sleep(1)

                self.inputCode(driver, codeInputter)

            time.sleep(3)

            self.updateDb(driver)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print 'Error occurs at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            traceback.print_exc(file=sys.stdout)
        finally:
            driver.quit()

        time.sleep(1)

    def needCode(self, driver):

        continueButtonName = '//a[@class="btn-pop btn-continue"]'

        element = findElement(driver, continueButtonName)

        if element is None or not element.is_displayed() or not element.is_enabled():
            return False

        element.click()

        time.sleep(3) # Sleep a little longer

        return True

    def inputCode(self, driver, inputter):

        tipsName = '//div[@class="item item-tips"]'
        retransmitButtonName = '//a[@class="btn-retransmit"]'
        inputName = '//input[@class="txt-input txt-phone"]'
        loginName = '//a[@class="btn-login"]'

        print 'Phone code is needed ...'

        # Notice
        element = findElement(driver, tipsName) 

        if element is not None:
            notice = element.text

        element = findElement(driver, retransmitButtonName) 

        if element is not None:
            element.click()
            time.sleep(1)

        element = findElement(driver, inputName)

        if element is not None:

            prompt = element.get_attribute('placeholder')

            content = inputter.getInput(notice, '', prompt, 6)

            if content is None:
                return

            element = findElement(driver, inputName)

            element.send_keys(Keys.CONTROL, 'a')
            element.send_keys(Keys.DELETE);
            element.send_keys(content);

            print 'Phone code is sent.'

            time.sleep(1)

            element = findElement(driver, loginName)
            element.click()

            time.sleep(3)

    def verify(self, driver, inputter):

        verifyBodyName = '//div[@class="verify-body"]'
        verifyMsgName = '//p[@class="verify-msg"]'
        verifyNoticeName = '//div[@class="verify-notice"]'
        verifyInputName = '//input[@class="verify-input"]'
        verifyContinueName = '//a[@class="verify-continue"]'

        time.sleep(1)

        # Verification

        element = findElement(driver, verifyBodyName)

        if element is None or not element.is_displayed() or not element.is_enabled():
            return False

        print 'Verification is needed ...'

        element = findElement(driver, verifyNoticeName)

        if element is not None:
            notice = element.text
        else:
            notice = None

        element = findElement(driver, verifyMsgName)

        if element is not None:
            msg = element.text
        else:
            msg = None

        element = findElement(driver, verifyInputName)

        if element is not None:

            prompt = element.get_attribute('placeholder')

            content = inputter.getInput(notice, msg, prompt)

            element.send_keys(content)

            print 'Verification code is sent.'

            time.sleep(2)

            element = findElement(driver, verifyContinueName)

            if element is not None:

                element.click()

                time.sleep(3) # Sleep a little longer

        return True

    def updateDb(self, driver):

        # Redirect to wqs
        time.sleep(1)

        # Save as type of cookie for requests
        cookies = dict()
        for cookie in driver.get_cookies():

            k = cookie['name']
            v = cookie['value']

            cookies[k] = v

        entryCookies = reprDict(cookies)

        sql = ''' UPDATE
                      `configs`
                  SET
                      `entryCookies`= '{}'
                  WHERE
                      `userId` = {} '''.format(entryCookies, self.userId)

        self.db.query(sql)

