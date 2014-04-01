import os
import yaml
import re


class ConfigState(dict):
    def __getattr__(self, k):
        value = self[k]
        if isinstance(value, dict) and not isinstance(value, ConfigState):
            return ConfigState(value)
        else:
            return value

    def __setattr__(self, k, value):
        if isinstance(value, dict) and not isinstance(value, ConfigState):
            value = ConfigState(value)
        self.__setitem__(k, v)


class Field(ConfigState):
    def __init__(self, key, fn, required=False, value=None):
        self.key = key
        self.fn = fn
        self.required = required
        self.value = value

    def __call__(self, value):
        if value is None:
            if self.required:
                raise ValueError("Value is required: %s" % self.key)
            if self.value is None and getattr(self.fn, 'accepts_none', False):
                self.value = self.fn(None)
        else:
            self.value = self.fn(value)
        return self.value

    @classmethod
    def create(self, key, fn):
        if isinstance(fn, Field):
            field = fn
            return Field(key, field.fn, required=field.required, value=field.value)
        return Field(key, fn)


### Fields ###
class Field(object):
    def __init__(self, key, fn, required=False, value=None):
        self.key = key
        self.fn = fn
        self.required = required
        self.value = value

    def __call__(self, value):
        if value is None:
            if self.required:
                raise ValueError("Value is required: %s" % self.key)
            if self.value is None and getattr(self.fn, 'accepts_none', False):
                self.value = self.fn(None)
        else:
            self.value = self.fn(value)
        return self.value

    def update(self, value):
        self.fn.update(value)

    @classmethod
    def create(self, key, fn):
        if isinstance(fn, Field):
            field = fn
            return Field(key, field.fn, required=field.required, value=field.value)
        return Field(key, fn)


class Required(object):
    def __ror__(self, fn):
        return Field(None, fn, required=True)

required = Required()

class default(object):
    def __init__(self, value):
        self.value = value

    def __ror__(self):
        return Field(None, fn, value=self.value)


### Config ###
class ConfigState(dict):
    def __getattr__(self, k):
        value = self.get(k, None)
        if isinstance(value, dict) and not isinstance(value, ConfigState):
            return ConfigState(value)
        else:
            return value

    def __setattr__(self, k, value):
        if isinstance(value, dict) and not isinstance(value, ConfigState):
            value = ConfigState(value)
        self.__setitem__(k, value)


class Config(object):
    def __init__(self, fields):
        self.value = ConfigState()
        self.field_map = {}
        self.fields = []
        self.load_funcs = []
        for k, field in fields.items():
            self.add(k, field)

    def __call__(self, value, state=None):
        unknown = set(value.keys()) - set(self.field_map.keys())
        if unknown:
            raise TypeError("Unknown fields: %s" % ", ".join(unknown))

        self.value.clear()
        for field in self.fields:
            key = field.key
            self.value[key] = field(value.get(key))
        return self.value

    def add(self, k, obj):
        if k in self.field_map:
            if isinstance(obj, dict):
                self.field_map[k].update(obj)
                return

        if isinstance(obj, list):
            obj = ConfigList(obj[0])
            field = Field(k, obj, value=obj.value)
        elif isinstance(obj, dict):
            obj = Config(obj)
            field = Field(k, obj, value=obj.value)
        else:
            field = Field.create(k, obj)
        
        self.fields.append(field)
        self.field_map[field.key] = field
        return field.value

    def add_group(self, k, fields):
        obj = ConfigGroup(fields)
        field = Field(k, obj, value=obj.value)
        return self.add(k, field)

    def follow(self, *path):
        node = self
        for p in path:
            node = node.field_map[p]
        return node

    def accept(self, *names):
        for name in names:
            self.add(name, dict)

    def load(self, path):
        result = self( yaml.load(contents_of_path(path)) )
        for fn in self.load_funcs:
            fn()
        return result
    
    def on_load(self, fn):
        self.load_funcs.append(fn)
        return fn

    def update(self, fields):
        for k, v in obj:
            self.add(k, v)


class ConfigList(object):
    def __init__(self, callable):
        self.callable = callable
        self.value = []

    def __call__(self, value):
        del self.value[:]
        if value:
            self.value.extend(self.callable(x) for x in value)
        return self.value


class ConfigGroup(object):
    name_key = 'key'
    extends_key = 'extends'
    accepts_none = True         # Accepts None when being called on a value

    def __init__(self, fields):
        self.fields = dict( fields )
        self.fields[self.name_key] = unicode
        self.fields[self.extends_key] = unicode
        self.value = ConfigState()

    def __call__(self, value):
        value = dict(value or {})

        self.value.clear()
        for k, v in value.items():
            v[self.name_key] = k
            if self.extends_key in v:
                extend(v, value[v[self.extends_key]])
            config = Config(self.fields)
            self.value[k] = config(v)
        return self.value

    def update(self, fields):
        self.fields.update(fields)


def extend(dct, prototype):
    """
    Extends a dictionary dct by prototype.
    """
    for k, v in prototype.items():
        dct.setdefault(k, v)


def accepts_none(fn):
    """
    Marks a function to accept None when being called on a value.
    """
    fn.accepts_none = True      
    return fn


@accepts_none
def string_list(value):
    """
    Returns a list of strings, if the ``value`` is a string then it is split().  Also returns an empty list
    if the ``value`` is ``None``.

    >>> string_list(["apple", "banana", "cherry"])
    ["apple", "banana", "cherry"]

    >>> string_list("apple banana cherry")
    ["apple", "banana", "cherry"]

    >>> string_list(None)
    []
    """
    if value is None:
        return []
    elif isinstance(value, basestring):
        return list(value.split())
    elif hasattr(value, '__iter__'):
        return list(value)
    raise TypeError("Value is not iterable: %r" % value)


def contents_of_path(path):
    """
    Returns the contents of the file at ``path``.
    """
    #path = os.path.abspath( os.path.join(os.path.dirname(__file__), '..', path) )
    with open(path) as file:
        return file.read()


config = Config({})
