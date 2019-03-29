#!/usr/bin/env python3

import random

class Box:
    def __init__(self, numbers=None):
        self.numbers = [numbers is None or (i + 1) in numbers for i in range(9)]

    def clap(self, numbers):
        for number in numbers:
            if self.numbers[number - 1] is not True:
                raise Exception("{} is already closed".format(number))

        for number in numbers:
            self.numbers[number - 1] = False

    def getPossibleNumbers(self):
        return {i for i in range(1, 10) if self.numbers[i - 1] is True}

    def getPenalty(self):
        return sum(self.getPossibleNumbers())

    def __repr__(self):
        return "".join([str(i) for i in self.getPossibleNumbers()])

class Game:
    def __init__(self, box=None):
        self.box = Box() if box is None else box

    def getPossibleMoves(self, dices):
        def _getMoves(count, numbers):
            if count == 0:
                # Yes, this is a possible solution
                return [frozenset()]
            if count < 0:
                # No solution available
                return list()

            moves = list()
            for number in numbers:
                for move in _getMoves(count - number, numbers - {number}):
                    moves.append({number,} | move)
            return moves

        moves = _getMoves(dices[0] + dices[1], self.box.getPossibleNumbers())
        new_moves = []
        for move in moves:
            if move not in new_moves:
                new_moves.append(move)

        return new_moves

    def isDone(self, dices):
        return len(self.getPossibleMoves(dices)) == 0

class GameRunner:
    def __init__(self, game, decider, diceRoller):
        self.game = game
        self.decider = decider
        self.diceRoller = diceRoller

    def rollDices(self):
        dices = self.diceRoller()
        if self.game.box.getPenalty() <= 6:
            return (dices[0], 0)
        return dices

    def run(self, debug=False):
        while True:
            dices = self.rollDices()
            if self.game.isDone(dices):
                if debug:
                    print("Rolled {} + {} = {}. Game Over. Penalty: {}".format(dices[0], dices[1], dices[0] + dices[1], self.game.box.getPenalty()))
                break
            moves = self.game.getPossibleMoves(dices)
            decision = self.decider(self.game.box.getPossibleNumbers(), dices, moves)
            assert(decision in moves)

            self.game.box.clap(decision)
            if debug:
                if len(moves) < 7:
                    print("Rolled {} + {} = {}. Possible: {}. Took {}. New Field: {}".format(dices[0], dices[1], dices[0] + dices[1], moves, decision, self.game.box.getPossibleNumbers()))
                else:
                    print("Rolled {} + {} = {}. Took {}. New Field: {}".format(dices[0], dices[1], dices[0] + dices[1], decision, self.game.box.getPossibleNumbers()))

        return self.game.box.getPenalty()

def rollRandomDices():
    return (random.randint(1,6), random.randint(1,6))

class PreparedDices:
    def __init__(self, rolls):
        self.rolls = rolls
        self.i = 0

    def peek(self, i):
        return self.rolls[(self.i + i) % len(self.rolls)]

    def roll(self):
        dices = self.rolls[self.i % len(self.rolls)]
        self.i += 1
        return dices

def shittyDecider(numbers, dices, moves):
    return random.choice(moves)

def highestFirst(numbers, dices, moves):
    moves.sort(key=lambda move: -1 * max(move))
    return moves[0]

# boxes: use 9 bit integer as key, each bit representing one number, highest bit is 1, lowest 9
# each entry is a quintuple:
# 1. set containing the available numbers
# 2. penalty sum if the game would be over right now
# 3. expected penalty sum when choosing the best successor
# 4. list of all successors available (each listentry containing the needed diceroll and a list of possible successor-ids)
# 5. list of optimal successors (each listentry being a triple with the needed diceroll, id, expected penalty)
# 3 and 5 are filled in _fill only
boxes = [None for i in range(512)]

def _numbers2id(numbers):
    return sum([pow(2,9-n) for n in numbers])

def _id2numbers(id):
    return boxes[id][0]

for n in range(512):
    # always get 9 digits
    field = bin(512 + n)[3:]
    numbers = {i + 1 for i in range(9) if field[i] == '1'}

    successors = []
    for a in range(1,7):
        for b in range(0,7):
            dices = (a, b)
            game = Game(Box(numbers))
            moves = game.getPossibleMoves(dices)
            ids = []
            for move in moves:
                nextNumbers = numbers - move
                id = _numbers2id(nextNumbers)
                ids.append(id)
            successors.append((dices, ids))

    boxes[n] = (numbers, Box(numbers).getPenalty(), None, successors, None)

def _fill(i):
    numbers, currentPenalty, expectedPenalty, successors, newSuccessors = boxes[i]
    # we already handled this entry, no further processing needed
    if expectedPenalty is not None:
        return

    possiblePenaltys = []
    newSuccessors = []
    for dices, nextIds in successors:
        # no nextIds => Game Over; we know the penalty
        if len(nextIds) == 0:
            penalty = currentPenalty
            nextId = None
        else:
            minP = None
            minPid = None
            for nextId in nextIds:
                _fill(nextId)
                if minP is None or boxes[nextId][2] < minP:
                    minPid = nextId
                    minP = boxes[nextId][2]
            penalty = minP
            nextId = minPid
        newSuccessors.append((dices, nextId, penalty))
        possiblePenaltys.append(penalty)
    expectedPenalty = sum(possiblePenaltys) / len(possiblePenaltys)
    boxes[i] = (numbers, currentPenalty, expectedPenalty, successors, newSuccessors)

