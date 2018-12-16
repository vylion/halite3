#!/usr/bin/env python3

# My first Halite bot. v.8

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import *

import random
import logging

def getHalitestNeighbor(pos, map):
    halitest = pos
    for neighbor in pos.get_surrounding_cardinals():
        if map[neighbor].halite_amount > map[halitest].halite_amount:
            halitest = neighbor
    return halitest

def processShip(ship, shipyard, map):
    if ship.halite_amount < 600:
        dest = getHalitestNeighbor(ship.position, map)
        if dest == ship.position:
            return ship.stay_still()
        else:
            order = map.naive_navigate(ship, dest)
            return ship.move(order)
    else:
        order = map.naive_navigate(ship, shipyard.position)
        return ship.move(Direction.convert(order))

ship_status = {}
game_turn = 0

# This game object contains the initial game state.
game = hlt.Game()
# Respond with your name.
game.ready("Vylbot_alpha")

while True:
    # Get the latest game state.
    game.update_frame()
    # You extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # A command queue holds all the commands you will run this turn.
    command_queue = []

    for ship in me.get_ships():
        logging.info("Ship {} has {} halite.".format(ship.id, ship.halite_amount))

        if ship.id not in ship_status:
            ship_status[ship.id] = "exploring"

        if ship_status[ship.id] == "returning":
            if ship.position == me.shipyard.position:
                ship_status[ship.id] = "exploring"
            else:
                order = game_map.naive_navigate(ship, me.shipyard.position)
                command_queue.append(ship.move(order))
                continue
        elif ship.halite_amount >= constants.MAX_HALITE / 2:
            ship_status[ship.id] = "returning"
        else:
            order = processShip(ship, me.shipyard, game_map)
            command_queue.append(order)


    # If you're on the first turn and have enough halite, spawn a ship.
    # Don't spawn a ship if you currently have a ship at port, though.
    if game.turn_number <= 1 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(game.me.shipyard.spawn())
    else:
        bestPlayer = None
        for key, player in game.players.items():
            if (bestPlayer is None or player.halite_amount > bestPlayer.halite_amount) and me.id != key:
                bestPlayer = player
        if bestPlayer is not None and random.random() > (1 - (game_turn / 500))/8 and me.halite_amount > 1000 and not game_map[me.shipyard].is_occupied:
            command_queue.append(me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)
    game_turn += 1
