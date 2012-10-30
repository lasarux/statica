#!/usr/bin/env python

__author__ = "Pedro Gracia"
__copyright__ = "Copyright 2012, Impulzia S.L."
__credits__ = ["Pedro Gracia"]
__license__ = "BSD"
__version__ = "0.9"
__maintainer__ = "Pedro Gracia"
__email__ = "pedro.gracia@impulzia.com"
__status__ = "Development"

import os
import sys
import re
import codecs
import pickle
import md5
from os.path import join, getsize
import shutil
import markdown
from jinja2 import Environment, FileSystemLoader, Template
from jinja2 import evalcontextfilter, contextfilter, Markup, escape
from PIL import Image, ImageOps
import jinja2.exceptions 

IMG_EXTENSION = ['jpg', 'jpeg', 'png', 'gif']
SLOT_EMPTY = 'SLOT EMPTY - PLEASE FILL IN'

# initialize makdown object
md = markdown.Markdown(safe_mode=False, extensions=['tables', 'superscript'])

def get_cache(filename):
    if os.path.exists(filename):
        CACHE = pickle.load(filename)
    else:
        CACHE = {}

def clean_line(line):
    """clean data line before process it"""
    if line.endswith('/n'):
        line = line[:-1]
    return line

def normalize(name):
    """convert name with spaces, minus or dots to name with underscores"""
    return name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')

def value_or_empty(value):
    # PAGE is a global variable
    if value.has_key(PAGE.lang):
        res = value[PAGE.lang]
    else:
        res = ''
    return res

@contextfilter
def thumbnail(context, value, width, height,style=""):
    """thumbnail filter for jinja2"""
    thumb = ImageOps.fit(value.image, (width, height), Image.ANTIALIAS)
    path = os.path.join(BUILD_DIR, 'static', 'img', 'thumbnail', value.filename)
    url = '%s/img/thumbnail/%s' % (context['page'].pre, value.filename)
    
    try:
        os.makedirs(os.path.join(BUILD_DIR, 'static', 'img', 'thumbnail'))
    except:
        pass
    thumb.save(path)
    
    if style:
        result = '<img class="%s" src="%s" title="%s" alt="%s"/>' % (style, url, value.title(), value.alt())
        result += '<p><strong>%s</strong></p>' % value.description()
    else:
        result = '<img src="%s" title="%s" alt="%s"/>' % (url, value.title(), value.alt())

    if context.eval_ctx.autoescape:
            result = Markup(result)
    return result

class Static:
    #TODO: use Item instead
    """Basic Object for css, js and images resources"""
    def __init__(self, path):
        self.css = {}
        self.js = {}
        self.img = {}
        self.ico = {}
        self.include(path, 'css')
        self.include(path, 'js')
        self.include(path, 'img')
        self.include(path, 'ico')
        
    def include(self, path, d):
        """walk throught static dirs to get files"""
        for root, dirs, files in os.walk(os.path.join(path, d)):
            for file in files:
                key_split = file.split('.')
                key = '.'.join(key_split[:-1])
                r = getattr(self, d)
                key = key.replace('-', '_').replace('.', '_')
                r[key] = '%s/%s' % (d, file)


