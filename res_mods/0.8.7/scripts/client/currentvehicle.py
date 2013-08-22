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
from items import tankmen

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

		# Default values
		logging = True

		spg_test = False
		binocular_test = True

		view_circle_color = "0xFFFFFF"
		view_circle_alpha = 50
		view_circle_thickness = 0.5

		binocular_circle_color = "0xFFFFFF"
		binocular_circle_alpha = 25
		binocular_circle_thickness = 0.5

		# Check if mod configuration file exists
		configuration_file = os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'tankrange.conf'
		if not os.path.exists(configuration_file):
			LOG_NOTE("Tank Range Configuration file missing (" + configuration_file + "). Using default values.")

		# Check xvm configuration file exists
		xvm_configuration_file = os.getcwd() + os.sep + 'res_mods' + os.sep + 'xvm' + os.sep + 'xvm.xc'
		if not os.path.exists(xvm_configuration_file):
			if logging:
				LOG_NOTE("XVM Configuration file missing (" + xvm_configuration_file + ")")
			return

		# Get name
		tank_name = self.__vehicle.descriptor.type.name.split(":")[1].lower().replace("-","_")
		if logging:
			LOG_NOTE("Tank Name: ", tank_name)

		# Get type
		if spg_test and 'SPG' in self.__vehicle.descriptor.type.tags:
			if logging:
				LOG_NOTE("Ignoring SPG Tank")
			return

		# Get view distance
		view_distance = self.__vehicle.descriptor.turret["circularVisionRadius"]
		if logging:
			LOG_NOTE("Base View Range: ", view_distance)

		# Check for Ventilation
		ventilation = False

		# Check for Consumable
		consumable = False

		# Get crew
		barracks_crew = yield Requester('tankman').getFromInventory()

		# Check for Brothers In Arms
		brothers_in_arms = True
		for tankman in barracks_crew:
			for i in range(len(self.__vehicle.crew)):
				if self.__vehicle.crew[i] == tankman.inventoryId:
					if not "brotherhood" in tankman.descriptor.skills:
						brothers_in_arms = False
						break
					else:
						bia_skill = 0

						training_skill = tankman.descriptor.skills.pop()
						if training_skill == "brotherhood":
							if tankman.descriptor.lastSkillLevel != 100:
								brothers_in_arms = False
								break

		# Calculate commander bonus
		commander_skill = 0
		for tankman in barracks_crew:
			for i in range(len(self.__vehicle.crew)):
				if self.__vehicle.crew[i] == tankman.inventoryId:
					if tankman.role == "Commander":
						# Major Role Skill
						commander_skill = tankman.roleLevel
						if brothers_in_arms == True:
							commander_skill += 5
						if ventilation == True:
							commander_skill += 5
						if consumable == True:
							commander_skill += 10

						if logging:
							LOG_NOTE("Commander Skill: ", commander_skill)

		# Calculate role and class skills
		other_bonus = 1.0
		for tankman in barracks_crew:
			for i in range(len(self.__vehicle.crew)):
				if self.__vehicle.crew[i] == tankman.inventoryId:
					if tankman.role == "Commander":
						# Recon Skill
						recon_skill = 0
						if len(tankman.descriptor.skills) > 0:
							training_skill = tankman.descriptor.skills.pop()
							if training_skill == "commander_eagleEye":
								recon_skill = tankman.descriptor.lastSkillLevel
							else:
								if "commander_eagleEye" in tankman.descriptor.skills:
									recon_skill = 100

						# Append skill
						other_bonus *= 1.0 + (( 0.02 * recon_skill ) / 100.0)

						if logging:
							LOG_NOTE("Recon Bonus: ", 1.0 + (( 0.02 * recon_skill ) / 100.0))
					if tankman.role == "Radio Operator":
						# Situational Awareness Skill
						situational_skill = 0
						if len(tankman.descriptor.skills) > 0:
							training_skill = tankman.descriptor.skills.pop()
							if training_skill == "radioman_finder":
								situational_skill = tankman.descriptor.lastSkillLevel
							else:
								if "radioman_finder" in tankman.descriptor.skills:
									situational_skill = 100

						# Append Skill
						other_bonus *= 1.0 + (( 0.03 * situational_skill ) / 100.0)

						if logging:
							LOG_NOTE("Situational Awareness Bonus: ", 1.0 + (( 0.03 * situational_skill ) / 100.0))

		# Check for Binoculars
		binoculars = False

		# Check for Coated Optics
		coated_optics = False

		# Calculate final value
		view_distance = ((view_distance / 0.875) * (0.00375* commander_skill + 0.5)) * other_bonus

		if logging:
			LOG_NOTE("Other Bonus:", other_bonus)
			LOG_NOTE("Final View Range: ", view_distance)

		# Load Configuration
		data = ""
		f = codecs.open(xvm_configuration_file, 'r', '"utf-8-sig"')
		for line in f.read().split('\n'):
			if line.find("//") == -1 or line.find("http") != -1:
				data += line + '\n'
		f.close()

		# Remove comments
		start = data.find("/*")
		if start != -1:
			end = data.find("*/")
			data = data[0:start] + data[end+3:]

		# Parse configuration
		xvm_conf = json.loads(data)

		# Make sure we have the correct minimap entries
		if not "minimap" in xvm_conf:
			xvm_conf["minimap"] = { "enabled": True }

		if not "circles" in xvm_conf["minimap"]:
			xvm_conf["minimap"]["circles"] = {}

		if not "special" in xvm_conf["minimap"]["circles"]:
			xvm_conf["minimap"]["circles"]["special"] = {}

		# Remove current circles
		remaining = []
		for tank_data in xvm_conf["minimap"]["circles"]["special"]:
			if tank_data.keys()[0] != tank_name:
				remaining.append(tank_data)
		xvm_conf["minimap"]["circles"]["special"] = remaining

		if binoculars == True:
			tank_data = { "enabled": True, "distance": view_distance * 1.25, "color": binocular_circle_color, "alpha": binocular_circle_alpha, "thickness": binocular_circle_thickness}
			tank = { tank_name: tank_data }
			xvm_conf["minimap"]["circles"]["special"].append(tank)

		if coated_optics == True:
			view_distance *= 1.1

		tank_data = { "enabled": True, "distance": view_distance, "color": view_circle_color, "alpha": view_circle_alpha, "thickness": view_circle_thickness}
		tank = { tank_name: tank_data }
		xvm_conf["minimap"]["circles"]["special"].append(tank)

		# Write result
		f = codecs.open(xvm_configuration_file, 'w', '"utf-8-sig"')
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
