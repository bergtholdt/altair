import os
import json
from itertools import chain

from jinja2 import Environment, FileSystemLoader, filters

filters.FILTERS['repr'] = repr

TYPE_MAP = {'oneOf': 'Union',
            "array": "List",
            "boolean": "Bool",
            "number": "CFloat",
            "string": "Unicode",
            "object": "Any",
            }


CLASS_ALIASES = {
    'PositionChannel': {'base': 'PositionChannelDef', 'type': 'channel'},
    'ChannelWithLegend': {'base': 'ChannelDefWithLegend', 'type': 'channel'},
    'Field': {'base': 'FieldDef', 'type': 'channel'},
    'OrderChannel': {'base': 'OrderChannelDef', 'type': 'channel'}
    }


def getpath(*args):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *args))


class SchemaProperty(object):
    """Class Wrapper for a property in a VegaLite Schema

    This class exposes methods used in the templating.
    """
    def __init__(self, schema, name, top):
        self.name = name
        self.schema = schema
        self.top = top

        self.properties = {k: SchemaProperty(v, k, self.top)
                           for k, v in self.schema.get('properties',
                                                       {}).items()}

    @property
    def subtypes(self):
        trait = self.trait_name
        if trait == 'Union':
            return [self.__class__(s, '', self.top)
                    for s in self.schema['oneOf']]
        elif trait == 'List':
            return [self.__class__(self.schema['items'], '', self.top)]
        else:
            return []

    @property
    def type(self):
        if '$ref' in self.schema:
            return '$ref'
        elif 'oneOf' in self.schema:
            return 'oneOf'
        else:
            return self.schema.get('type', '')

    @property
    def trait_name(self):
        if self.refname:
            trait = self.top.definitions[self.refname].trait_name
            if trait == 'Any':
                return 'Instance'
            else:
                return self.refname
        else:
            return TYPE_MAP.get(self.type, "Any")

    @property
    def trait_descr(self):
        trait = self.trait_name
        if trait == 'Instance':
            return self.refname
        elif self.subtypes:
            return '{0}({1})'.format(trait, ', '.join(t.trait_descr
                                                      for t in self.subtypes))
        else:
            return trait

    @property
    def trait_fulldef(self):
        trait = self.trait_name
        kwds = "allow_none=True, default_value=None"
        if 'minimum' in self.schema:
            kwds += ', min={0}'.format(self.schema['minimum'])
        if 'maximum' in self.schema:
            kwds += ', max={0}'.format(self.schema['maximum'])
        if self.description:
            kwds += ', help="""{0}"""'.format(self.short_description)

        if trait == 'Union':
            return ('T.Union([{0}])'
                    ''.format(', '.join(t.trait_fulldef
                                        for t in self.subtypes)))
        elif trait == 'List':
            return 'T.List({0}, {1})'.format(*(t.trait_fulldef
                                               for t in self.subtypes), kwds)
        elif trait == 'Instance':
            return 'T.Instance({0}, {1})'.format(self.refname, kwds)
        elif trait == self.refname:
            return '{0}({1})'.format(self.refname, kwds)
        else:
            return 'T.{0}({1})'.format(trait, kwds)

    @property
    def trait_or_subtrait(self):
        if self.refname is not None:
            return self.refname
        elif self.trait_name in ['Union', 'List']:
            for t in self.subtypes:
                if t.trait_or_subtrait is not None:
                    return t.trait_or_subtrait
            else:
                return None
        else:
            return None

    @property
    def description(self):
        return self.schema.get('description', '')

    @property
    def short_description(self):
        if self.description:
            return self.description.split('(e.g.')[0].split('.')[0] + '.'
        else:
            return ''

    @property
    def long_description(self):
        return self.description

    @property
    def refname(self):
        if '$ref' in self.schema:
            return self.schema['$ref'].split('/')[-1]
        else:
            return None

    @property
    def imports(self):
        def gen_imports():
            if self.refname:
                yield self.refname
            for t in self.subtypes:
                yield from t.imports
            for v in self.properties.values():
                yield from v.imports
        return sorted(set(gen_imports()))

    @property
    def attributes(self):
        return [v for k, v in sorted(self.properties.items())]

    @property
    def enum(self):
        return self.schema.get('enum', [])