class Item:
    def __init__(self, root, lang=None, parent=None, only_children=False, level=0):
        self.parent = parent
        self.root = root
        self.only_children = only_children
        self.type = None
        self._index = []
        self.children = []
        self.level = level
        self.lang = lang
        self._url = '/'.join(root.split('/')[-level:]) + '/index.html' # FIXME: split('/') doesn't work in windows
        
        self.parse_page()
        self.discover()

        
    def url(self):
        if 'PAGE' in globals():
            r = '../' * PAGE.level + self._url
        else:
            r = 'Error: Global PAGE object doesn\'t defined'
        return r

    def add_value(self, name, item):
        if not self.only_children:
            setattr(self, normalize(name), item)
        
    def add_child(self, name, item):
        self.add_value(name, item)
        item.parent = self # add parent (self) to item
        l = len(self._index)
        if hasattr(item, 'id'):
            id = item.id
        else:
            print "Item without id"
            id = 'zzzz'
        if l > 0:
            for i in range(len(self._index)):
                if id <= self._index[i]:
                    self._index.insert(i, id)
                    self.children.insert(i, item)
                    id = 'done'
                    break
            if id != 'done':
                self._index.append(id)
                self.children.append(item)
        else:
            self._index.append(id)
            self.children.append(item)

    def parse_page(self):
        # TODO: use item for images too?
        if os.path.exists('%s/page.md' % self.root):
            self.type = 'page'
            self.box = Box('%s/page.md' % self.root)
            lines = codecs.open('%s/page.md' % self.root, 'r', 'utf-8').readlines()
            for line in lines:
                data = clean_line(line).split(':')
                key = data[0]
                values = ''.join(data[1:])[:-1] # drop '\n'
                if values.strip == '':
                    break
                else:
                    value = values
                    #try:
                        # to eval a string is cool! (maths are welcome)
                    #    value = eval(values)
                    #except:
                    #    value = values
                    setattr(self, key, value)
        else:
            self.type = 'dir'

    def discover(self):
        items = os.listdir(self.root)
        for item in items:            
            path = os.path.join(self.root, item)
            if os.path.isdir(path):
                self.add_child(item, Item(path, parent=self, level=self.level + 1))
            else:
                ext = item.split('.')[-1]
                if ext.lower() in IMG_EXTENSION:
                    name = item[:-(len(ext)+1)]
                    self.add_value(name, Img(item, path))
                else:
                    self.add_value(item, path)
        return self


class Img:
    def __init__(self, filename, path):
        self.filename = filename
        self.name = '.'.join(filename.split('.')[:-1]).lower()
        self.image = Image.open(path)
        self._title = {}
        self._alt = {}
        self._description = {}
        self._url = 'img/%s' % self.filename
        self.build_path = os.path.join(BUILD_DIR, 'static', 'img', self.filename)
        dirname = os.path.dirname(path)
        
        self.read_catalog(dirname)
        self.save()
    
    def url(self):
        # here we use the current page defined into main loop (it's a global variable)
        url = '%s/%s' % (PAGE.pre, self._url)
        return url
        
    def title(self):
        return value_or_empty(self._title)

    def alt(self):
        return value_or_empty(self._alt)
        
    def description(self):
        return value_or_empty(self._description)

    def read_catalog(self, dirname):
        """read translated info about the image from language catalogs"""
        for lang in LANGUAGES:
            try:
                lines = codecs.open('%s/catalog.%s' % (dirname, lang[0]), 'r', 'utf-8').readlines()
            except IOError:
                break
            for line in lines:
                if line.startswith('%s:' % self.name):
                    values = ''.join(line.split(':')[1:])
                    title, alt, description = values.split(',')
                    self._title[lang[0]] = title.replace(';', ',')
                    self._alt[lang[0]] = alt.replace(';', ',')
                    self._description[lang[0]] = description.replace(';', ',')
                    break

    def save(self):
        # save to build/static/img
        try:
            # TODO: use dddrid
            os.makedirs(os.path.join(BUILD_DIR, 'static', 'img'))
        except:
            pass
        self.image.save(self.build_path)

    def __repr__(self):
            return self
        #return '<img src="%s" title="%s" alt="%s" />' % (self.url(), self.title(), self.alt())

class Resource:
    #TODO: review this and use Item
    def __init__(self):
        pass
    
    def addfile(self, filename, path, title, alt):
        # TODO: autodiscover type
        name = '_'.join(filename.lower().split('.')[:-1])
        img = Img(filename, path)
        setattr(self, name, img)


class Gallery:
    """Image container"""
    def __init__(self, root, dirs, files):
        self.images = []
        for file in files:
            ext = file.split('.')[-1]
            if ext.lower() in IMG_EXTENSION:
                key = file[:-(len(ext)+1)]
                img = Img(file, os.path.join(root, file))
                self.images.append(img)
                    
    def parse_catalog(self):
        pass
    

