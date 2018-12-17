#!/usr/bin/env python3

# Harvester Bot

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import *

import random
import logging

class Pilot(object):
    Role = "UNASSIGNED"

    def __init__(self, ai, ship):
        self.ai = ai
        self.id = ship.id
        self.role = Pilot.Role
        self.lastPos = ship.position
        self.static = 0

    def log(self, s):
        ai.log("[#{} {}] {}".format(self.id, self.role, s))

class Harvester(Pilot):
    Role = "HARVESTER"
    StatusSearch = "SEARCH"
    StatusHarvest = "HARVEST"
    StatusDeposit = "DEPOSIT"
    StatusRunback = "RUNBACK"
    StatusLeave = "LEAVING"

    def __init__(self, ai, ship):
        super(Harvester, self).__init__(ai, ship)
        self.status = "INACTIVE"
        self.log("{} Pilot assigned to ship".format(Harvester.Role))
        self.status = Harvester.StatusSearch
        self.role = Harvester.Role
        self.target = self.ai.shipyard().position

    def log(self, s):
        super(Harvester, self).log("[{}] {}".format(self.status, s))

    def getHalitestNeighbor(self, ship):
        halitest = ship.position
        map = self.ai.map()
        neighbors = ship.position.get_surrounding_cardinals()
        random.shuffle(neighbors)
        for neighbor in neighbors:
            if map[neighbor].halite_amount > map[halitest].halite_amount:
                halitest = neighbor
        return halitest

    def getClosestDropoff(self, ship):
        source = ship.position
        map = self.ai.map()
        closest = (None, 0)
        for dropoff in self.ai.dropoffs:
            dist = map.calculate_distance(source, dropoff)
            if closest[0] is None or closest[1] > dist:
                closest = (dropoff, dist)
        return closest[0]

    def shouldBuild(self, ship):
        should = (self.status == Harvester.StatusDeposit and self.static > 5)
        can = self.ai.current_halite >= constants.DROPOFF_COST

        closest = self.getClosestDropoff(ship)
        map = self.ai.map()
        dist = map.calculate_distance(ship.position, closest)
        worth = dist > self.static
        return can and should and worth and not self.ai.noMoreCosts

    def amOnTime(self, ship):
        map = self.ai.map()
        closest = self.getClosestDropoff(ship)
        distance = map.calculate_distance(ship.position, closest)
        return distance*2 <= constants.MAX_TURNS - self.ai.turn()

    def search(self, ship):
        self.log("Searching; collected halite: {}".format(ship.halite_amount))
        map = self.ai.map()
        shipyard = self.ai.shipyard()

        dest = self.getHalitestNeighbor(ship)
        if dest == ship.position:
            return ship.stay_still()
        else:
            order = map.naive_navigate(ship, dest)
            return ship.move(order)

    def step(self, ship):
        if (not self.amOnTime(ship) and self.status != Harvester.StatusRunback
            and self.status != Harvester.StatusLeave):
            self.ai.noMoreCosts = True
            self.status = Harvester.StatusRunback
            self.target = self.getClosestDropoff(ship)
            self.log("Initiating runback")

        if ship.position == self.lastPos:
            self.static += 1
        else:
            self.static = 0
            self.lastPos = ship.position

        if self.shouldBuild(ship):
            self.log("Bulding Dropoff point")
            self.ai.addDropoff(ship.position)
            self.ai.current_halite -= constants.DROPOFF_COST
            return ship.make_dropoff()

        map = self.ai.map()
        shipyard = self.ai.shipyard()
        # Status is runback, last deposit run
        if self.status == Harvester.StatusRunback:
            # Deposited successfully
            if ship.position == self.target:
                self.log("Halite has been deposited one last time")
                self.status = Harvester.StatusLeave
                self.target = random.choice(self.ai.enemyShipyards()).position
                self.target = map.normalize(self.target)
            # Still travelling to dropoff point
            else:
                if self.ai.newDropoffs:
                    self.target = self.getClosestDropoff(ship)
                order = map.naive_navigate(ship, self.target)
                return ship.move(order)
        # Make way for other Runbacks
        if self.status == self.StatusLeave:
            order = map.get_unsafe_moves(ship.position, self.target)[0]
            return ship.move(order)
        # Status is returning to deposit halite on a dropoff point
        if self.status == Harvester.StatusDeposit:
            # Deposited successfully
            if ship.position == self.target:
                self.log("Halite has been deposited")
                self.status = Harvester.StatusSearch
            # Still travelling to dropoff point
            else:
                if self.ai.newDropoffs:
                    self.target = self.getClosestDropoff(ship)
                order = map.naive_navigate(ship, self.target)
                return ship.move(order)
        # Status is searching for halite
        elif self.status == Harvester.StatusSearch:
            order = self.search(ship)
            if (order == Direction.Still or
                ship.halite_amount + map[ship.position].halite_amount > constants.MAX_HALITE * 3/4):
                self.log("Stopping to harvest halite")
                self.status = Harvester.StatusHarvest
                return ship.stay_still()
            else:
                return order
        # Status is harvesting halite in current tile
        elif self.status == Harvester.StatusHarvest:
            # Enough to go to deposit halite
            if ship.halite_amount >= constants.MAX_HALITE*2 / 3:
                self.log("Returning to deposit collected halite: {}"
                         .format(ship.halite_amount))
                self.status = Harvester.StatusDeposit
                self.target = self.getClosestDropoff(ship)
                return ship.stay_still()
            # Not enough to go deposit halite
            elif map[ship.position].halite_amount <= 0:
                self.status = Harvester.StatusSearch
                return self.setp(ship)
        return ship.stay_still()