# start with a full box, each bit set
_fill(511)

def heuristicDecider(numbers, dices, moves):
    id = _numbers2id(numbers)
    numbersB, currentPenalty, expectedPenalty, oldSuccessors, successors = boxes[id]
    assert(numbers == numbersB)

    nextId = None
    for sucDices, sucNextId, sucPenalty in successors:
        if dices == sucDices:
            nextId = sucNextId
    assert(nextId is not None)

    nextNumbers, nextCurrentPenalty, nextExpectedPenalty, nextOldSuccessors, nextSuccessors = boxes[nextId]
    move = numbers - nextNumbers
    assert(move in moves)

    return move

class PredictingDecider:
    def __init__(self, preparedDices):
        self.preparedDices = preparedDices

    def decide(self, numbers, dices, moves):
        id = _numbers2id(numbers)
        numbers, currentPenalty, expectedPenalty, allSuccessors, successors = boxes[id]

        def _minimumPenaltyMove(nextId, dicesI):
            minPenalty = None
            minPenaltyMove = None

            numbers, currentPenalty, expectedPenalty, allSuccessors, successors = boxes[nextId]
            nextDices = self.preparedDices.peek(dicesI)
            if currentPenalty <= 6:
                nextDices = (nextDices[0], 0)

            for sucDices, sucNextIds in allSuccessors:
                if sucDices == nextDices:
                    for sucNextId in sucNextIds:
                        penalty, move = _minimumPenaltyMove(sucNextId, dicesI + 1)
                        if minPenalty is None or penalty < minPenalty:
                            minPenalty = penalty
                            minPenaltyMove = numbers - boxes[sucNextId][0]

            if minPenaltyMove is None:
                return currentPenalty, None

            return minPenalty, minPenaltyMove

        minPenalty, minPenaltyMove = _minimumPenaltyMove(id, -1)
        if minPenaltyMove is None:
            minPenaltyMove = moves[0]
        assert(minPenaltyMove in moves)

        return minPenaltyMove

deciders = [("random", lambda x: shittyDecider), ("higestNumber", lambda x: highestFirst), ("heuristicDecider", lambda x: heuristicDecider), ("predicting", lambda x: PredictingDecider(x).decide)]

# compare deciders in one example
if True:
    diceRolls = [rollRandomDices() for i in range(100)]

    for deciderLabel, generateDecider in [("random", lambda x: shittyDecider), ("higestNumber", lambda x: highestFirst), ("heuristicDecider", lambda x: heuristicDecider), ("predicting", lambda x: PredictingDecider(x).decide)]:
        preparedDices = PreparedDices(diceRolls)
        decider = generateDecider(preparedDices)

        print(deciderLabel)
        game = GameRunner(Game(), decider, preparedDices.roll)
        game.run(debug=True)
        print()

# compare deciders with 1000 rounds each
if False:
    rolls = [rollRandomDices() for i in range(10000)]
    for deciderLabel, generateDecider in deciders:
        preparedDices = PreparedDices(rolls)
        decider = generateDecider(preparedDices)

        resultSum, resultCount = 0, 0
        for i in range(1000):
            game = GameRunner(Game(), decider, preparedDices.roll)
            penalty = game.run()

            resultSum += penalty
            resultCount += 1

        print("Average Penalty for {} in {} games: {}".format(deciderLabel, resultCount, resultSum / resultCount))

# print statistics regarding one specific game state
if False:
    numbers = {1,2,3,4,5,6,7,8,9}
    dices = (6,4)
    numbers = {2,3,4,5,6,7,8}
    dices = None

    id = _numbers2id(numbers)
    numbersB, currentPenalty, expectedPenalty, oldSuccessors, successors = boxes[id]
    assert(numbers == numbersB)

    print("Numbers:  {}".format(numbersB))
    if dices is not None:
        print("Dices:    {} + {} = {}".format(dices[0], dices[1], dices[0] + dices[1]))
    print("Penalty:  {:5.2f}".format(expectedPenalty))

    output = []
    for sucDices, sucNextIds in oldSuccessors:
        if dices is None or sucDices == dices:
            for nextId in sucNextIds:
                nextNumbers, nextCurrentPenalty, nextExpectedPenalty, nextOldSuccessors, nextSuccessors = boxes[nextId]
                output.append((sucDices, nextNumbers, nextExpectedPenalty, nextId))

    output.sort(key=lambda row: boxes[row[3]][2])
#    output.sort(key=lambda row: row[0])
    for sucDices, nextNumbers, nextExpectedPenalty, nextId in output:
        print("{} {:>15}   {:05.2f}  {:+6.2f}".format(sucDices, str(numbersB - nextNumbers), nextExpectedPenalty, nextExpectedPenalty - expectedPenalty))