class Box:
    """Basic Box object"""
    def __init__(self, filename):
        self.filename = filename
        try:
            self.lines = codecs.open(filename, "r", "utf-8").readlines()
        except UnicodeDecodeError:
            print 'Please, use UTF-8 in %s' % filename
            sys.exit(1) 
        self.md = ""
        self.html = ""
        
        self.parse()

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
                data = clean_line(line).split(":")
                if self.filename == 'expandyourmind/resources/es/index/page.md':
                    print "---", self.filename, data
                    t = True
                else:
                    t = False
                # end of header
                if len(data) == 1:
                    is_header = False
                    self.md += line + ' '
                    continue
                # add attribute to this object
                attr = data[0]
                data = line[len(attr)+1:].strip()
                value = data
                # TODO: use symbol '#' to mark expresions to evaluate
                #try:
                    # to eval a string is cool! (maths are welcome)
                    #value = eval(data)
                #except:
                #value = data
                #    if t: print "+++", attr, value
                setattr(self, attr, value)
        self.get_html() 


def dyn(items):
    items_pre = {}
    pre = '../' * (PAGE.level +1) #page.pre
    for k,v in items.items():
        items_pre[k] = '%s/static/%s' % (pre[:-1], v)
    return items_pre


# TEST: to show pages
def walk(item, items={}):
    items = items
    for i in item.children:
        items[i.id] = i
        if i.children:
            walk(i, items)
    return items