class Brain(object):
    def __init__(self, game, logEnabled=False):
        self.logEnabled = logEnabled
        self.game = game
        self.pilotTypes = [Harvester]
        self.pilots = {}
        self.noHaliteCheck = (game.turn_number, False)
        self.noEnemiesCheck = (game.turn_number, False)
        self.dropoffs = [game.me.shipyard.position]
        self.newDropoffs = False
        self.noMoreCosts = False
        self.current_halite = game.me.halite_amount

        self.enemies = {}
        for key, player in game.players.items():
            if(key != game.me.id):
                self.enemies[key] = player

    def log(self, s):
        if self.logEnabled:
            logging.info(s)

    def me(self):
        return self.game.me

    def map(self):
        return self.game.game_map

    def turn(self):
        return self.game.turn_number

    def shipyard(self):
        return self.game.me.shipyard

    def enemyShipyards(self):
        return [self.enemies[pid].shipyard for pid in self.enemies]

    def addDropoff(self, pos):
        self.newDropoffs = True
        self.dropoffs.append(pos)

    def canSpawn(self):
        me = self.me()
        map = self.map()
        return self.current_halite >= constants.SHIP_COST and not map[me.shipyard].is_occupied

    def shouldSpawn(self):
        rate = random.expovariate(self.game.turn_number / 20)
        return not self.noMoreCosts and (self.turn() <= 1 or random.random() <= rate)

    def tailingSpawn(self):
        bestPlayer = None
        for key, player in self.enemies.items():
            if (bestPlayer is None or player.halite_amount > bestPlayer.halite_amount):
                bestPlayer = player
        if bestPlayer is not None and random.random() > (1 - (self.turn() / 500))/8 and me.halite_amount > 1000 and not game_map[me.shipyard].is_occupied:
            return True

    def step(self):
        self.newDropoffs = False
        self.game.update_frame()
        me = self.me()
        map = self.map()
        shipyard = self.shipyard()
        self.current_halite = me.halite_amount

        # A command queue holds all the commands you will run this turn.
        commands = []

        for ship in me.get_ships():
            if ship.id not in self.pilots:
                type = random.choice(self.pilotTypes)
                self.pilots[ship.id] = type(ai, ship)

            order = self.pilots[ship.id].step(ship)
            commands.append(order)

        # If you're on the first turn and have enough halite, spawn a ship.
        # Don't spawn a ship if you currently have a ship at port, though.
        if self.canSpawn() and self.shouldSpawn():
            self.current_halite -= constants.SHIP_COST
            commands.append(shipyard.spawn())

        # Send your moves back to the game environment, ending this turn.
        self.game.end_turn(commands)

# This game object contains the initial game state.
ai = Brain(hlt.Game(), True)
# Respond with your name.
ai.game.ready("Vyl_harvester")

while True:
    ai.step()
