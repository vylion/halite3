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
    StateHarvest = "HARVEST"
    StateDeposit = "DEPOSIT"

    def __init__(self, ai, ship):
        super(Harvester, self).__init__(ai, ship)
        self.status = "INACTIVE"
        self.log("{} Pilot assigned to ship".format(Harvester.Role))
        self.status = Harvester.StateHarvest
        self.role = Harvester.Role

    def log(self, s):
        super(Harvester, self).log("[{}] {}".format(self.status, s))

    def getHalitestNeighbor(self, ship):
        halitest = ship.position
        map = self.ai.map()
        for neighbor in ship.position.get_surrounding_cardinals():
            if map[neighbor].halite_amount > map[halitest].halite_amount:
                halitest = neighbor
        return halitest

    def getClosestDropoff(self, ship):
        source = ship.position
        map = self.ai.map()
        closest = (None, 0)
        for dropoff in self.ai.dropoffs:
            dist = map.calculate_distance(source, dropoff)
            if closest[0] == None or closest[1] > dist:
                closest = (dropoff, dist)
        return closest[0]

    def shouldBuild(self, ship):
        return (self.status == Harvester.StateDeposit and self.static > 5 and
                self.ai.me().halite_amount >= constants.DROPOFF_COST)

    def harvest(self, ship):
        self.log("Harvesting; collected halite: {}".format(ship.halite_amount))
        map = self.ai.map()
        shipyard = self.ai.shipyard()

        dest = self.getHalitestNeighbor(ship)
        if dest == ship.position:
            return ship.stay_still()
        else:
            order = map.naive_navigate(ship, dest)
            return ship.move(order)

    def step(self, ship):
        if ship.position == self.lastPos:
            self.static += 1
        else:
            self.static = 0
            self.lastPos = ship.position

        if self.shouldBuild(ship):
            self.ai.addDropoff(ship.position)
            return ship.make_dropoff()

        map = self.ai.map()
        shipyard = self.ai.shipyard()
        # Status is returning to deposit halite on a dropoff point
        if self.status == Harvester.StateDeposit:
            # Deposited successfully
            if ship.position == self.ai.shipyard().position:
                self.log("Halite has been deposited")
                self.status = Harvester.StateHarvest
            # Still travelling to dropoff point
            else:
                if self.ai.newDropoffs:
                    self.dropoff = self.getClosestDropoff(ship)
                order = map.naive_navigate(ship, self.dropoff)
                return ship.move(order)
        # Status is harvesting halite; halite exceeds criteria for dropoff
        elif ship.halite_amount >= constants.MAX_HALITE / 2:
            if map[ship.position].halite_amount > 0 and ship.halite_amount < constants.MAX_HALITE:
                self.log("Finishing halite harvest")
                return ship.stay_still()
            self.log("Returning to deposit collected halite: {}"
                     .format(ship.halite_amount))
            self.status = Harvester.StateDeposit
            self.dropoff = self.getClosestDropoff(ship)
        # Status is harvesting halite
        else:
            return self.harvest(ship)
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

    def addDropoff(self, pos):
        self.newDropoffs = True
        self.dropoffs.append(pos)

    def canSpawn(self):
        me = self.me()
        map = self.map()
        return me.halite_amount >= constants.SHIP_COST and not map[me.shipyard].is_occupied

    def shouldSpawn(self):
        rate = random.expovariate(self.game.turn_number / 15)
        return self.turn() <= 1 or random.random() <= rate

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
            commands.append(shipyard.spawn())

        # Send your moves back to the game environment, ending this turn.
        self.game.end_turn(commands)

# This game object contains the initial game state.
ai = Brain(hlt.Game(), True)
# Respond with your name.
ai.game.ready("Vyl_harvester")

while True:
    ai.step()