def main(project_path):
    # main function
    #CACHE = get_cache('.cache')
    
    # initial constants
    PROJECT_DIR = project_path
    BUILD_DIR = os.path.join(PROJECT_DIR, 'build')
    RESOURCES_DIR = os.path.join(PROJECT_DIR, 'resources')
    RESOURCES_IMG_DIR = os.path.join(RESOURCES_DIR, 'img')
    STATIC_DIR = os.path.join(PROJECT_DIR, 'static')
    TEMPLATES_DIR = os.path.join(PROJECT_DIR, 'templates')
    TEMPLATE_DEFAULT = 'main.html'
    #DEFAULT_LANGUAGE = 'ca'
    #templates = {}

    exec("import %s as s" % PROJECT_DIR)
    globals()['LANGUAGES'] = s.LANGUAGES
    globals()['BUILD_DIR'] = BUILD_DIR

    google_analytics = Template("""<script type="text/javascript">

        var _gaq = _gaq || [];
        _gaq.push(['_setAccount', '{{ analytics_id }}']);
        _gaq.push(['_trackPageview']);

        (function() {
          var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
          ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
          var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
        })();

      </script>""")
  
    google_maps = Template("""<script src="https://maps.googleapis.com/maps/api/js?sensor=false"></script>
    <script>
      function initialize() {
        var myLatlng = new google.maps.LatLng({{ lat }}, {{ lon }});
        var mapOptions = {
          zoom: {{ zoom }},
          center: myLatlng,
          mapTypeId: google.maps.MapTypeId.ROADMAP
        }
        var map = new google.maps.Map(document.getElementById('map_canvas'), mapOptions);

        var marker = new google.maps.Marker({
            position: myLatlng,
            map: map,
            title: '{{ title }}'
        });
      }
    </script>""")
    
    # initialize jinja2 objects
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters['thumbnail'] = thumbnail
    #template = env.get_template(TEMPLATE_DEFAULT)
    res = Static(STATIC_DIR)
    builtins = {}
    
    # built-ins
    try:
        builtins['google_analytics'] = google_analytics.render(analytics_id=s.analytics_id)
        builtins['google_maps'] = google_maps.render(zoom=s.map_zoom, lat=s.map_lat, lon=s.map_lon, title=s.map_title)
    except:
        print "Warning! There aren't information to setup Google services."

    # copy static/ to build/static
    try:
        shutil.rmtree(os.path.join(BUILD_DIR, 'static/'))
    except:
        pass

    shutil.copytree(STATIC_DIR, os.path.join(BUILD_DIR, 'static/'))
    
    # process image galleries
    # TODO: remove this and use Item
    galleries = {}
    for dir in os.listdir(RESOURCES_IMG_DIR):
        for root, dirs, files in os.walk(os.path.join(RESOURCES_IMG_DIR, dir)):
            galleries[dir] = Gallery(root, dirs, files)
    
    # process images
    # TODO: remove this and use Item
    res_obj = Resource()
    
    # process page files
    pages = {} #TODO: Page class?
    menu = {}
    for lang in s.LANGUAGES:
        #TODO: join menus and pages ??
        menu[lang[0]] = Item(os.path.join(RESOURCES_DIR, lang[0]), lang=lang[0], level=0)
        pages[lang[0]] = walk(Item(os.path.join(RESOURCES_DIR, lang[0]), lang=lang[0], level=0))

    resources_img = Item(os.path.join(RESOURCES_DIR, 'img'))

    for lang in s.LANGUAGES:
        for n, m in pages[lang[0]].items():
            
            globals()['PAGE'] = m # current page goes to global 'page' var
            try:
                t = '%s.html' % m.template #template
            except AttributeError:
                print ">>>", n
                print "Please, define a template for page %s/%s." % (lang[0], m.id)
                t = '%s.html' % s.DEFAULT_TEMPLATE
            for root, dirs, files in os.walk(m.root):
                boxes = {}
                for file in files:
                    #TODO: check extension (markdown, html, etc.)
                    #process files except hiddens
                    if not file.startswith('.'):
                        box = Box(join(root, file))
                        key = file.split('.')[0]
                        boxes[key] = box
                
                # get each page with same name
                #lang_pages = []
                #for k, v in pages.items():
                #    try:
                #        lang_pages.append(v[m.title])
                #    except KeyError:
                #        print "Warning: missing info for '%s' language." % m.dir
                
                lang_pages = []
                for l in s.LANGUAGES:
                    try:
                        lang_pages.append(pages[l[0]][m.id])
                    except KeyError:
                        print "Warning: missing info for '%s' language." % l
                       
                # write output file
                boxes['current_language'] = m.lang
                boxes['builtins'] = builtins
                boxes['resource'] = res_obj
                boxes['page'] = m #TODO: better not in boxes?
                boxes['gallery'] = {}
                boxes['image'] = resources_img
                boxes['lang_pages'] = lang_pages
                
                menu_lang = menu[lang[0]].children
                
                # gallery items
                for key, value in galleries.items():
                    boxes['gallery'][key] = value 
            
                template = env.get_template('%s' % t)
                
                # dynamically build resources url
                css = dyn(res.css)
                js = dyn(res.js)
                img = dyn(res.img)
                ico = dyn(res.ico)
                
                try:
                    output_md = template.render(css=css, js=js, img=img, ico=ico, menu=menu_lang, **boxes)
                except jinja2.exceptions.UndefinedError:
                    print "Warning, slot empty at %s" % m.name
                    output_md = SLOT_EMPTY
                # second pass to use template engine within markdown output
                env_md = Environment()
                env_md.filters['thumbnail'] = thumbnail
                template_md = env_md.from_string(output_md)
                
                output = template_md.render(css=css, js=js, img=img, ico=ico, menu=menu_lang, **boxes)
                
                try:
                    os.makedirs(os.path.join(BUILD_DIR, os.path.join(*m.root.split('/')[-m.level-1:])))
                    print "directory %s created." % os.path.join(BUILD_DIR, l[0], os.path.join(m.root.split('/')[-m.level-1:]))
                except:
                    pass
                codecs.open(os.path.join(BUILD_DIR, l[0], os.path.join(*m.root.split('/')[-m.level:]), 'index.html'), 'w', 'utf-8').write(output)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: %s path/to/project' % sys.argv[0])
        
    project = sys.argv[1].endswith('/') and sys.argv[1][:-1] or sys.argv[1] #nice line!!! :-)
    main(project)