class VegaLiteSchema(SchemaProperty):
    """
    This is a wrapper for the vegalite JSON schema that provides tools to
    export Python wrappers.
    """
    def __init__(self, schema_file=None):
        if schema_file is None:
            schema_file = getpath('..', 'altair', 'schema',
                                  'vega-lite-schema.json')
        with open(schema_file) as f:
            schema = json.load(f)

        self.definitions = {k: SchemaProperty(v, k, self)
                            for k, v in schema['definitions'].items()}

        template_path = getpath('templates')
        self.templates = Environment(loader=FileSystemLoader(template_path))

        super(VegaLiteSchema, self).__init__(schema, 'VegaLiteSchema', self)

    def write_interface(self, path=None):
        # Make sure the path is valid
        if path is None:
            path = getpath('..', 'altair', 'schema', '_interface')
        if not os.path.exists(path):
            os.makedirs(path)

        print("Writing code to {0}".format(path))

        # Write Init File
        template = self.templates.get_template('__init__.py.tpl')
        header = "Auto-generated Python wrappers for Vega-Lite Schema"
        print(" - Writing __init__.py")
        objects = [dict(module=obj.lower(), classname=obj)
                   for obj in sorted(self.definitions)]
        with open(os.path.join(path, '__init__.py'), 'w') as f:
            f.write(template.render(objects=objects,
                                    header=header))

        # Write Class Definition files
        templates = {'string': self.templates.get_template('enum.py.tpl'),
                     'object': self.templates.get_template('object.py.tpl')}
        for key, prop in sorted(self.definitions.items()):
            if prop.type not in templates:
                raise ValueError("No template for type={0}".format(prop.type))
            outfile = os.path.join(path, '{0}.py'.format(key.lower()))
            print(" - Writing {0}".format(os.path.basename(outfile)))
            with open(outfile, 'w') as f:
                f.write(templates[prop.type].render(cls=prop))

    def write_interface_tests(self, path=None):
        # Make sure the path is valid
        if path is None:
            path = getpath('..', 'altair', 'schema', '_interface', 'tests')
        if not os.path.exists(path):
            os.makedirs(path)

        print("Writing tests to {0}".format(path))

        # Write test Init File
        template = self.templates.get_template('__init__.py.tpl')
        header = 'Auto-generated tests for Vega-Lite Schema wrappers'
        print(" - Writing __init__.py")
        with open(os.path.join(path, '__init__.py'), 'w') as f:
            f.write(template.render(objects=[], header=header))

        # Write test file
        template = self.templates.get_template('test_instantiations.py.tpl')
        classes = [prop for key, prop in sorted(self.definitions.items())]
        print(" - Writing test_instantiations.py")
        with open(os.path.join(path, 'test_instantiations.py'), 'w') as f:
            f.write(template.render(classes=classes))

    def write_wrappers(self, path=None):
        # make sure the path is valid
        if path is None:
            path = getpath('..', 'altair', 'schema', '_wrappers')
        if not os.path.exists(path):
            os.makedirs(path)

        print("Writing wrappers to {0}".format(path))

        # get all channel class aliases
        classes = sorted([(k, v['base'])
                          for k, v in CLASS_ALIASES.items()
                          if v['type'] == 'channel'])

        # write the class definition files
        template = self.templates.get_template('channel_defs.py.tpl')
        for cls, basename in sorted(classes):
            base = self.definitions[basename]
            filename = os.path.join(path, '{0}.py'.format(cls.lower()))
            print("- Writing {0}".format(filename))
            with open(filename, 'w') as f:
                f.write(template.render(cls=cls, base=base))

        # All Encoding attributes get their own class name:
        encoding = self.definitions['Encoding']
        channels = [{'name': attr.name.title(),
                     'base': attr.trait_or_subtrait.replace('Def', '')}
                    for attr in encoding.attributes]
        imports = sorted(set(c['base'] for c in channels))

        # write the encoding channel wrapper files
        template = self.templates.get_template('encoding_defs.py.tpl')
        filename = os.path.join(path, 'encoding_defs.py')
        print("- Writing {0}".format(filename))
        with open(filename, 'w') as f:
            f.write(template.render(imports=imports, channels=channels))

        # write the init file
        template = self.templates.get_template('__init__.py.tpl')
        header = 'Wrappers for low-level schema objects'
        objects = [dict(module=cls[0].lower(), classname=cls[0])
                   for cls in classes]
        objects.extend([dict(module='encoding_defs', classname=c['name'])
                        for c in channels])
        objects.append(dict(module='encoding_defs', classname='CHANNEL_CLASSES'))
        objects.append(dict(module='encoding_defs', classname='CHANNEL_NAMES'))
        print(" - Writing __init__.py")
        with open(os.path.join(path, '__init__.py'), 'w') as f:
            f.write(template.render(header=header, objects=objects))


if __name__ == '__main__':
    schema = VegaLiteSchema()
    schema.write_interface()
    schema.write_interface_tests()
    schema.write_wrappers()
