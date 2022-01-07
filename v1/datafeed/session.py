from datetime import datetime
from fuzzywuzzy import fuzz
from pathlib import Path
from scraperski.component import Note
from scraperski.emulator import Emulator
from selenium import webdriver as Webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions

import io
import json
import logging
import uuid

logger = logging.getLogger('scraperski')

def amazonScoring(similarity) -> list:
  return list(set([item[0] for item in similarity]))

def jwScoring(similarity) -> list:
  return list(set([item[0] for item in similarity]))

def pccasegearScoring(similarity) -> list:
  return list(set([item[0] for item in similarity if item[1]["inStock"]]))

def umartScoring(similarity) -> list:
  return list(set([item[0] for item in similarity if item[1]["availability"] == "In Stock"]))

def pcbyteScoring(similarity) -> list:
  return list(set([item[0] for item in similarity if item[1]["availability"] == "IN STOCK"]))

# ---------------------------------------------------------------------------#
# Session
# ---------------------------------------------------------------------------#    
class Session(Note):
  store = None
  scoring = {
    "amazon": amazonScoring,
    "jw": jwScoring,
    "pcbyte": pcbyteScoring,
    "pccasegear": pccasegearScoring,
    "umart": umartScoring
  }

  def __init__(self, packet: dict):
    super().__init__(packet)
    if self.appDesc not in self.scoring:
      raise AttributeError(f"App descriptor {self.appDesc} does not exist in the scoring function map")
    required = ("api", "arrangement", "queryProducts")
    if not self.hasAttr(*required):
      raise AttributeError(f"One or more required session attributes are not provided. Required :\n{required}")
    if not isinstance(self.api, list):
      raise AttributeError(f"Attribute type {type(self.api)} of session attribute 'api' is invalid, list is required")
    apiKeys = [item[0] for item in self.api]
    if "evaluate/candidates" not in apiKeys:
      raise AttributeError(f"Required session.api route 'evaluate/candidates' is not provided")
    try:
      self.api = dict(self.api)
    except Exception as ex:
      raise AttributeError("Failed to convert session.api value from a list of entries to a dictionary")
    # set required properties
    filtered = []
    for item in packet["queryProducts"]:
      if item[0] == 1:
        filtered.append(item)
    self.queryProducts = filtered
    self.qindex = 0
    switchModes = {}
    for item in self.switchSource:
      stateKey, response = item
      if stateKey in self.switchModes:
        logger.debug(f"Adding stateKey to switch modes : {stateKey}")
        switchModes[stateKey] = response
    self.switchModes = switchModes
    self.pop("switchSource")
    logger.info(f"Switch modes are now setup :\n{switchModes}")
    # self.streamist = XhrStreamist(self.repoDir)
    for item in self.apiProtoData:
      self[item[0]] = Note(item[1])
      logger.debug(f"Added api config data : {item[0]}, {item[1]}")
    self.pop("apiProtoData")
  @classmethod
  def get(cls):
    return cls.store

  @classmethod
  def make(cls, extDir, ffBinaryPath : str, params: object):
    if not cls.store:
      cls.arrange(extDir, ffBinaryPath, params)
      cls.store = cls(params)
    return cls.store

  #-----------------------------------------------------------------#
  # arrange
  #-----------------------------------------------------------------#
  @classmethod
  def arrange(cls, extDir, ffBinaryPath: str, params: Note):
    # extDir = Path(sys.argv[0]).parent
    buildDir = extDir / 'build'
    with open(buildDir / 'manifest.json') as fh:
      manifest = json.load(fh)

    zipDir = extDir / 'web-ext-artifacts'
    extZipFile = f'{manifest["name"].lower()}-{manifest["version"]}.zip'
    
    extZipPath = (zipDir / extZipFile).resolve()
    # extPath = (extDir / f'referer-mod-{manifest["version"]}.zip').resolve()
    logger.info('Extension path : ' + str(extZipPath))
    extId = manifest["browser_specific_settings"]["gecko"]["id"]

    sessionId = str(uuid.uuid4())
    cls.extOrigin = f'moz-extension://{sessionId}'
    logger.info(f'Webonaut extension session id : {sessionId}')

    profile = Webdriver.FirefoxProfile()
    # profile = webdriver.FirefoxProfile(profile_directory="/home/peter/.mozilla/firefox/3yengw4u.dev-edition-default")
    # Pre-seed the dynamic addon ID so we can find the options page
    profile.set_preference('xpinstall.signatures.required', False)
    
    otherExtId = 'a26bd115-cede-46f9-bb32-ba9ae322173d'
    otherExtZipFile = 'ublock_origin-1.40.0-an+fx.xpi'
    otherExtZipPath = (zipDir / otherExtZipFile).resolve()
    otherSessId = str(uuid.uuid4())
    logger.info(f'UBlock-origin extension session id : {otherSessId}')
    profile.set_preference('extensions.webextensions.uuids',
                           json.dumps({
                             extId: sessionId,
                             otherExtId: otherSessId}))

    # Use the local test environment, see testserver/
    profile.set_preference('network.proxy.type', 1)
    profile.set_preference('network.proxy.http', 'localhost')
    profile.set_preference('network.proxy.http_port', 3128)
    profile.set_preference('browser.startup.homepage', 'about:debugging')
    profile.set_preference('browser.theme.content-theme', 1)
    profile.set_preference('browser.theme.toolbar-theme', 1)
    profile.set_preference('extensions.activeThemeID', 'firefox-compact-light@mozilla.org')

    options = FirefoxOptions()
    options.profile = profile
    options.binary = ffBinaryPath
    webdriver = Webdriver.Firefox(options=options)
    webdriver.install_addon(str(extZipPath), temporary=True)
    webdriver.install_addon(str(otherExtZipPath), temporary=True)
    config = Note({"emulatorKind":"SE_SUP01"})
    cls.emulator = Emulator(config, webdriver)
    cls.emulator.prepare(params)

  #-----------------------------------------------------------------#
  # getCandidates
  #-----------------------------------------------------------------#
  def getCandidates(self, candidates: list) -> (int, list):
    logger.debug("Found {} product candidates in search results page".format(len(candidates)))
    
    if len(candidates) == 0:
      logger.error("Zero candidates were provided for fuzzy analysis ...")
      return 400, "None"

    threshold, groupSize = self.eligibility.tell("simScoreThreshold", "topScoreGroupSize")
    similarity = []

    for candidate in candidates:
      simScore = fuzz.token_sort_ratio(self.targetProduct, candidate["title"])
      similarity.append((simScore, candidate))
      # logger.info(f"Similarity score : [{simScore}, {prodTitle}]")
      
    # remove duplicates by wrapping with set
    scores = self.scoring[self.appDesc](similarity)
    scores.sort(reverse=True)
    logger.info(f"Unique product candidate similarity scores, sorted in descending order :\n{scores}")
    topScores = [x for x in scores[:groupSize] if x >= threshold]
    
    if topScores:
      logger.info(f"Filtering eligibles by top {groupSize} unique scores >= {threshold}% similarity :\n{topScores}")
      selected = [item[1] for item in similarity if item[0] in topScores]
    
    else:
      # in this case, when even the top score is under the threshold, 
      # just select the top scored item(s)
      selected = [item[1] for item in similarity if item[0] in scores[:groupSize]]
      logger.warn(f"No candidates are eligible by cutoff margin, so taking the first {groupSize} highest rated items")

    # remove duplicates again due to potential duplicate supplier product listings

    logger.info("Selected product candidates :\n{}".format( "\n".join([str(x) for x in selected])) )

    return 200, selected[0]["title"]

  #-----------------------------------------------------------------#
  # isComplete
  #-----------------------------------------------------------------#
  def isComplete(self) -> bool:
    return len(self.queryProducts) == self.qindex

  #-----------------------------------------------------------------#
  # newStream
  #-----------------------------------------------------------------#
  def newStream(self, clientId):
    self.streamist.create(clientId)
    return None
  
  #-----------------------------------------------------------------#
  # writeToStream
  #-----------------------------------------------------------------#
  def writeToStream(self, article):
    self.streamist.write(article)
    return None

  #-----------------------------------------------------------------#
  # exportStream
  #-----------------------------------------------------------------#
  def exportStream(self, article):
    self.streamist.export(article)
    return None

  #-----------------------------------------------------------------#
  # nextQueryProduct
  #-----------------------------------------------------------------#
  def nextQueryProduct(self, stateKey: str) -> dict:
    logger.debug(f"Product set size, current index : {len(self.queryProducts)}, {self.qindex}")
    qsetSize = len(self.queryProducts)
    qindex = self.qindex
    enabled = 0
    # only return scrape enabled query products
    while not enabled:
      if qsetSize == qindex:
        logger.info("!! Notifying client that the scraping session is now complete !!")
        return {
          'status': 'complete',
          'statusCode': 200,
          'stateKey': stateKey
        }
      enabled, prodTag, category, subCategory, targetProduct, queryProduct = self.queryProducts[qindex]
      if enabled:
        break
      qindex += 1
    self.targetProduct = targetProduct
    logger.debug(f"Returning the next query product : {queryProduct}")
    packet = {
      'category': category,
      'queryProduct': queryProduct,
      'subCategory': subCategory,
      'status': 'running',
      'statusCode': 200,
      'stateKey': stateKey
    }
    self.qindex = qindex + 1
    return packet
  
  #-----------------------------------------------------------------#
  # reset
  #-----------------------------------------------------------------#
  def reset(self):
    self.qindex = 0

  #-----------------------------------------------------------------#
  # setTrackingData
  #-----------------------------------------------------------------#
  def setTrackingData(self, cid, trackRef: str):
    if trackRef in self.tracked.trackRef:
      self.tracked.cids.append(cid)
      logger.debug(f"Found {trackRef} in tracked.trackRef reference list - removing it ...")
      self.tracked.trackRef.remove(trackRef)
      logger.debug(f"Current tracked.trackRef list status : {self.tracked.trackRef}")
      self.tracked._trackRef.append(trackRef)

  #-----------------------------------------------------------------#
  # taskIsComplete - verifies task completion
  #-----------------------------------------------------------------#
  def taskIsComplete(self, cid):
    if cid in self.tracked.cids:
      if len(self.tracked.trackRef) == 0:
        self.tracked.cids = []
        self.tracked.trackRef = self.tracked._trackRef.copy()
        self.tracked._trackRef = []
        logger.debug(f"Resetting tracked.trackRef data ... {self.tracked.rawBody}")
        return True
    return False
    
