import sys                          # for passing filename as argument and error handling
import socket                       # for sockets
from select import select           # for select() function
from pathlib import Path            # to verify file exists
import pickle                       # for converting Packet class to bytes
import time                         # for timing
from copy import deepcopy           # for creating deep copies
from random import randrange        # for uniformly distributing different timer values

SHOW_TABLE = True                   # flag for printing out routing table on update (periodic/triggered)
DEBUG = False                       # debug flag for showing extra print statements

class Packet:
    # Class for the routing update packets being sent between routing demons.
    def __init__(self, routerId, data=""):
        self.routerId = routerId
        self.version = 2            # version number is always 2
        self.type = "response"      # packets are always response packets
        self.data = data
        
        
class Route:
    # Class for the routes that are in the routing table for each routing demon.
    def __init__(self, port, weight, nextHop, updateVal = 0, timerVal = 0):
        self.port = port
        self.weight = weight
        self.nextHop = nextHop
        self.updateVal = updateVal
        self.timerVal = timerVal
        
    def __repr__(self):
        message = "[" + str(self.port) + ", " + str(self.weight) + ", " + str(self.nextHop)
        message += ", " + str(self.updateVal) + ", " + str(self.timerVal) + "]"
        return message
    
    def __eq__(self, other):
        if (self.port != other.port):
            return False
        if (self.weight != other.weight):
            return False
        if (self.nextHop != other.nextHop):
            return False
        if (self.updateVal != other.updateVal):
            return False
        if (self.timerVal != other.timerVal):
            return False
        return True


def readConfigFile(routerId, inputPorts, routingTable, neighbourPorts):
    # Reads the config file as indicated by the command line parameter, and appends
    # the values from the file into the argument lists. Doesn't matter which order
    # the values appear in the config file or if there are empty lines or comment in between
    
    timer = 30
    if (len(sys.argv) == 1):
        sys.exit("ERROR: no config file specified")
    if (len(sys.argv) > 2):
        sys.exit("ERROR: too many command line arguments - only 1 config file required")    
    filename = sys.argv[1]            # sys.argv[1] is the config file to read
    if not Path(filename).is_file():
        sys.exit("ERROR: config file doesn't exist - exiting...")
    file = open(filename, "r")
    
    if (DEBUG): print("Reading config file...")
    for line in file:
        if (line[:9] == "router-id"):
            if (routerId):
                sys.exit("ERROR: [router-id] router-id already read from config file")
            if (len(line.split()) != 2):
                sys.exit("ERROR: [router-id] incorrect number of router-id arguments - must be 1")
            if(not line.split()[1].isdigit()):
                sys.exit("ERROR: [router-id] router-id must be an integer")
            if (int(line.split()[1]) < 1 or int(line.split()[1]) > 64000):
                sys.exit("ERROR: [router-id] invalid router-id: " + line.split()[1] + " - must be between 1 and 64000")
            if (int(line.split()[1]) in routingTable):
                sys.exit("ERROR: [router-id] router-id " + line.split()[1] + " already used in outputs")
            routerId.append(int(line.split()[1]))
            if (DEBUG): print("router-id:", routerId[0])
        
        if (line[:11] == "input-ports"):
            if (len(inputPorts) > 0):
                sys.exit("ERROR: [input-ports] input-ports already read from config file")
            for port in line[12:].strip().split(", "):
                if (len(port) == 0):
                    sys.exit("ERROR: [input-ports] incorrect number of arguments, must be at least 1") 
                if (not port.isdigit()):
                    sys.exit("ERROR: [input-ports] invalid input-port formatting - must be integer, integer, ...")
                if (int(port) < 1024 or 64000 < int(port)):
                    sys.exit("ERROR: [input-ports] input-port out of range: " + port + " - must be between 1024 and 64000")
                if (int(port) in inputPorts):
                    sys.exit("ERROR: [input-ports] duplicate input-port: " + port)
                if (int(port) in neighbourPorts):
                    sys.exit("ERROR: [input-ports] input-port: " + port + " already used in outputs")
                inputPorts.append(int(port))
            if (DEBUG): print("input-ports:", inputPorts)
    
        if (line[:7] == "outputs"):
            for info in line[8:].strip().split(", "):
                if (len(info) == 0):
                    sys.exit("ERROR: [outputs] incorrect number of arguments, must be at least 1") 
                info = info.split("-")
                if (not info[0].isdigit() or len(info) != 3):
                    sys.exit("ERROR: [outputs] invalid output formatting, must be integer-integer-integer, ...")
                if (int(info[0]) < 1024 or 64000 < int(info[0])):
                    sys.exit("ERROR: [outputs] invalid output port: " + info[0] + " - must be between 1024 and 64000")
                if (int(info[0]) in inputPorts):
                    sys.exit("ERROR: [outputs] output port: " + info[0] + " already used in input-ports")
                if (len(routerId) == 1 and int(info[2]) == routerId[0]):
                    sys.exit("ERROR: [outputs] router-id: " + info[2] + " already used for current router")
                if (int(info[2]) in routingTable):
                    sys.exit("ERROR: [outputs] duplicate router-id: " + info[2])
                if (int(info[2]) < 1 or int(info[2]) > 64000):
                    sys.exit("ERROR: [outputs] router-id out of range: " + info[2] + " - must be between 1 and 64000")
                if (int(info[1]) < 1 or 15 < int(info[1])):         # 16 is infinity in RIP
                    sys.exit("ERROR: [outputs] metric out of range: " + info[1] + " - must be between 1 and 15")
                if (int(info[0]) in neighbourPorts):
                    sys.exit("ERROR: [outputs] duplicate output port: " + info[0])
                
                newRoute = Route(int(info[0]), int(info[1]), int(info[0]))
                routingTable[int(info[2])] = newRoute
                neighbourPorts.append(int(info[0]))
            if (DEBUG): print("outputs:", routingTable)
            
        if(line[:11] == "timer-value"):
            line = line[12:].strip().split()
            if (len(line) != 1): 
                sys.exit("ERROR: [timer-value] incorrect number of arguments - must be 1")            
            if (not line[0].isdigit()):
                sys.exit("ERROR: [timer-value] invalid timer-value formatting - must be an integer")
            if (int(line[0]) < 1):
                sys.exit("ERROR: [timer-value] value must be greater than 0")
            timer = int(line[0])
    
    if (not routerId or not inputPorts or not routingTable):
        message = "ERROR: missing line in config file for: "
        if (not routerId):
            message += "routerId, "
        if (not inputPorts):
            message += "inputPorts, "
        if (not routingTable):
            message += "outputs"
        sys.exit(message)
    if (DEBUG): print()
    return timer


