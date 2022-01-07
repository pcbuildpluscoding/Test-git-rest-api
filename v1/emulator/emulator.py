from scraperski.component import Note
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.wait import WebDriverWait
from typing import Any

import logging
import random
import time

logger = logging.getLogger('scraperski')

#=================================================================#
# Emulator
#=================================================================#
class Emulator(Note):

  def __init__(self, browser: object):
    self.browser = browser
    self.currTab = None
    self._ready = False

  @property
  def name(self):
    return self.__class__.__name__

  #-----------------------------------------------------------------#
  # prepare
  #-----------------------------------------------------------------#
  def prepare(self, params: Note):
    logger.info(f"{self.name} is preparing this session ...")
    # self.addSnapshot("First scraping task - main search page")
    self.browser.maximize_window()
    self.currTab = None
    self.result = Note({
      "dataset": {},
      "html": [],
      "screenshot": [],
      }, False)

  #-----------------------------------------------------------------#
  # run -- resolve the next state
  #-----------------------------------------------------------------#
  def run(self, params) -> int:
    try:
      if not self._ready:
        self._ready = True
        self.prepare(params)
        
      if not self.hasAttr(params.state):
        raise AttributeError(f"{self.name} - emulator method {params.state} does not exist")
      return self[params.state](params)
    except TimeoutException:
      return params.pageLoadErrCode
    except Exception as ex:
      logger.error(f"{self.name} caught emulator task error :\n{ex}", exc_info=True)
      # self.browser.quit()
    return 555

  #-----------------------------------------------------------------#
  # click
  #-----------------------------------------------------------------#
  def click(self, element: object, waitAfter: int=0):
    if element:
      element.click()
      if waitAfter:
        time.sleep(waitAfter)
  
  #-----------------------------------------------------------------#
  # dataEntry
  #-----------------------------------------------------------------#
  def dataEntry(self, inputElem: object, value: str, submit=True, delaySubmit: int=1, waitAfter: int=0):
    # keyChain = self.browser.actions.sequence("key", "keyboard_id")
    inputElem.clear()
    logger.debug(f"About to submit the next search query for : {value}")
    inputElem.send_keys(value)
    if submit:
      if not delaySubmit:
        delaySubmit = 1
      time.sleep(delaySubmit)
      inputElem.send_keys(Keys.ENTER)
    if waitAfter:
      time.sleep(waitAfter)

  #-----------------------------------------------------------------#
  # element_displayed
  #-----------------------------------------------------------------#
  def element_displayed(self, isRequired: bool, params: Note, timeout=0) -> bool:
    return self.findExpectedCondition(expected.visibility_of_element_located, 
                                        isRequired, params, timeout)

  #-----------------------------------------------------------------#
  # element_enabled
  #-----------------------------------------------------------------#
  def element_enabled(self, isRequired: bool, params: Note, timeout=0) -> bool:
    return self.findExpectedCondition(expected.element_to_be_clickable, 
                                        isRequired, params, timeout)


  #-----------------------------------------------------------------#
  # element_present
  #-----------------------------------------------------------------#
  def element_present(self, isRequired: bool, params: Note, timeout=0) -> Any:
    return self.findExpectedCondition(expected.presence_of_element_located, 
                                        isRequired, params, timeout)

  #-----------------------------------------------------------------#
  # elements_present
  #-----------------------------------------------------------------#
  def elements_present(self, isRequired: bool, params: Note, timeout=0) -> Any:
    return self.findExpectedCondition(expected.presence_of_all_element_located, 
                                      isRequired, params, timeout, findFirst=False)

  #-----------------------------------------------------------------#
  # findExpectedCondition
  #-----------------------------------------------------------------#
  def findExpectedCondition(self, conditioner: object, isRequired: bool,
                              params: Note, timeout: int, findFirst=True) -> Any:
    try:
      findArgs = params.findArgs
      if not timeout:
        timeout = params.timeout
      if isRequired:
        if findFirst:
          finder = lambda b: b.find_element(*findArgs)
        else:
          finder = lambda b: b.find_elements(*findArgs)
        return WebDriverWait(self.browser, timeout).until(conditioner(finder))
      return WebDriverWait(self.browser, timeout).until(conditioner(*findArgs))
    except (NoSuchElementException, TimeoutException):
      return None

