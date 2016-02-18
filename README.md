=====
VUE4j
=====

VUE4j is A Python-based data extraction tool & Neo4j integration for [VUE](http://vue.tufts.edu/), a graph/concept-mapping interface.

Using VUE4j, node and link data from .vue source files can be extracted and translated into Neo4j instances, allowing for the handling of VUE maps as graph databases (and vice versa).

## Install

To get started with VUE4j, add the package with your preferred installer:

`pip install vue4j`

or

`easy_install vue4j`

or [grab it off of PyPi](https://pypi.python.org/pypi/vue4j/0.1).

## Usage

VUE4j implements a customized file reader, which must be passed a valid .vue file:

```
from vue4j import VUE4j

vue = VUE4j('your_vue_map.vue')
```

Instances of the VUE class make it easy to list nodes & links in any VUE map:

```
# Get nodes by ID & title
node_list = vue.nodes(verbose=True)
print(node_list)

# Print a table view of graph edges
edge_table = vue.links(verbose=True)
print(edge_table)
```

VUE4j can also insert graph data into Neo4j:

```
from py2neo import authenticate

config = {
    'host_port': 'localhost:7474',
    'user_name': 'your_username', # default: neo4j
    'password': 'your_password' # default: neo4j
}

authenticate(**config)

graph = vue.to_neo4j()

assert vue.confirm_transaction(graph)
```

If starting from a fresh Neo4j instance, confirm the VUE data import via `vue.confirm_transaction(G)`.


## History

### 0.1 // 2016-02-18
Initial release. Known bugs: does not yet work for resource-heavy VUE maps (e.g. many external links/files)

## Credits

VUE4j was written by [Steven Salka](http://ssalka.io)

## License

VUE4j is published under the [MIT License](https://github.com/ssalka/VUE4j/blob/master/LICENSE)
