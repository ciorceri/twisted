
import warnings
from twisted.python import components
from twisted.python.reflect import qual

from twisted.web2 import iweb

#try:
#    import nevow
#    from nevow import inevow
#    dataqual = qual(inevow.IData)
#except ImportError:
dataqual = object()

_marker = object()

def megaGetInterfaces(adapter):
    adrs = [qual(x) for x in components.getInterfaces(adapter)]
    ## temporarily turn this off till we need it
    if False: #hasattr(adapter, '_adapterCache'):
        adrs.extend(adapter._adapterCache.keys())
    return adrs


class WebContext(object):
    _remembrances = None
    tag = None
    _slotData = None
    parent = None

    # XXX: can we get rid of these 4 somehow?
    isAttrib = property(lambda self: False)
    precompile = property(lambda self: False)
    def with(self, tag):
        warnings.warn("use WovenContext(parent, tag) instead", DeprecationWarning, stacklevel=2)
        return WovenContext(self, tag)
    
    def arg(self, get, default=None):
        """Placeholder until I can find Jerub's implementation of this

        Return a single named argument from the request arguments
        """
        req = self.locate(iweb.IRequest)
        return req.args.get(get, [default])[0]

        
    
    def __init__(self, parent=None, tag=None, remembrances=None):
        self.tag = tag
        sd = getattr(tag, 'slotData', None)
        if sd is not None:
            self._slotData = sd
        self.parent = parent
        self._remembrances = remembrances

    def remember(self, adapter, interface=None):
        """Remember an object that implements some interfaces.
        Later, calls to .locate which are passed an interface implemented
        by this object will return this object.
        
        If the 'interface' argument is supplied, this object will only
        be remembered for this interface, and not any of
        the other interfaces it implements.
        """
        if interface is None:
            interfaceList = megaGetInterfaces(adapter)
            if not interfaceList:
                interfaceList = [dataqual]
        else:
            interfaceList = [qual(interface)]
        if self._remembrances is None:
            self._remembrances = {}
        for interface in interfaceList:
            self._remembrances[interface] = adapter
        return self

    def locate(self, interface, depth=1):
        """Locate an object which implements a given interface.
        Objects will be searched through the context stack top
        down.
        """
        key = qual(interface)
        if depth < 0:
            full = []
            while True:
                try:
                    full.append(self.locate(interface, len(full)+1))
                except KeyError:
                    break
            #print "full", full, depth
            if full:
                return full[depth]
            return None
        if self._remembrances is not None and self._remembrances.has_key(key):
            depth -= 1
            if not depth:
                return self._remembrances[key]
        if self.parent is None:
            raise KeyError, "Interface %s was not remembered." % key
        return self.parent.locate(interface, depth)

    def chain(self, context):
        """For nevow machinery use only.

        Go to the top of this context's context chain, and make
        the given context the parent, thus continuing the chain
        into the given context's chain.
        """
        top = self
        while top.parent is not None:
            if top.parent.tag is None:
                ## If top.parent.tag is None, that means this context (top)
                ## is just a marker. We want to insert the current context
                ## (context) as the parent of this context (top) to chain properly.
                break
            top = top.parent
            if top is context: # this context is already in the chain; don't create a cycle
                return
        top.parent = context

    def fillSlots(self, name, stan):
        """Set 'stan' as the stan tree to replace all slots with name 'name'.
        """
        if self._slotData is None:
            self._slotData = {}
        self._slotData[name] = stan

    def locateSlotData(self, name):
        """For use by nevow machinery only, or for some fancy cases.

        Find previously remembered slot filler data.
        For use by flatstan.SlotRenderer"""
        if self._slotData:
            data = self._slotData.get(name, _marker)
            if data is not _marker:
                return data
        if self.parent is None:
            raise KeyError, "Slot named '%s' was not filled." % name
        return self.parent.locateSlotData(name)
    
    def clone(self, deep=True, cloneTags=True):
        ## don't clone the tags of parent contexts. I *hope* code won't be
        ## trying to modify parent tags so this should not be necessary.
        ## However, *do* clone the parent contexts themselves.
        ## This is necessary for chain(), as it mutates top-context.parent.
        
        if self.parent:
            parent=self.parent.clone(cloneTags=False)
        else:
            parent=None
        if cloneTags:
            tag = self.tag.clone(deep=deep)
        else:
            tag = self.tag
        if self._remembrances is not None:
            remembrances=self._remembrances.copy()
        else:
            remembrances=None
        return type(self)(
            parent = parent,
            tag = tag,
            remembrances=remembrances,
        )

    def getComponent(self, interface, registry=None, default=None):
        """Support IFoo(ctx) syntax.
        """
        try:
            return self.locate(interface)
        except KeyError:
            return default


class FactoryContext(WebContext): 
    """A context which allows adapters to be registered against it so that an object 
    can be lazily created and returned at render time. When ctx.locate is called
    with an interface for which an adapter is registered, that adapter will be used
    and the result returned.
    """
    cache = None
    def locate(self, interface, depth=1):
        if self.cache is None: self.cache = {}
        else:
            adapter = self.cache.get(interface, None)
            if adapter is not None:
                return adapter

        ## Prevent infinite recursion from interface(self) calling self.getComponent calling self.locate
        ## Shadow the class getComponent
        def shadow(interface, registry=None, default=None):
            if registry:
                return registry.getAdapter(self, interface, default)
            return default
        self.getComponent = shadow
        adapter = interface(self, None)
        ## Remove shadowing
        if getattr(self, 'getComponent', None) is shadow:
            del self.getComponent

        if adapter is not None:
            self.cache[interface] = adapter
            return adapter
        return WebContext.locate(self, interface, depth)


class SiteContext(FactoryContext):
    """A SiteContext is created and installed on a NevowSite upon initialization.
    It will always be used as the root context, and can be used as a place to remember
    things sitewide.
    """
    pass


class RequestContext(FactoryContext):
    """A RequestContext has adapters for the following interfaces:
    
    ISession
    IFormDefaults
    IFormErrors
    IHand
    IStatusMessage
    """
    pass

components.registerAdapter(lambda ctx: ctx.tag, RequestContext, iweb.IRequest)

def getRequestContext(self):
    top = self.parent
    while not isinstance(top, RequestContext):
        top = top.parent
    return top

class PageContext(FactoryContext):
    """A PageContext has adapters for the following interfaces:

    IRenderer
    IRendererFactory
    IData
    """
    context = property(getRequestContext)
