from lxml import etree
from py2neo import Graph
from py2neo.cypher import MergeNode, DatabaseError
from collections import OrderedDict
from tabulate import tabulate

def parse_children(root, vertices=None, edges=None, residual_edges=None):
    """
    Conducts a depth-first search of an XML element tree, classifying
    each element (representing a VUE object) as either a node or link.

    This algorithm uses the conventional letters V and E to denote the
    sets of graph 'vertices' and 'edges,' respectively. However, the
    terms 'node' and 'link' are also used to refer to graph objects.
    Neo4j also favors 'relationship' over 'edge' and 'link.'

    Note: the tree represents the XML structure of the VUE graph, not
    the graph itself - XML tags are used in VUE to denote both nodes and links.

    :param root: XML element tree root (contains all graph data as 'child' tags)
    :param vertices: initial dictionary of vertices
    :param edges: initial dictionary of edges
    :param skipped_elements: XML edge elements that raised a KeyError
    :return:  tuple G = (V, E) of graph data
    """

    # Initializations
    V = vertices or {}
    E = edges or {}
    E_res = residual_edges or {}

    params = {'V': V, 'E': E, 'E_res': E_res,
              'parent_ID': root.get('ID')}
    parser = ElementParser()

    # DFS + element classification
    for element in root.findall('child'):
        element_type = element.get(parser._xsi_type)
        if element_type in ['node','link']:
            V, E, E_res = parser.handler[element_type](parser,element,**params)
            params.update({'V': V, 'E': E, 'E_res': E_res})

    # Iterating through skipped edges
    skipped_elements = E_res.copy()
    while skipped_elements:
        for id, element in skipped_elements.items():
            V, E, E_res = parser.handle_as_link(element,**params)
            if id in E.keys(): del E_res[id] # Endpoint lookup succeeded
            params.update({'V': V, 'E': E, 'E_res': E_res})
        skipped_elements = E_res.copy()

    if root.tag == 'LW-MAP':
        # Final result sorted by ID
        V = OrderedDict(sorted(V.items()))
        E = OrderedDict(sorted(E.items()))
    return V, E

def MergeRelationship(args):
    '''
    Relationship equivalent of py2neo MergeNode function

    :param args: tuple of string arguments
    :return: Cypher query for merging a relationship
    '''
    return \
        'MATCH (start:Node {VUE_ID: %s}),(end:Node {VUE_ID: %s}) \
        MERGE (start)-[r:%s{%s}]->(end) \
        RETURN start.VUE_ID, type(r), end.VUE_ID' % (*args,)


