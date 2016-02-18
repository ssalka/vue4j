=====
PyVUE
=====

A minimal graph extractor and Neo4j import tool for [VUE](http://vue.tufts.edu/). Using PyVUE, any VUE concept map can be easily translated into a Neo4j graph instance, allowing for the handling of VUE maps in a more data-centric fashion.

## Install

To get started with PyVUE, simply add the package with your preferred installer:

```pip install pyvue```

```easy_install pyvue```

## Usage

PyVUE implements a customized file reader, which must be passed a valid .vue file:

```
from pyvue import VUE

vue = VUE('your_vue_map.vue')
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

PyVUE can also insert graph data into Neo4j:

```
from py2neo import authenticate

config = {
    'host_port': 'localhost:7474',
    'user_name': 'neo4j',
    'password': 'neo4j'
}

authenticate(**config)

graph = vue.to_neo4j(confirm_success=True)
```

If starting from a fresh Neo4j instance, confirm the VUE data import via `vue.confirm_transaction(G)`.


## History

### 0.1 // 2016-02-18
Initial release. Known bugs: does not yet work for resource-heavy VUE maps (e.g. many external links/files)

## Credits

PyVUE was written by [Steven Salka](http://ssalka.io)

## License

PyVUE is published under the [MIT License](https://github.com/ssalka/pyvue/blob/master/LICENSE)