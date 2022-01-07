__all__ = ["Emulator"]
from .emulatorSE import SE_SUP01

from scraperski.component import Note

#=================================================================#
# Emulators
#=================================================================#
Emulators = {
  "SE_SUP01": SE_SUP01,
}

#-----------------------------------------------------------------#
# Constructor
#-----------------------------------------------------------------#
def Emulator(config: Note, browser: object) -> object:
  if not config.hasAttr("emulatorKind"):
    raise Exception("Required DataMining config emulatorKind is missing")
  if config.emulatorKind not in Emulators:
    raise Exception(f"EmulatorMAA kind {config.emulatorKind} does not exist")
  return Emulators[config.emulatorKind](browser)