class XhrStreamist:
  _instance = {}

  def __init__(self, repoDir):
    XhrStream.repoDir = repoDir
    
  def create(self, article):
    if not article.hasAttr("clientId"):
      logger.error(f"XhrStream constructing failed - required param clientId is not provided :\n{article.body}")
      return
    clientId = article.clientId
    if clientId in self._instance:
      logger.error(f"XhrStream constructing failed - XhrStream instance with clientId {clientId} already exists")
      return
    self._instance[clientId] = XhrStream(clientId)
    self._instance[clientId].start()
  
  def destroy(self, article):
    if not article.clientId in self._instance:
      logger.error(f"XhrStream with clientId {article.clientId} does not exist in the cache")
      return
    self._instance[article.clientId].close()
    self._instance.pop(article.clientId)

  def export(self, article):
    if not article.clientId in self._instance:
      logger.error(f"XhrStream with clientId {article.clientId} does not exist in the cache")
      return
    self._instance[article.clientId].export(article)
    self.destroy(article)
    
  def write(self, article):
    if not article.clientId in self._instance:
      logger.error(f"XhrStream with clientId {article.clientId} does not exist in the cache")
      return
    self._instance[article.clientId].write(article.data)

class XhrStream():
  repoDir = None
     
  def __init__(self, clientId):
    self.clientId = clientId
    self.ready = False
    self._buffer = io.BytesIO()
    self._writer = io.BufferedWriter(self._buffer)
    
  def close(self):
    if self.ready:
      self._buffer.close()
      self._buffer = None
      self._writer = None
      self.ready = False
    
  def export(self, article):
    logger.info("Writing json byte stream to a json output file ...")
    self._writer.flush()
    reader = io.BufferedReader(self._buffer)
    reader.seek(0)
    fileName = article.label + '-xhr-' + self.clientId + '.json'
    dirPath = Path(self.repoDir + f'/docs/output/{article.label}')
    if not dirPath.exists():
      dirPath.mkdir(parents=True)
    filePath = dirPath / fileName
    logger.info("Output json file path : \n" + filePath.as_posix())
    with open(filePath, "bw") as fw:
      fw.write(reader.read())
    
  def start(self):
    self.ready = True
    
  def write(self, data):
    if self.ready:
      self._writer.write(bytes(data))