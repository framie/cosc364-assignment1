A routing daemon written in Python that runs over several instances on a single machine to emulate a network. 

This program works using configuration files to identify the number of UDP sockets necessary for communication for a network. Afterwards, the router will enter an infinite loop wherein it will react to incoming events based on the result of select() calls. The routing daemon is designed to handle new/disrupted connections and is also able to dynamically calculate the shortest distance to every other routing daemon in the network.
