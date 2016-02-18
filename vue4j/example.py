from vue4j import VUE4j

vue = VUE4j('your_map.vue')

# Get nodes by ID & title
node_list = vue.nodes(verbose=True)
print(node_list)

# Print a table view of graph edges
edge_table = vue.links(verbose=True)
print(edge_table)


# Connect to Neo4j via py2neo and populate a graph
from py2neo import authenticate

config = {
    'host_port': 'localhost:7474',
    'user_name': 'your_username', # default: neo4j
    'password': 'your_password' # default: neo4j
}

authenticate(**config)

graph = vue.to_neo4j()

assert vue.confirm_transaction(graph)