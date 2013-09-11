# Embedded file name: scripts/client/CurrentVehicle.py
import BigWorld
from Event import Event
from items import vehicles
from helpers import isPlayerAccount
from adisp import async, process
from account_helpers.AccountSettings import AccountSettings, CURRENT_VEHICLE
from gui.ClientUpdateManager import g_clientUpdateManager
from gui import prb_control
from gui.shared import g_itemsCache, REQ_CRITERIA
from gui.shared.utils.HangarSpace import g_hangarSpace
from gui.shared.gui_items import GUI_ITEM_TYPE
from gui.shared.gui_items.Vehicle import Vehicle
from gui.Scaleform.locale.MENU import MENU
from gui.Scaleform.Waiting import Waiting
import io, os, json, codecs, math
from items import tankmen
from debug_utils import *

class _CurrentVehicle():
    def __init__(self):
        self.__vehInvID = 0
        self.__changeCallbackID = None
        self.onChanged = Event()
        self.onChangeStarted = Event()
        self.__crew = {}
        return

    def init(self):
        g_clientUpdateManager.addCallbacks({'inventory': self.onInventoryUpdate,
         'cache.vehsLock': self.onLocksUpdate})
        prbVehicle = self.__checkPrebattleLockedVehicle()
        storedVehInvID = AccountSettings.getFavorites(CURRENT_VEHICLE)
        self.selectVehicle(prbVehicle or storedVehInvID)

    def destroy(self):
        self.__vehInvID = 0
        self.__clearChangeCallback()
        self.onChanged.clear()
        self.onChangeStarted.clear()
        g_clientUpdateManager.removeObjectCallbacks(self)
        g_hangarSpace.removeVehicle()
        self.selectNoVehicle()

    def onInventoryUpdate(self, invDiff):
        vehsDiff = invDiff.get(GUI_ITEM_TYPE.VEHICLE, {})
        isVehicleSold = False
        isVehicleDescrChanged = False
        if 'compDescr' in vehsDiff and self.__vehInvID in vehsDiff['compDescr']:
            isVehicleSold = vehsDiff['compDescr'][self.__vehInvID] is None
            isVehicleDescrChanged = not isVehicleSold
        if isVehicleSold or self.__vehInvID == 0:
            self.selectVehicle()
        elif 'repair' in vehsDiff:
            isRepaired = self.__vehInvID in vehsDiff['repair']
            if not GUI_ITEM_TYPE.TURRET in invDiff:
                isComponentsChanged = GUI_ITEM_TYPE.GUN in invDiff
                isVehicleChanged = len(filter(lambda hive: self.__vehInvID in hive, vehsDiff.itervalues())) > 0
                (isComponentsChanged or isRepaired or isVehicleDescrChanged) and self.refreshModel()
            (isVehicleChanged or isRepaired) and self.onChanged()
        return

    def onLocksUpdate(self, locksDiff):
        if self.__vehInvID in locksDiff:
            self.refreshModel()

    def refreshModel(self):
        if self.isPresent() and self.isInHangar() and self.item.modelState:
            g_hangarSpace.updateVehicle(self.item)
        else:
            g_hangarSpace.removeVehicle()

    @property
    def invID(self):
        return self.__vehInvID

    @property
    def item(self):
        if self.__vehInvID > 0:
            return g_itemsCache.items.getVehicle(self.__vehInvID)
        else:
            return None

    def isPresent(self):
        return self.item is not None

    def isBroken(self):
        return self.isPresent() and self.item.isBroken

    def isLocked(self):
        return self.isPresent() and self.item.isLocked

    def isClanLock(self):
        return self.isPresent() and self.item.clanLock > 0

    def isCrewFull(self):
        return self.isPresent() and self.item.isCrewFull

    def isInBattle(self):
        return self.isPresent() and self.item.isInBattle

    def isInHangar(self):
        return self.isPresent() and not self.item.isInBattle

    def isAwaitingBattle(self):
        return self.isPresent() and self.item.isAwaitingBattle

    def isAlive(self):
        return self.isPresent() and self.item.isAlive

    def isReadyToPrebattle(self):
        return self.isPresent() and self.item.isReadyToPrebattle

    def isReadyToFight(self):
        return self.isPresent() and self.item.isReadyToFight

    def selectVehicle(self, vehInvID = 0):
        vehicle = g_itemsCache.items.getVehicle(vehInvID)
        if vehicle is None:
            invVehs = g_itemsCache.items.getVehicles(criteria=REQ_CRITERIA.INVENTORY)
            if len(invVehs):
                vehInvID = sorted(invVehs.itervalues())[0].invID
            else:
                vehInvID = 0
        self.__selectVehicle(vehInvID)
        return

    def selectNoVehicle(self):
        self.__selectVehicle(0)

    def getHangarMessage(self):
        if self.isPresent():
            state, stateLvl = self.item.getState()
            return ('#menu:currentVehicleStatus/' + state, stateLvl)
        return (MENU.CURRENTVEHICLESTATUS_NOTPRESENT, Vehicle.VEHICLE_STATE_LEVEL.CRITICAL)

    def __selectVehicle(self, vehInvID):
        if vehInvID != self.__vehInvID:
            Waiting.show('updateCurrentVehicle', isSingle=True)
            self.onChangeStarted()
            self.__vehInvID = vehInvID
            AccountSettings.setFavorites(CURRENT_VEHICLE, vehInvID)
            self.refreshModel()
            if not self.__changeCallbackID:
                self.__changeCallbackID = BigWorld.callback(0.1, self.__changeDone)

        if self.isPresent():
            # Set Defaults
            xvm_conf = {}

            # Load configuration
            xvm_configuration_file = os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'tankrange.xc'
            if not os.path.exists(xvm_configuration_file):
                LOG_NOTE("Configuration file missing (" + xvm_configuration_file + "). Creating.")
            else:
                data = ""
                blockComment = False

                f = codecs.open(xvm_configuration_file, 'r', '"utf-8-sig"')
                for line in f.read().split('\n'):
                    line = line.strip()
                    if line != "":
                        # Start of block comment
                        comment = line.find("/*")
                        if comment != -1 and comment == 0:
                            blockComment = True
                            continue

                        # End of block comment
                        comment = line.find("*/")
                        if comment != -1:
                            blockComment = False
                            continue

                        # Block Comment
                        if blockComment == True:
                            continue

                        # Start of line comment
                        comment = line.find("//")
                        if comment != -1 and comment == 0:
                            continue

                        # Remove end of line comments
                        position = 0
                        for i in range(0,line.count("//")):
                            comment = line.find("//", position+2)
                            if comment != -1:
                                colon = line.find(":")

                                startSpeach = line.find("\"", colon+1)
                                if startSpeach > comment:
                                    line = line[:comment].strip()

                                endSpeach = line.find("\"", startSpeach+1)
                                if comment > endSpeach:
                                    line = line[:comment].strip()

                            position += comment

                        if line != "":
                            data += line + '\n'
                f.close()

                xvm_conf = json.loads(data)

            # Make sure we have the correct defaults
            if not "tankrange" in xvm_conf:
                xvm_conf["tankrange"] = {}

            if not "logging" in xvm_conf["tankrange"]:
                xvm_conf["tankrange"]["logging"] = True

            if not "ignore_artillery" in xvm_conf["tankrange"]:
                xvm_conf["tankrange"]["ignore_artillery"] = False

            if not "circle_view" in xvm_conf["tankrange"]:
                xvm_conf["tankrange"]["circle_view"] =  {
                    "enabled": True,
                    "color": "0xFFFFFF",
                    "alpha": 50,
                    "thickness": 0.5
                }

            if not "circle_binocular" in xvm_conf["tankrange"]:
                xvm_conf["tankrange"]["circle_binocular"] =  {
                    "enabled": True,
                    "color": "0xFFFFFF",
                    "alpha": 50,
                    "thickness": 0.5
                }

            if not "circle_artillery" in xvm_conf["tankrange"]:
                xvm_conf["tankrange"]["circle_artillery"] =  {
                    "enabled": True,
                    "color": "0xFF0000",
                    "alpha": 50,
                    "thickness": 0.5
                }


            # Setup Circles Dictionary
            if not "circles" in xvm_conf:
                xvm_conf["circles"] = { "enabled": True }

            if not "major" in xvm_conf["circles"]:
                xvm_conf["circles"]["major"] = [
                    { "enabled": False, "distance": 445, "thickness": 0.75, "alpha": 45, "color": "0xFFCC66" },
                    { "enabled": False, "distance": 50, "thickness": 1.00, "alpha": 100, "color": "0xFFFFFF" }
                ]

            if not "special" in xvm_conf["circles"]:
                xvm_conf["circles"]["special"] = {}

            # Get name
            tank_name = g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.type.name.split(":")[1].lower().replace("-","_")
            if xvm_conf["tankrange"]["logging"]:
                LOG_NOTE("Tank Name: ", tank_name)

            # Remove current circles
            remaining = []
            for tank_data in xvm_conf["circles"]["special"]:
                if tank_data.keys()[0] != tank_name:
                    remaining.append(tank_data)
            xvm_conf["circles"]["special"] = remaining

            # Get type
            if xvm_conf["tankrange"]["ignore_artillery"] and "SPG" in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.type.tags:
                f = codecs.open(xvm_configuration_file, 'w', '"utf-8-sig"')
                f.write(unicode(json.dumps(xvm_conf, ensure_ascii=False, indent=2)))
                f.close()

                if xvm_conf["tankrange"]["logging"]:
                    LOG_NOTE("Ignoring " + vehicle_type + " tank.")
                return

            # Get view distance
            view_distance = g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.turret["circularVisionRadius"]
            if xvm_conf["tankrange"]["logging"]:
                LOG_NOTE("Base View Range: ", view_distance)

            # Check for Ventilation
            ventilation = self.__isOptionalEquipped("improvedVentilation")
            if xvm_conf["tankrange"]["logging"] and ventilation:
                LOG_NOTE("Ventilation Found")

            # Check for Consumable
            consumable = self.__isConsumableEquipped("ration")
            if xvm_conf["tankrange"]["logging"] and consumable:
                LOG_NOTE("Premium Consumable Found")

            # Update crew
            self.__updateCrew()

            # Check for Brothers In Arms
            brothers_in_arms = True
            for name, data in self.__crew.iteritems():
                if "brotherhood" not in data["skill"]:
                    brothers_in_arms = False

            if xvm_conf["tankrange"]["logging"] and brothers_in_arms:
                LOG_NOTE("BIA Found")

            # Calculate commander bonus
            commander_skill = 0
            if "commander" in self.__crew:
                commander_skill = self.__crew["commander"]["level"]

                if brothers_in_arms == True:
                    commander_skill += 5
                if ventilation == True:
                    commander_skill += 5
                if consumable == True:
                    commander_skill += 10

                if xvm_conf["tankrange"]["logging"]:
                    LOG_NOTE("Commander Skill: ", commander_skill)

            # Calculate other bonuses
            other_bonus = 1.0
            for name, data in self.__crew.iteritems():
                # Calculate recon skills
                if "commander_eagleEye" in data["skill"]:
                    other_bonus *= 1.0 + ( 0.0002 * data["skill"]["commander_eagleEye"] )

                    if xvm_conf["tankrange"]["logging"]:
                        LOG_NOTE("Recon Bonus: ", 1.0 + ( 0.0002 * data["skill"]["commander_eagleEye"] ))

                # Calculate Situational Awareness Skill
                if "radioman_finder" in data["skill"]:
                    other_bonus *= 1.0 + ( 0.0002 * data["skill"]["radioman_finder"] )

                    if xvm_conf["tankrange"]["logging"]:
                        LOG_NOTE("Situational Awareness Bonus: ", 1.0 + ( 0.0003 * data["skill"]["radioman_finder"] ))

            # Check for Binoculars
            binoculars = self.__isOptionalEquipped("stereoscope")
            if xvm_conf["tankrange"]["logging"] and binoculars:
                LOG_NOTE("Binoculars Found")

            # Check for Coated Optics
            coated_optics = self.__isOptionalEquipped("coatedOptics")
            if xvm_conf["tankrange"]["logging"] and coated_optics:
                LOG_NOTE("Coated Optics Found")

            # Calculate final value
            view_distance = ((view_distance / 0.875) * (0.00375* commander_skill + 0.5)) * other_bonus

            if xvm_conf["tankrange"]["logging"]:
                LOG_NOTE("Other Bonus:", other_bonus)
                LOG_NOTE("Final View Range: ", view_distance)

            # Add binocular Circles
            if xvm_conf["tankrange"]["circle_binocular"]["enabled"] and binoculars:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_binocular" }, "distance": view_distance * 1.25 } })

            # Add standard Circles
            if coated_optics == True:
                view_distance = min(view_distance * 1.1, 500)

            if xvm_conf["tankrange"]["circle_view"]["enabled"]:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_view" }, "distance": view_distance } })

            # Add Artillery Range
            if xvm_conf["tankrange"]["circle_artillery"]["enabled"] and "SPG" in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.type.tags:
                artillery_range = 0
                for shell in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.gun["shots"]:
                    artillery_range = max(artillery_range, round(math.pow(shell["speed"],2) / shell["gravity"]))

                if xvm_conf["tankrange"]["logging"]:
                    LOG_NOTE("Calculated Firing Range:", artillery_range)

                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_artillery" }, "distance": artillery_range } })

            # Write result
            f = codecs.open(xvm_configuration_file, 'w', '"utf-8-sig"')
            f.write(unicode(json.dumps(xvm_conf, ensure_ascii=False, indent=2, sort_keys=True)))
            f.close()

        return

    @process
    def __updateCrew(self):
        from gui.shared.utils.requesters import Requester
        self.__crew.clear()

        barracks = yield Requester('tankman').getFromInventory()
        for tankman in barracks:
            for crewman in self.item.crew:
                if crewman[1].invID == tankman.inventoryId:
                    crew_member = { "level": tankman.descriptor.roleLevel, "skill": {} }

                    skills = []
                    for skill_name in tankman.descriptor.skills:
                        skills.append({ "name": skill_name, "level": 100 })

                    if len(skills) != 0:
                        skills[-1]["level"] = tankman.descriptor.lastSkillLevel

                    for skill in skills:
                        crew_member["skill"][skill["name"]] = skill["level"]

                    self.__crew[tankman.descriptor.role] = crew_member

    def __isOptionalEquipped(self, optional_name):
        for item in self.item.descriptor.optionalDevices:
            if item is not None and optional_name in item.name:
                return True
        return False

    def __isConsumableEquipped(self, consumable_name):
        from gui.shared.utils.requesters import VehicleItemsRequester

        for item in self.item.eqsLayout:
            if consumable_name in item.descriptor.name:
                return True
        return False

    def __changeDone(self):
        self.__clearChangeCallback()
        if isPlayerAccount():
            self.onChanged()
        Waiting.hide('updateCurrentVehicle')

    def __clearChangeCallback(self):
        if self.__changeCallbackID is not None:
            BigWorld.cancelCallback(self.__changeCallbackID)
            self.__changeCallbackID = None
        return

    def __checkPrebattleLockedVehicle(self):
        clientPrb = prb_control.getClientPrebattle()
        if clientPrb is not None:
            rosters = prb_control.getPrebattleRosters(prebattle=clientPrb)
            for rId, roster in rosters.iteritems():
                if BigWorld.player().id in roster:
                    vehCompDescr = roster[BigWorld.player().id].get('vehCompDescr', '')
                    if len(vehCompDescr):
                        vehDescr = vehicles.VehicleDescr(vehCompDescr)
                        vehicle = g_itemsCache.items.getItemByCD(vehDescr.type.compactDescr)
                        if vehicle is not None:
                            return vehicle.invID

        return 0

    def __repr__(self):
        return 'CurrentVehicle(%s)' % str(self.item)


g_currentVehicle = _CurrentVehicle()
