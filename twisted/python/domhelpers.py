# domhelpers.py

from twisted.web import microdom

class NodeLookupError(Exception): pass

def substitute(request, node, subs):
    """
    Look through the given node's children for strings, and
    attempt to do string substitution with the given parameter.
    """
    for child in node.childNodes:
        if child.nodeValue:
            child.replaceData(0, len(child.nodeValue), child.nodeValue % subs)
        substitute(request, child, subs)

def _get(node, nodeId):
    """
    (internal) Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes.
    """
    if hasattr(node, 'hasAttributes') and node.hasAttributes() and ((str(node.getAttribute("id")) == nodeId) or (str(node.getAttribute("class")) == nodeId) or (str(node.getAttribute("model")) == nodeId)):
        return node
    if node.hasChildNodes():
        if hasattr(node.childNodes, 'length'):
            length = node.childNodes.length
        else:
            length = len(node.childNodes)
        for childNum in range(length):
            result = _get(node.childNodes[childNum], nodeId)
            if result: return result

def get(node, nodeId):
    """
    Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes. If there is no such node, raise
    L{NodeLookupError}.
    """
    result = _get(node, nodeId)
    if result: return result
    raise NodeLookupError, nodeId

def getIfExists(node, nodeId):
    """
    Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes.  If there is no such node, return
    C{None}.
    """
    return _get(node, nodeId)

def getAndClear(node, nodeId):
    result = get(node, nodeId)
    if result:
        clearNode(result)
    return result

def clearNode(node):
    """
    Remove all children from the given node.
    """
    if node.hasChildNodes():
        while len(node.childNodes):
            node.removeChild(node.lastChild())

def locateNodes(nodeList, key, value):
    """
    Find subnodes in the given node where the given attribute
    has the given value.
    """
    returnList = []
    if not isinstance(nodeList, type([])):
        return locateNodes(nodeList.childNodes, key, value)
    
    for childNode in nodeList:
        if not hasattr(childNode, 'getAttribute'):
            continue
        if str(childNode.getAttribute(key)) == value:
            returnList.append(childNode)
        returnList.extend(locateNodes(childNode, key, value))
    return returnList
    
def superSetAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superSetAttribute(child, key, value)

def superPrependAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    old = node.getAttribute(key)
    if old:
        node.setAttribute(key, value+'.'+old)
    else:
        node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superPrependAttribute(child, key, value)

def superAppendAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    old = node.getAttribute(key)
    if old:
        node.setAttribute(key, old + '/' + value)
    else:
        node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superAppendAttribute(child, key, value)

def getElementsByTagName(iNode, name):
    childNodes = iNode.childNodes[:]
    gathered = []
    while childNodes:
        node = childNodes.pop(0)
        if node.childNodes:
            childNodes.extend(node.childNodes)
        if node.nodeName == name:
            gathered.append(node)
    print "gathered", gathered
    return gathered

def gatherTextNodes(iNode):
    childNodes = iNode.childNodes[:]
    gathered = []
    while childNodes:
        node = childNodes.pop(0)
        if node.childNodes:
            childNodes.extend(node.childNodes)
        if hasattr(node, 'nodeValue'):
            gathered.append(node.nodeValue)
    print "text", gathered
    return ''.join(gathered)


class RawText(microdom.Text):
    """This is an evil and horrible speed hack. Basically, if you have a big
    chunk of XML that you want to insert into the DOM, but you don't want
    to incur the cost of parsing it, you can construct one of these and insert 
    it into the DOM. This will most certainly only work with minidom as the 
    API for converting nodes to xml is different in every DOM implementation.
    
    This could be improved by making this class a Lazy parser, so if you
    inserted this into the DOM and then later actually tried to mutate
    this node, it would be parsed then.
    """
    def writexml(self, writer, indent="", addindent="", newl=""):
        writer.write("%s%s%s" % (indent, self.data, newl))