def createInputSockets(inputSockets, ports, address = '127.0.0.1'):
    # Creates and binds sockets to the port and address (127.0.0.1 default) specified,
    # then appends them to inputSockets.
    
    for i in range(0, len(ports)):
        try:
            socket_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # SOCK_DGRAM used for UDP Datagrams
        except:
            sys.exit("ERROR: failed to create socket with port: " + str(port))
            
        try:
            socket_in.bind((address, ports[i]))
        except:
            sys.exit("ERROR: failed to bind socket with port: " + str(port))
        inputSockets.append(socket_in)


def sendPacketToNeighbours(routerId, outSocket, neighbourPorts, routingTable, address = '127.0.0.1'):
    # Sends a packet containing both this router's id and the routing table to the specified address
    # and neighbour ports.
    if (DEBUG): print("Sending packets to:", neighbourPorts)
    for port in neighbourPorts:
        
        sendTable = deepcopy(routingTable)          # for split horizon
        toRemove = []
        for route in sendTable:
            if (sendTable[route].nextHop == port):
                toRemove.append(route)         
        for route in toRemove:
            del sendTable[route]        
        newPacket = Packet(routerId, data = sendTable)
        
        try:
            if (DEBUG): print("Sending packet to port:", port)
            outSocket.sendto(pickle.dumps(newPacket), (address, port))
        except:
            if (DEBUG): print("Failed to send packet to port:", port)


def updateRoutingTable(routerId, routingTable, data, inputPorts, originalTable):
    # Updates the routes in the routing table based on the argument data (routerId, routingTable) tuple.  
    dist = originalTable[data[0]].weight
    for router in data[1]:
        info = data[1][router]
        if (router != routerId and info.updateVal == 0):
            if (router not in routingTable and (info.weight + dist) < 16):
                newRoute = Route(info.port, info.weight + dist, originalTable[data[0]].port, 0, round(time.clock(), 2))
                routingTable[router] = newRoute
            if (router in routingTable):
                if (info.weight + dist < routingTable[router].weight):
                    newRoute = Route(info.port, info.weight + dist, originalTable[data[0]].port, 0)
                    del routingTable[router]
                    routingTable[router] = newRoute
                if (router in data[1] and info.updateVal != 1):
                    if (router not in originalTable or info.nextHop == originalTable[router].port):
                        routingTable[router].timerVal = round(time.clock(), 2)
                        
        if (router in routingTable and info.updateVal == 1):        # updateVal == 1 when there is poison reverse
            routingTable[router].updateVal = 1
        if (router in routingTable and info.updateVal == 0):
            routingTable[router].updateVal = 0
    
    if (data[0] in originalTable and (data[0] not in data[1] or (data[1][data[0]] + dist) < 16)):
        routingTable[data[0]] = deepcopy(originalTable[data[0]])
    routingTable[data[0]].timerVal = round(time.clock(), 2)
    
    
