# Embedded file name: scripts/client/CurrentVehicle.py
import BigWorld
from items import vehicles
from AccountCommands import LOCK_REASON
from account_helpers.AccountSettings import AccountSettings
from account_helpers.AccountPrebattle import AccountPrebattle
from adisp import process, async
from Event import Event, EventManager
from gui.Scaleform.Waiting import Waiting
from gui.Scaleform.gui_items import FittingItem
from debug_utils import *
import io, os, json, codecs

class _CurrentVehicle(object):

    def __init__(self):
        self.firstTimeInitialized = False
        self.__eventManager = EventManager()
        self.onChanged = Event(self.__eventManager)
        self.onChanging = Event(self.__eventManager)
        self.__vehicle = None
        self.__changeCallbackID = None
        self.__clanLock = None
        return

    def __reset(self):
        self.firstTimeInitialized = False
        self.__vehicle = None
        return

    def isVehicleTypeLocked(self):
        return self.__clanLock is not None

    def cleanup(self):
        self.reset(True)
        self.__eventManager.clear()

    def __setVehicleToServer(self, id):
        AccountSettings.setFavorites('current', id)

    def __repr__(self):
        return 'CurrentVehicle(%s)' % str(self.__vehicle)

    def __getVehicle(self):
        return self.__vehicle

    def __setVehicle(self, newVehicle):
        self.__request(newVehicle.inventoryId)
        g_currentVehicle.onChanging()

    def setVehicleById(self, id):
        self.__request(id)

    vehicle = property(__getVehicle, __setVehicle)

    def __getRepairCost(self):
        return self.__vehicle.repairCost

    def __setRepairCost(self, newValue):
        if self.__vehicle.repairCost != newValue:
            self.__vehicle.repairCost = newValue
            self.onChanged()

    repairCost = property(__getRepairCost, __setRepairCost)

    def isBroken(self):
        return self.__vehicle.repairCost > 0

    def setLocked(self, newValue):
        if self.__vehicle.lock != newValue:
            self.__vehicle.lock = newValue
            self.onChanged()

    def isCrewFull(self):
        return self.isPresent() and None not in self.__vehicle.crew and self.__vehicle.crew != []

    def isInBattle(self):
        return self.__vehicle.lock == LOCK_REASON.ON_ARENA

    def isInHangar(self):
        return self.isPresent() and not self.isInBattle()

    def isAwaitingBattle(self):
        return self.__vehicle.lock == LOCK_REASON.IN_QUEUE

    def isLocked(self):
        return self.__vehicle.lock != LOCK_REASON.NONE

    def isAlive(self):
        return self.isPresent() and not self.isBroken() and not self.isLocked()

    def isReadyToFight(self):
        isBS = AccountPrebattle.isBattleSession()
        if isBS:
            isBSVehicleLockMode = bool(AccountPrebattle.getSettings()['vehicleLockMode'])
            isCurrentVehicleTypeLocked = self.isVehicleTypeLocked()
            if isBSVehicleLockMode and isCurrentVehicleTypeLocked:
                return False
        return self.isAlive() and self.isCrewFull()

    def isPresent(self):
        return self.__vehicle is not None

    def getState(self):
        if not self.isInHangar():
            return None
        else:
            return self.vehicle.getState()

    def getHangarMessage(self):
        from gui.Scaleform.utils.gui_items import InventoryVehicle
        if self.vehicle is None:
            return ('#menu:currentVehicleStatus/notpresent', InventoryVehicle.STATE_LEVEL.CRITICAL)
        else:
            return ('#menu:currentVehicleStatus/' + self.__vehicle.getState(), self.__vehicle.getStateLevel())

    def getReadyMessage(self):
        return self.getHangarMessage()

    def reset(self, silent = False):
        self.__reset()
        if not silent:
            self.onChanged()

    @process
    def __request(self, inventoryId):
        Waiting.show('updateCurrentVehicle', True)
        from gui.Scaleform.utils.requesters import Requester, StatsRequester
        vehicles = yield Requester('vehicle').getFromInventory()
        vehicleTypeLocks = yield StatsRequester().getVehicleTypeLocks()
        globalVehicleLocks = yield StatsRequester().getGlobalVehicleLocks()
        old = self.__vehicle
        self.__vehicle = self.__findCurrent(inventoryId, vehicles)
        self.item = yield self.__requestVehicleItem(inventoryId)
        if self.__vehicle and self.__vehicle != old:
            self.__setVehicleToServer(self.__vehicle.inventoryId)
        self.__clanLock = None
        if g_currentVehicle.isPresent():
            clanDamageLock = vehicleTypeLocks.get(self.__vehicle.descriptor.type.compactDescr, {}).get(1, None)
            clanNewbeLock = globalVehicleLocks.get(1, None)
            if not clanDamageLock:
                self.__clanLock = clanNewbeLock
            self.__changeCallbackID = self.__changeCallbackID or BigWorld.callback(0.1, self.__changeDone)

        # Get name
        tank_name = self.__vehicle.descriptor.type.name.split(":")[1].lower().replace("-","_")
        LOG_NOTE("Tank Name: ", tank_name)

        # Get view distance
        view_distance = self.__vehicle.descriptor.turret["circularVisionRadius"]
        LOG_NOTE("Base View Range: ", view_distance)

        # Get crew
        tankmen = yield Requester('tankman').getFromInventory()
        for tankman in tankmen:
            for i in range(len(self.__vehicle.crew)):
                if self.__vehicle.crew[i] == tankman.inventoryId:
                    if tankman.role == "Commander":
                        view_distance *= (tankman.roleLevel / 100.0)

        LOG_NOTE("Scaled View Range: ", view_distance)

        # Load Configuration
        data = ""
        f = codecs.open(os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'xvm.xc', 'r', '"utf-8-sig"')
        for line in f.read().split('\n'):
            if line.find("//") == -1 or line.find("http") != -1:
                data += line + '\n'
        f.close()

        start = data.find("/*")
        if start != -1:
            end = data.find("*/")
            data = data[0:start] + data[end+3:]

        xvm_conf = json.loads(data)

        # Update Configuration
        tank_found = False
        for tank_data in xvm_conf["minimap"]["circles"]["special"]:
            if tank_name in tank_data:
                tank_found = True
                tank_data[tank_name]["distance"] = view_distance

        if tank_found == False:
            tank_data = { "color": "0xFFFFFF", "distance": view_distance, "alpha": 50, "enabled": True, "thickness": 0.5}
            tank = { tank_name: tank_data }
            xvm_conf["minimap"]["circles"]["special"].append(tank)

        # Write result
        f = codecs.open(os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'xvm.xc', 'w', '"utf-8-sig"')
        f.write(unicode(json.dumps(xvm_conf, ensure_ascii=False, indent=2)))
        f.close()

        return

    def __changeDone(self):
        self.__changeCallbackID = None
        player = BigWorld.player()
        if player and hasattr(player, 'isPlayer') and player.isPlayer:
            self.onChanged()
        Waiting.hide('updateCurrentVehicle')
        return

    def __findCurrent(self, inventoryId, vehicles):
        for vehicle in vehicles:
            if vehicle.inventoryId == inventoryId:
                return vehicle

        vehicles.sort()
        if len(vehicles):
            return vehicles[0]
        else:
            return None

    def update(self):
        if self.firstTimeInitialized:
            self.__request(self.__vehicle.inventoryId if self.__vehicle else None)
        return

    @async
    @process
    def getFromServer(self, callback):
        currentId = AccountSettings.getFavorites('current')
        from gui.Scaleform.utils.requesters import Requester
        vehiclesList = yield Requester('vehicle').getFromInventory()
        prebattle = AccountPrebattle.get()
        if prebattle is not None:
            for rId, roster in prebattle.rosters.iteritems():
                if BigWorld.player().id in roster:
                    vehCompDescr = roster[BigWorld.player().id].get('vehCompDescr')
                    if len(vehCompDescr):
                        vehDescr = vehicles.VehicleDescr(compactDescr=vehCompDescr)
                        for v in vehiclesList:
                            if v.descriptor.type.id == vehDescr.type.id:
                                currentId = v.inventoryId
                                break

        self.__vehicle = self.__findCurrent(currentId, vehiclesList)
        self.item = yield self.__requestVehicleItem(currentId)
        self.onChanged()
        self.firstTimeInitialized = True
        LOG_NOTE('Vehicle Get From Server. %s', self.__vehicle)
        callback(True)
        return

    @async
    @process
    def __requestVehicleItem(self, invID, callback):
        from gui.Scaleform.utils.requesters import ItemsRequester
        ir = yield ItemsRequester().request()
        callback(ir.getFromInventory(vehicles._VEHICLE).inventoryMap().get(invID, None))
        return

    def getParams(self):
        from gui.Scaleform.utils import ItemsParameters
        data = list()
        if self.isPresent():
            params = ItemsParameters.g_instance.getParameters(g_currentVehicle.vehicle)
            if params is not None:
                for p in params:
                    data.append(p[0])
                    data.append(p[1])

        return data


g_currentVehicle = _CurrentVehicle()