class ElementParser:

    def __init__(self):
        self._xsi_type = '{http://www.w3.org/2001/XMLSchema-instance}type'

    def handle_as_node(self,element, **kwargs):
        """
        Handles an element identified as a node, extracts relevant
        data and inserts into current node dictionary. Makes a
        recursive call to parse_children if any nested nodes are found.

        :param element: element to handle
        :param kwargs: sets V, E, E_res
        :return: updated sets V, E, E_res
        """
        V, E, E_res = (kwargs[key] for key in ['V','E','E_res'])
        parent_ID = kwargs['parent_ID']
        ID = int(element.get('ID'))

        if element.find('resource') is not None:
            # Handles attached images & URLs
            rs = element.find('resource')
            type_ = rs.get('type')
            title = rs.findtext('title')
            resource = dict(ID=ID, title=title, type=type_)
            prop_tags = rs.findall('property')
            for tag in prop_tags:
                resource.__setitem__(*tag.attrib.values())
        else: resource = None

        if element.find('metadata-list') is not None:
            # Handles node metadata
            metadata = {'keywords': []}
            md_tags = element.findall('md')
            for tag in md_tags:
                tag_is_keyword = tag.attrib['t'] == '1'
                if tag_is_keyword:
                    value = tag.attrib['v']
                    metadata['keywords'].append(value)
                else: # Unknown metadata tag
                    raise ValueError('Invalid tag attribute on MD: t="%s"' % tag.attrib['t'])
        else: metadata = None

        label = element.get('label',default='').replace('\n',' ')
        properties = {
            'VUE_ID': ID, 'type': 'Node', 'label': label,
            'resource': str(resource), 'metadata': str(metadata),
            'layer': element.get('layerID'),
            'parent': parent_ID
        }

        V[ID] = {
            'label': label,
            'properties': properties
        }

        if element.find('child') is not None: # Handles nested nodes
            V, E = parse_children(element, V, E, E_res)

        return V, E, E_res

    def handle_as_link(self, element, **kwargs):
        """
        Handles an element identified as a link, extracts relevant
        data and inserts into current link dictionary.

        :param element: element to handle
        :param kwargs: sets V, E, E_res
        :return: updated sets V, E, E_res
        """
        ID = int(element.get('ID'))
        V = kwargs['V']
        E, E_res = kwargs['E'], kwargs['E_res']
        endpoints = self.link_endpoint_tags(element, V, E)
        if endpoints:
            endpoint_types = self.get_object_types(endpoints)
            link_type = '{}-{}'.format(*endpoint_types)

            arrow_state = int(element.get('arrowState'))
            if arrow_state == 3:
                directed = 'bidirectional'
            else:
                if arrow_state == 1: endpoints.reverse()
                directed = 'undirected' if not arrow_state else 'directed'

            E[ID] = {
                'start_node': endpoints[0],
                'label': element.get('label', default=''),
                'end_node': endpoints[1],
                'properties': {
                    'VUE_ID': ID, 'directed': directed,
                    'type': 'Link: ' + link_type
                }
            }
        else:
            # Edge is referencing downstream XML element
            # Retry in next iteration
            E_res[ID] = element

        return V, E, E_res

    def get_object_types(self,iterable):
        """ Returns object property types """
        return [obj['properties']['type'] for obj in iterable]

    def link_endpoint_tags(self, element, V, E):
        """
        Gets 2 child tags corresponding to a link's endpoints

        :param element: parent element of endpoint tags
        :param V: current set of nodes
        :param E:current set of links
        :return:
        """
        endpoints = []
        for i in [1,2]:
            tag = element.find('ID' + str(i))
            tag_type = tag.get(self._xsi_type)
            tag_set = V if tag_type == 'node' else E
            graph_element_ID = int(tag.text)
            try:
                endpoint = tag_set[graph_element_ID]
                if endpoint is None:
                    raise ValueError('Endpoint is none')
                endpoints.append(endpoint)
            except KeyError:
                return False
        return endpoints

    handler = {
        'node': handle_as_node,
        'link': handle_as_link
    }


