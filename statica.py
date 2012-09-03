#!/usr/bin/env python

__author__ = "Pedro Gracia"
__copyright__ = "Copyright 2012, Impulzia S.L."
__credits__ = ["Pedro Gracia"]
__license__ = "BSD"
__version__ = "0.2"
__maintainer__ = "Pedro Gracia"
__email__ = "pedro.gracia@impulzia.com"
__status__ = "Development"

import os
import codecs
from os.path import join, getsize
import shutil
import markdown
from jinja2 import Environment, FileSystemLoader


# initial constants
RESOURCES_DIR = 'resources/'
TEMPLATES_DIR = 'templates/'
TEMPLATE_DEFAULT = 'main.html'
BUILD_DIR = 'build/'
LANGUAGES = ['ca', 'es']
#DEFAULT_LANGUAGE = 'ca'

# initialize makdown object
md = markdown.Markdown(safe_mode=False, extensions=['tables', 'superscript'])
# initialize jinja2 objects
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
template = env.get_template(TEMPLATE_DEFAULT)

class Box:
    """Basic Page object"""
    def __init__(self, filename):
        self.filename = filename
        self.lines = codecs.open(filename, "r", "utf-8").readlines()
        self.md = ""
        self.html = ""

    def __str__(self):
        return self.html or self.md or "Empty, please fill it"

    def get_html(self):
        self.html = md.convert(self.md.strip())
        
        # insert newline after header tags
        for i in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.html = self.html.replace('</%s>' % i, '</%s><br>' % i)
        
        # add bootstrap styles to tables
        self.html = self.html.replace('<table>', '<table class="table table-striped">')

    def parse(self):
        """Parse a page object in order to set attributes from its header"""
        # read attributes until empty line or not key-value pair
        is_header = True
        for line in self.lines:
            # add line to markdown if it isn't header
            if not is_header:
                self.md += line + ' '
            else:
                # empty line to split header from body
                if is_header and line == "":
                    self.md += '\n'
                    continue
                data = line.split(":")
                # end of header
                if len(data) == 1:
                    is_header = False
                    self.md += line + ' '
                    continue
                # add attribute to this object
                attr = data[0]
                try:
                    # to eval a string is cool! (maths are welcome)
                    value = eval(line[len(attr)+1:].strip())
                except:
                    value = line[len(attr)+1:].strip()
                setattr(self, attr, value)
        self.get_html() 
        return self
        

def main():
    for root, dirs, files in os.walk(RESOURCES_DIR):
        if root == RESOURCES_DIR and 'config' in files:
            pass #TODO: parse config file
        
        if files:
            # TODO: this is an ugly hack - remove it!
            continue
        # process resources for each languages
        for lang in dirs:
            for root, dirs, files in os.walk(os.path.join(RESOURCES_DIR, lang)):
                boxes = {}
                for file in files:
                    print file
                    #TODO: check extension (markdown, html, etc.)
                    box = Box(join(root, file))
                    data = file.split('.')[0]
                    boxes[data] = box.parse()

                # write output file
                boxes['current_language'] = lang
                output = template.render(**boxes)
                codecs.open(os.path.join(BUILD_DIR, lang, 'index.html'), 'w', 'utf-8').write(output)
    
    shutil.copytree('static/', os.path.join(BUILD_DIR, 'static/'))

if __name__ == '__main__':
    main()