def checkRoutes(routingTable, timerVal):
    # Checks the routes in the routing table if any have been timed out (6 * timerVal since an update).
    # If it finds any timed out routes, returns True, otherwise returns False.
    updateFlag = False                  # for triggered updates
    for router in routingTable:	
        if (routingTable[router].updateVal == 0 and (routingTable[router].timerVal + (timerVal * 6)) < time.clock()):
            routingTable[router].weight = 16
            routingTable[router].updateVal = 1
            routingTable[router].timerVal = round(time.clock(), 2)
            updateFlag = True
    return updateFlag


def removeDeadRoutes(routingTable, timerVal, originalTable):
    # Removes any garbage (4 * timerVal since an update) routes from the routing table, and also any other
    # routes that may be affected by the removal of garbage routes.
    deadRoutes = []
    affectedRoutes = []
    for router in routingTable:
        if (routingTable[router].updateVal == 1 and (routingTable[router].timerVal + (timerVal * 4)) < time.clock()):
            deadRoutes.append(router)
    for route in deadRoutes:
        if (route in originalTable):
            for affectedRoute in routingTable:
                if routingTable[affectedRoute].nextHop == originalTable[route].port:
                    affectedRoutes.append(affectedRoute)
    for route in list(set(deadRoutes + affectedRoutes)):
        del routingTable[route]


def readFromSocket(inputSocket):
    # Attempts to read the data from the argument inputSocket. If it fails it prints an error message,
    # however on success returns the received data.
    recv = None
    try:
        recv, addr = inputSocket.recvfrom(1024)
        recv = pickle.loads(recv)
    except:
        if (DEBUG): print("Unable to read from socket", inputSocket.getsockname())    
    return recv

def verifyPacket(packet):
    # Verifies the packet given as an argument and returns False if any of the tests
    # in the function fail, otherwise returns True.
    if (packet.routerId < 1 or packet.routerId > 64000):
        return False
    if (packet.version != 2):
        return False
    if (packet.type != "response"):
        return False
    for router in packet.data:
        route = packet.data[router]
        if (router < 1 or router > 64000):
            return False
        if (route.port < 1024 or route.port > 64000):
            return False
        if (route.weight < 1 or route.weight > 16):
            return False
        if (route.nextHop < 1024 or route.nextHop > 64000):
            return False
        if (route.updateVal < 0 or route.updateVal > 1):
            return False
    return True    
    

def main():
    
    routerId = []                       # router-id for current router (1 < x < 64000)
    inputPorts = []                     # [ ports ]
    routingTable = dict()               # dict {id: [ port, cost, next hop, route change flag, [timers]] }
    neighbourPorts = []                 # [ ports ]
    inputSockets = []                   # [ sockets ]
    lastUpdate = 0                      # last time.clock() value where a timed update was sent
    timer = 30                          # value for timing, default is the 30-second value for RIPv2
                                        # 180 seconds for timer (6x), 120 seconds for garbage collection (4x)
    
    timer = readConfigFile(routerId, inputPorts, routingTable, neighbourPorts)
    routerId = routerId[0]
    originalTable = deepcopy(routingTable)
    createInputSockets(inputSockets, inputPorts)
    timerVal = randrange(800 * timer, 1200 * timer, 1) / 1000       # uniform distribution of up to 4000 timer values
    timerVal = 1    
    print("Routing demon (id = " + str(routerId) + ", timer = " + str(timerVal) + "s) is running...")
    
    while 1:
        readable, writable, special = select(inputSockets, [inputSockets[0]], [], 1)
        if (any (inputSocket in readable for inputSocket in inputSockets)):
            old_dict = deepcopy(routingTable)
            for inputSocket in readable:
                recv = readFromSocket(inputSocket)
                if (recv):
                    if (verifyPacket(recv)):
                        if (DEBUG): print("Packet successfully verified")
                        updateRoutingTable(routerId, routingTable, [recv.routerId, recv.data], inputPorts, originalTable)
                    else:
                        if (DEBUG): print("Dropped packet.")
            if (DEBUG and old_dict != routingTable): print("Updated routing table!")
        if (checkRoutes(routingTable, timerVal) == True or lastUpdate == 0 or lastUpdate + timerVal < time.clock()):
            lastUpdate = time.clock()
            removeDeadRoutes(routingTable, timerVal, originalTable)
            sendPacketToNeighbours(routerId, inputSockets[0], neighbourPorts, routingTable)
            if(SHOW_TABLE or DEBUG): print("Routing table (", str(round(time.clock(), 2)), "):", routingTable)   
            if (DEBUG): print()

if __name__ == "__main__":
    main()