class VUE4j:

    def __init__(self,file=None):
        self.file = file

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self,path):
        """
        Sets file path, raising a ValueError
        if an invalid path is provided
        
        :param path: absolute file path of .vue file
        """
        self._file = path
        if not path or path[-4:] != '.vue':
            raise ValueError('Class VUE requires a .vue file to read')
        else:
            self.root = self.get_root()
            self.V, self.E = parse_children(self.root)

    def nodes(self,key='label',verbose=False):
        """
        Returns specified data on graph nodes 
        
        :param key: key to request from each node
        :param verbose: boolean specifying output format
        :return: Graph node data (OrderedDict by node ID)
        """
        if verbose:
            node_properties = [element[key] for element in self.V.values()]
            node_list = list(zip(self.V.keys(),node_properties))
            headers = ('ID',key.upper())
            self._nodes = tabulate(node_list,headers=headers)
        else:
            self._nodes = self.V
        
        return self._nodes

    def links(self, max_length=30, verbose=False):
        """
        Returns a list of links/relationships/edges in the graph
        
        :param max_length: string length to truncate at
        :param verbose: boolean specifying output format
        :return: Graph link data (OrderedDict by link ID) 
        """
        if verbose:
            edge_list = []
            for id, edge in self.E.items():
                start, end = edge['start_node']['label'], edge['end_node']['label']
                start = start[:max_length] + (start[max_length:] and '...')
                end = end[:max_length] + (end[max_length:] and '...')
                arrow_str = self.rel_arrow_str(edge)
                record = (id,start,arrow_str,end) if verbose else (start, end)
                edge_list.append(record)
            self._links = tabulate(edge_list,headers=('Link ID','Node 1','Relationship','Node 2'))
        else:
            self._links = self.E

        return self._links


    def get_root(self):
        """
        Removes non-essential tags from a given VUE (XML) file.
        
        :return: Root of XML element tree
        """
        with open(self.file) as f:
            while True:
                line = f.readline()
                if not line:
                    break
                elif not line.startswith('<LW-MAP'):
                    continue
                else:
                    data = line + f.read()
                    return etree.fromstring(data)

    def rel_arrow_str(self, link):
        """
        Consructs a string representation of an arrow/link,
        used in the verbose printing of an edge table

        :param link: Link to get representation of
        :return: string representation of link
        """
        rel = link['label']
        arrow_tag = '[{}]'.format(rel).replace('[]','')
        directed = link['properties']['directed']
        left_arrow = ' <' if directed == 'bidirectional' else ''
        right_arrow = '> ' if directed != 'undirected' else ''

        return '--'.join([left_arrow,arrow_tag,right_arrow])

    def get_endpoints(self,link):
        """ Returns the endpoint IDs of a link """
        return (link[key+'_node']['properties']['VUE_ID'] for key in ['start','end'])

    @property
    def neo4j_compatible_links(self):
        return self._compatible_links

    @neo4j_compatible_links.setter
    def neo4j_compatible_links(self,links):
        """
        Filters out VUE links that have other links as endpoints,
        as this feature is not currently supported by Neo4j

        :param warn: If true, issues a warning when any incompatible links are found
        :return: dict of compatible links by ID
        """
        self._compatible_links =  {
            id: edge for (id,edge) in links.items()
            if 'Link' not in edge['properties']['type'][6:]
        }
        diff = set(links.keys()) - set(self._compatible_links.keys())
        if diff:
            warning = 'Warning: file \'%s\' contains link types incompatible with Neo4j'
            print(warning % self.file)

    def to_neo4j(self):
        """
        Merges a Neo4j database with graph data
        obtained from parse_children algorithm

        :return: Neo4j graph object, populated with nodes
                 and relationships from self.V, self.E
        """

        G = Graph()


        self.neo4j_compatible_links = self.E

        # Node transaction
        node_tx = G.cypher.begin()
        for id, node in self.V.items():
            statement = MergeNode('Node','VUE_ID',id).set(node['label'],**node['properties'])
            node_tx.append(statement)
        node_tx.commit()

        # Link transaction
        link_tx = G.cypher.begin()
        for id, link in self.neo4j_compatible_links.items():
            props = link['properties']
            str_props = ', '.join(['{}: "{}"'.format(k,str(v)) for k,v in props.items()])
            endpointIDs = self.get_endpoints(link)
            label = link['label'] or props['directed']
            args = (*endpointIDs,label,str_props)
            statement = MergeRelationship(args)
            link_tx.append(statement)
        link_tx.commit()

        # Done
        return G

    def confirm_transaction(self,graph):
        """
        Tests whether the number of extracted data values in V, E
        match the sizes of Neo4j nodes & relationships. Useful when
        importing a VUE map into a new/empty Neo4j graph.

        :param graph: Neo4j graph to check against
        :return: True/False, confirming whether the
                 graph transaction was successful
        """
        node_records = graph.cypher.execute('MATCH (n) return n.VUE_ID order by n.VUE_ID')
        relationship_records = graph.cypher.execute('START r=rel(*) RETURN r')

        v, n = len(self.V), len(node_records)
        e, r = len(self.neo4j_compatible_links), len(relationship_records)

        nodes_match = (v - n == 0)
        links_match = (e - r == 0)

        set_lengths = tuple(str(var) for var in [v,n,e,r])
        assert nodes_match, 'Got unequal node sets: %s, %s' % set_lengths[:2]
        assert links_match, 'Got unequal edge sets: %s, %s' % set_lengths[2:]

        return nodes_match and links_match