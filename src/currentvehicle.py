import BigWorld
import random
from Event import Event
from items import vehicles
from helpers import isPlayerAccount
from adisp import async, process
from account_helpers.AccountSettings import AccountSettings, CURRENT_VEHICLE
from gui.ClientUpdateManager import g_clientUpdateManager
from gui import prb_control, game_control, g_tankActiveCamouflage, SystemMessages
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

    def init(self):
        g_clientUpdateManager.addCallbacks({
            'inventory': self.onInventoryUpdate,
            'cache.vehsLock': self.onLocksUpdate
        })
        game_control.g_instance.igr.onIgrTypeChanged += self.onIgrTypeChanged
        prbVehicle = self.__checkPrebattleLockedVehicle()
        storedVehInvID = AccountSettings.getFavorites(CURRENT_VEHICLE)
        self.selectVehicle(prbVehicle or storedVehInvID)

    def destroy(self):
        self.__vehInvID = 0
        self.__clearChangeCallback()
        self.onChanged.clear()
        self.onChangeStarted.clear()
        g_clientUpdateManager.removeObjectCallbacks(self)
        game_control.g_instance.igr.onIgrTypeChanged -= self.onIgrTypeChanged
        g_hangarSpace.removeVehicle()
        self.selectNoVehicle()

    def onIgrTypeChanged(self, *args):
        self.refreshModel()

    def onInventoryUpdate(self, invDiff):
        vehsDiff = invDiff.get(GUI_ITEM_TYPE.VEHICLE, {})
        isVehicleSold = False
        isVehicleDescrChanged = False
        if 'compDescr' in vehsDiff and self.__vehInvID in vehsDiff['compDescr']:
            isVehicleSold = vehsDiff['compDescr'][self.__vehInvID] is None
            isVehicleDescrChanged = not isVehicleSold
        if isVehicleSold or self.__vehInvID == 0:
            self.selectVehicle()
        else:
            isRepaired = 'repair' in vehsDiff and self.__vehInvID in vehsDiff['repair']
            isCustomizationChanged = 'igrCustomizationsLayout' in vehsDiff and self.__vehInvID in vehsDiff['igrCustomizationsLayout']
            isComponentsChanged = GUI_ITEM_TYPE.TURRET in invDiff or GUI_ITEM_TYPE.GUN in invDiff
            isVehicleChanged = len(filter(lambda hive: self.__vehInvID in hive or (self.__vehInvID, '_r') in hive, vehsDiff.itervalues())) > 0

            if isComponentsChanged or isRepaired or isVehicleDescrChanged or isCustomizationChanged:
                self.refreshModel()
            if isVehicleChanged or isRepaired:
                self.onChanged()

        if self.isPresent():
            self.__updateViewRange()

    def onLocksUpdate(self, locksDiff):
        if self.__vehInvID in locksDiff:
            self.refreshModel()

    def refreshModel(self):
        if self.isPresent() and self.isInHangar() and self.item.modelState:
            if not g_tankActiveCamouflage.has_key(self.item.intCD):
                availableKinds = []
                currKind = 0
                for id, startTime, days in self.item.descriptor.camouflages:
                    if id is not None:
                        availableKinds.append(currKind)
                    currKind += 1

                if len(availableKinds) > 0:
                    g_tankActiveCamouflage[self.item.intCD] = random.choice(availableKinds)
            g_hangarSpace.updateVehicle(self.item)
        else:
            g_hangarSpace.removeVehicle()
        return

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

    def isDisabledInRoaming(self):
        return self.isPresent() and self.item.isDisabledInRoaming

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

    def isAutoLoadFull(self):
        if self.isPresent() and self.item.isAutoLoad:
            for shell in self.item.shells:
                if shell.count != shell.defaultCount:
                    return False

        return True

    def isAutoEquipFull(self):
        if self.isPresent() and self.item.isAutoEquip:
            for i, e in enumerate(self.item.eqsLayout):
                if e != self.item.eqs[i]:
                    return False

        return True

    def selectVehicle(self, vehInvID = 0):
        vehicle = g_itemsCache.items.getVehicle(vehInvID)
        if vehicle is None:
            invVehs = g_itemsCache.items.getVehicles(criteria=REQ_CRITERIA.INVENTORY)
            if len(invVehs):
                vehInvID = sorted(invVehs.itervalues())[0].invID
            else:
                vehInvID = 0
        self.__selectVehicle(vehInvID)

    def selectNoVehicle(self):
        self.__selectVehicle(0)

    def getHangarMessage(self):
        if self.isPresent():
            state, stateLvl = self.item.getState()
            return ('#menu:currentVehicleStatus/' + state, stateLvl)
        return (MENU.CURRENTVEHICLESTATUS_NOTPRESENT, Vehicle.VEHICLE_STATE_LEVEL.CRITICAL)

    def __selectVehicle(self, vehInvID):
        if vehInvID == self.__vehInvID:
            return
        Waiting.show('updateCurrentVehicle', isSingle=True)
        self.onChangeStarted()
        self.__vehInvID = vehInvID
        AccountSettings.setFavorites(CURRENT_VEHICLE, vehInvID)
        self.refreshModel()
        if not self.__changeCallbackID:
            self.__changeCallbackID = BigWorld.callback(0.1, self.__changeDone)

        if self.isPresent():
            self.__updateViewRange()

    def __updateViewRange(self):
        # Set Defaults
        xvm_conf = {}
        saveConfig = False

        # Load configuration
        xvm_configuration_file = os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'tankrange.xc'
        if not os.path.exists(xvm_configuration_file):
            SystemMessages.pushMessage("Configuration file missing (" + xvm_configuration_file + ")", type=SystemMessages.SM_TYPE.Error)
            return
        else:
            try:
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
            except Exception as e:
                SystemMessages.pushMessage("Parsing configuration file: " + str(e), type=SystemMessages.SM_TYPE.Error)
                return

        # Code for migrating old configuration files (v1.5->v1.6)
        if not xvm_conf["tankrange"].has_key("spotting_limit"):
            xvm_conf["tankrange"]["spotting_limit"] = True
            saveConfig = True

        # Code for migrating old configuration files (v1.7->v1.8)
        if not xvm_conf["tankrange"].has_key("notify_changes"):
            xvm_conf["tankrange"]["notify_changes"] = True
            saveConfig = True

        # Get name
        tank_name = g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.type.name.replace(":","-")
        if xvm_conf["tankrange"]["logging"]:
            LOG_NOTE("Tank Name: ", tank_name)

        # Only update when we have a crew
        if not self.isCrewFull():
            if xvm_conf['tankrange']['logging']:
                LOG_NOTE('Crew is missing.')
            return

        # Remove current circles
        remaining = []
        oldCircles = {}
        for tank_data in xvm_conf["circles"]["special"]:
            if tank_data.keys()[0] != tank_name:
                remaining.append(tank_data)
            elif tank_data[tank_name].has_key('distance') and tank_data[tank_name].has_key('$ref') and tank_data[tank_name]['$ref'].has_key('path'):
                oldCircles[tank_data[tank_name]['$ref']['path']] = tank_data[tank_name]['distance']

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
        consumable = False
        if self.__isConsumableEquipped("ration"):
            consumable = True
        if self.__isConsumableEquipped("chocolate"):
            consumable = True
        if self.__isConsumableEquipped("cocacola"):
            consumable = True
        if self.__isConsumableEquipped("hotCoffee"):
            consumable = True
        if xvm_conf["tankrange"]["logging"] and consumable:
            LOG_NOTE("Premium Consumable Found")

        # Update crew
        self.__updateCrew()

        # Check for Brothers In Arms
        brothers_in_arms = True
        if len(self.__crew) == 0:
            brothers_in_arms = False
        else:
            for name, data in self.__crew.iteritems():
                if "brotherhood" not in data["skill"]:
                    brothers_in_arms = False
                elif data["skill"]["brotherhood"] != 100:
                    brothers_in_arms = False

        if xvm_conf["tankrange"]["logging"] and brothers_in_arms:
            LOG_NOTE("BIA Found")

        # Calculate commander bonus
        commander_skill = 0.0
        if "commander" in self.__crew:
            commander_skill = self.__crew["commander"]["level"]

            if brothers_in_arms == True:
                commander_skill += 5.0
            if ventilation == True:
                commander_skill += 5.0
            if consumable == True:
                commander_skill += 10.0

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
                other_bonus *= 1.0 + ( 0.0003 * data["skill"]["radioman_finder"] )

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
        view_distance = ((view_distance / 0.875) * (0.00375 * commander_skill + 0.5)) * other_bonus

        if xvm_conf["tankrange"]["logging"]:
            LOG_NOTE("Other Bonus:", other_bonus)
            LOG_NOTE("Final View Range: ", view_distance)

        # Add binocular Circles
        binocular_distance = None
        if xvm_conf["tankrange"]["circle_binocular"]["enabled"] and binoculars:
            binocular_distance = view_distance * 1.25
            if xvm_conf["tankrange"]["spotting_limit"]:
                binocular_distance = min(445, binocular_distance);

            if not xvm_conf["tankrange"]["circle_binocular"]["filled"]:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_binocular" }, "distance": binocular_distance } })
            else:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_binocular" }, "thickness": (binocular_distance*0.25)-14, "distance": binocular_distance*0.5 } })

            # store only when changes
            if not oldCircles.has_key("tankrange.circle_binocular") or float(oldCircles["tankrange.circle_binocular"]) != binocular_distance:
                saveConfig = True

        # Remove old circles
        elif oldCircles.has_key("tankrange.circle_binocular"):
            saveConfig = True

        # Add standard Circles
        if coated_optics == True:
            view_distance = min(view_distance * 1.1, 500)

        if xvm_conf["tankrange"]["circle_view"]["enabled"]:
            if xvm_conf["tankrange"]["spotting_limit"]:
                view_distance = min(445, view_distance);

            if not xvm_conf["tankrange"]["circle_view"]["filled"]:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_view" }, "distance": view_distance } })
            else:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_view" }, "thickness": (view_distance*0.25)-14, "distance": view_distance*0.5 } })

            # store only when changes
            if not oldCircles.has_key("tankrange.circle_view") or float(oldCircles["tankrange.circle_view"]) != view_distance:
                saveConfig = True

        # Remove old circles
        elif oldCircles.has_key("tankrange.circle_view"):
            saveConfig = True

        # Add Artillery Range
        artillery_range = 0
        if xvm_conf["tankrange"]["circle_artillery"]["enabled"] and "SPG" in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.type.tags:
            for shell in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.gun["shots"]:
                artillery_range = max(artillery_range, round(math.pow(shell["speed"],2) / shell["gravity"]))

            if xvm_conf["tankrange"]["logging"]:
                LOG_NOTE("Calculated Firing Range:", artillery_range)

            if not xvm_conf["tankrange"]["circle_artillery"]["filled"]:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_artillery" }, "distance": artillery_range } })
            else:
                xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_artillery" }, "thickness": (artillery_range*0.25)-14, "distance": artillery_range*0.5 } })

            # store only when changes
            if not oldCircles.has_key("tankrange.circle_artillery") or float(oldCircles["tankrange.circle_artillery"]) != artillery_range:
                saveConfig = True

        # Remove old circles
        elif oldCircles.has_key("tankrange.circle_artillery"):
            saveConfig = True

        # Add Artillery Range
        shell_range = 0
        if xvm_conf["tankrange"]["circle_shell"]["enabled"]:
            for shell in g_itemsCache.items.getVehicle(self.__vehInvID).descriptor.gun["shots"]:
                shell_range = max(shell_range, shell["maxDistance"])

            if xvm_conf["tankrange"]["logging"]:
                LOG_NOTE("Calculated Shell Range:", shell_range)

            if shell_range < 445:
                if not xvm_conf["tankrange"]["circle_shell"]["filled"]:
                    xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_shell" }, "distance": shell_range } })
                else:
                    xvm_conf["circles"]["special"].append({ tank_name: { "$ref": { "path": "tankrange.circle_shell" }, "thickness": (shell_range*0.25)-14, "distance": shell_range*0.5 } })

                # store only when changes
                if not oldCircles.has_key("tankrange.circle_shell") or float(oldCircles["tankrange.circle_shell"]) != shell_range:
                    saveConfig = True

        # Remove old circles
        elif oldCircles.has_key("tankrange.circle_shell"):
            saveConfig = True

        # Write result
        if saveConfig:
            f = codecs.open(xvm_configuration_file, 'w', '"utf-8-sig"')
            f.write(unicode(json.dumps(xvm_conf, ensure_ascii=False, indent=2, sort_keys=True)))
            f.close()

        # notify changes
        if saveConfig and xvm_conf["tankrange"]["notify_changes"]:
            msg = "{0}: View Distance: {1}m".format(g_itemsCache.items.getVehicle(self.__vehInvID).userName, round(view_distance,1) )
            if binocular_distance:
                msg += " + Binoculars: {0}m".format( round(binocular_distance,1) )
            if artillery_range:
                msg += " Artillery Range: {0}m".format( round(artillery_range,1) )
            if shell_range > 0 and shell_range < 445:
                msg += " Shell Range: {0}m".format( round(shell_range,1) )
            SystemMessages.pushMessage(msg, type=SystemMessages.SM_TYPE.Information)

    @process
    def __updateCrew(self):
        from gui.shared.utils.requesters import Requester
        self.__crew.clear()

        barracks = yield Requester('tankman').getFromInventory()
        for tankman in barracks:
            for crewman in self.item.crew:
                if crewman[1] is not None and crewman[1].invID == tankman.inventoryId:
                    factor = tankman.descriptor.efficiencyOnVehicle(g_itemsCache.items.getVehicle(self.__vehInvID).descriptor)

                    crew_member = {
                        "level": tankman.descriptor.roleLevel * factor[0], 
                        "skill": {} 
                    }

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
            if item is not None and consumable_name in item.descriptor.name:
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
