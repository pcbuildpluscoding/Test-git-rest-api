from ..emulator import Emulator
from scraperski.component import Note
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

import logging
import time

logger = logging.getLogger('scraperski')

#=================================================================#
# EmulatorSUP01
#=================================================================#
class EmulatorSUP01(Emulator):

  #-----------------------------------------------------------------#
  # STEP03C
  #-----------------------------------------------------------------#
  def STEP03C(self, params: Note) -> int:
    logger.debug("about to run emulator STEP03C ...")
    params.timeout = 10

    windows = self.browser.window_handles.copy()
    windows.reverse()
    for windowId in windows:
      logger.debug(f"Next window : {windowId}")
      if windowId != self.browser.current_window_handle:
        self.browser.switch_to_window(windowId)
        self.currTab = windowId
        time.sleep(2)
      try:
        return self.evalStep03C(params)
      except NoSuchElementException:
        logger.debug("Current window is not the target window ...")
        continue

  #-----------------------------------------------------------------#
  # evalStep03C
  #-----------------------------------------------------------------#
  def evalStep03C(self, params):
    eid = "GLUXPostalCodeWithCityInputSection"
    logger.info(f"Finding the delivery suburb input container by id ... : {eid}")
    params.findArgs = (By.ID, eid)
    container = self.browser.find_element_by_id(eid)
    if not container:
      # self.addSnapshot("After clicking postcode suburb modal opener, then not finding the input container")
      logger.error(f"Browser failed to discover the delivery suburb input container by id ... : {eid}")
      return 500
    
    logger.info("Making the delivery suburb input container actionable ...")
    # self.scrollIntoView(container)
    
    # self.addSnapshot(f"Before delivery postcode input element discovery")
    
    eid = "GLUXPostalCodeWithCity_PostalCodeInput"
    logger.info(f"Finding the delivery postcode input element by id ... : {eid}")
    element = container.find_element(By.ID, eid)
    if not element:
      logger.error(f"Browser failed to discover the delivery postcode input element by id ... : {eid}")
      return 500
    
    # slow down randomly to emulate human-like decision and action speed
    logger.info(f"About to enter the target postcode {params.postcode} in the input element")
    # self.dataEntry(element, params.postcode, delaySubmit=2, waitAfter=3)
    self.dataEntry(element, params.postcode, delaySubmit=2)
    return 200
