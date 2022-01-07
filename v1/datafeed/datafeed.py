
from scraperski.component import Note

import logging
import socketio

logger = logging.getLogger("scraperski")

#=================================================================#
# Datafeed
#=================================================================#
class Datafeed:

  @staticmethod
  # def make(extOrigin: str, session: object) -> object:
  def make(session: object) -> object:
    logger.info("Datafeed is constructing a socketio.ASGIApp ...")
    websock = socketio.AsyncServer(
      async_mode='asgi',
      logger=logger,
      cors_allowed_origins=[session.extOrigin, session.remoteUrl])

    async def onArrange(cid, packet):
      packet = session.arrangement.rawBody
      packet["extOrigin"] = session.extOrigin
      logger.info(f"Returning webonaut director arrangement params ...\n{packet}")
      return packet
    websock.on("arrange", handler=onArrange)

    async def onAsyncPacket(cid, packet):
      try:
        article = Note(packet)
        if not article.hasAttr('action'):
          raise ValueError(f"Invalid request, required param action not provided. Got : {packet}")
        if article.action == "emulator/run/task":
          logger.debug(f"Running emulator task with article :\n{article.body}")
          statusCode = session.emulator.run(article.payload)
          if statusCode != 200:
            logger.error("Browser task emulator errored", exc_info=True)
        elif article.action == "xhr/stream/prepare":
          logger.debug(f"Preparing for XHR intercept streaming : {cid}")
          return session.newStream(article)
        elif article.action == "xhr/stream/data":
          logger.debug(f"Adding XHR intercept data : {cid}")
          return session.streamist.write(article)
        elif article.action == "xhr/stream/eof":
          logger.debug(f"Got XHR intercept stream OEF. Dumping xhr json stream to json file : {cid}")
          return session.streamist.export(article)
        elif article.action == "xhr/stream/error":
          logger.debug(f"Got XHR intercept stream error notice :\n{article.errmsg}")
          return session.streamist.destroy(article)

      except Exception as ex:
        logger.error("OnAsyncPacket handler errored", exc_info=True)
    websock.on("asyncPacket", handler=onAsyncPacket)

    async def onConnect(cid, environ):
      logger.info(f"Websocket client[{cid}] has connected ...")
    websock.on("connect", handler=onConnect)

    async def onDisconnect(cid):
      logger.info(f"Websocket client {cid} has disconnected ...")
      if session.taskIsComplete(cid):
        packet = {
          "status": "repeating",
          "statusCode": 200
        }
        if session.isComplete():
          logger.info("!! Notifying client that the scraping session is now complete !!")
          packet["status"] = "complete"
        logger.info("Dispatching a ScrapingComplete event for director handling ...")
        await websock.emit("scrapingComplete", packet, to="session")
    websock.on("disconnect", handler=onDisconnect)

    async def onDebugLog(cid, packet):
      logger.debug(f"Got debug packet from webonaut director : \n{packet}")
    websock.on("debugLog", handler=onDebugLog)

    async def onMessage(cid, *args):
      logger.debug(f"Remote log message : \n{args}")
    websock.on("message", handler=onMessage)

    async def onPacket(cid, packet):
      try:
        defResponse = {
          "status": "running",
          "statusCode": 200,
          "stateKey": packet.get("stateKey","0"),
          "type": "output"
        }
        article = Note(packet)
        required = ("action", "stateKey")
        if not article.hasAttr(*required):
          errmsg = "Invalid request, one or more required params are not provided :"
          errmsg = f"{errmsg}\nRequired : {required}\nPacket : {packet}"
          logger.error(errmsg)
          defResponse.update({
            "errmsg": errmsg,
            "status": "failed",
            "statusCode": 400,
          })
        if article.action == "candidate/estimate/data":
          logger.debug(f"Got candidate estimate data:\n{article.rawBody}")
        elif article.action == "emulator/run/task":
          logger.debug(f"Running emulator task with article :\n{article.body}")
          defResponse["statusCode"] = session.emulator.run(article)
        elif article.action == "evaluate/candidates":
          statusCode, selected = session.getCandidates(article.candidates)
          packet = session.api["evaluate/candidates"].copy()
          defResponse["payload"] = session.api["evaluate/candidates"].copy()
          defResponse["payload"]["selected"] = selected
        elif article.action == "get/query/product/next":
          return session.nextQueryProduct(article.stateKey)
        elif article.action == "poll/load/status":
          logger.debug(f"Calculating load check backoff delay :\n{article.rawBody}")
          if article.payload.turn >= session.finderConfig.maxTurns:
            defResponse.update({
              "status": "failed",
              "statusCode": 500
            })
          else:
            if article.payload.turn == 0:
              article.payload.pollDelay = session.finderConfig.pollDelay
            article.payload.turn += 1
            defResponse.update({
              "payload": article.payload.body,
              "status": "polling"
            })
        elif article.action == "scraping/debug":
          logger.info(f"Got webonaut debug message\n{article.body}")
        elif article.action == "scraping/pricing":
          logger.info(f"Got webonaut product pricing scrape result\n{article.dataset}")
        elif article.action == "scraping/shipping":
          logger.info(f"Got webonaut shipping cost scrape result\n{article.dataset.body}")
        elif article.action == "session/tracking":
          logger.info(f"Got session tracking request with params :\n{article.body}")
          session.setTrackingData(cid, article.trackRef)
        elif article.action == "set/client/controler":
          logger.debug(f"Initializing session room with client controler id : {cid}")
          websock.enter_room(cid, "session")
          return {
            "status": "running",
            "statusCode": 200
          }
        else:
          logger.warn(f"Unknown service action : {article.action}. article :\n{packet}")
          defResponse.update({
            "errmsg": f"Unknown service action : {article.action}",
            "statusCode": 400,
          })
        logger.info("Returning successful packet response ...")
        if article.stateKey in session.switchModes:
          return session.switchModes[article.stateKey].copy()
        return defResponse
      except Exception as ex:
        logger.error("OnPacket handler errored", exc_info=True)
        return {
          "errmsg": str(ex),
          "statusCode": 500,
          "stateKey": packet.get("stateKey","0"),
          "type": "output"
        }
    websock.on("packet", handler=onPacket)
    
    async def onStarting(cid, packet):
      session.reset()
      packet = {
        "appKey": session.appKey,
        "contentScripts": session.contentScripts.rawBody,
        "extOrigin": session.extOrigin,
        "finderConfig": session.finderConfig.rawBody,
        "remoteHost": session.remoteHost,
        "remoteUrl": session.remoteUrl,
        "runMode": session.runMode
        }
      logger.info(f"Returning webonaut director starting params ...\n{packet}")
      return packet

    websock.on("starting", handler=onStarting)
    return socketio.ASGIApp(websock, static_files={'/': './public/'})
