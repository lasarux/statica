#!/usr/bin/env python

__author__ = "Pedro Gracia"
__copyright__ = "Copyright 2012, Impulzia S.L."
__credits__ = ["Pedro Gracia"]
__license__ = "BSD"
__version__ = "0.7"
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

BUILD_DIR = 'build/'
IMG_EXTENSION = ['jpg', 'jpeg', 'png', 'gif']
SLOT_EMPTY = 'SLOT EMPTY - PLEASE FILL IN'

# initialize makdown object
md = markdown.Markdown(safe_mode=False, extensions=['tables', 'superscript'])

def get_cache(filename):
    if os.path.exists(filename):
        CACHE = pickle.load(filename)
    else:
        CACHE = {}

def normalize(name):
    return name.lower().replace("-", "_").replace(".", "_")

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
        
    def include(self, path, t):
        """walk throught static dirs to get files"""
        for root, dirs, files in os.walk(os.path.join(path, t)):
            for file in files:
                key_split = file.split('.')
                key = '.'.join(key_split[:-1])
                r = getattr(self, t)
                key = key.replace('-', '_').replace('.', '_')
                r[key] = '%s/%s' % (t, file) #TODO: add ../../../../ dynamicaly


class Item:
    def __init__(self, root, parent=None):
        self.parent = parent
        self.root = root
        self.children = []
        
        self.discover(root)
        
    def __unicode__(self):
        print self.root

    def add_value(self, name, value):
        setattr(self, normalize(name), value)
        
    def add_child(self, name, item):
        self.add_value(name, item)
        self.children.append(item)

    def discover(self, root):
        items = os.listdir(root)
        for item in items:            
            path = os.path.join(root, item)
            if os.path.isdir(path):
                self.add_child(item, Item(path, self))
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
        # here we use the current page defined into main loop
        url = '%s/%s' % (PAGE.pre, self._url)
        return url
        
    def title(self):
        if self._title.has_key(PAGE.lang):
            res = self._title[PAGE.lang]
        else:
            res = ''
        return res

    def alt(self):
        if self._alt.has_key(PAGE.lang):
            res = self._alt[PAGE.lang]
        else:
            res = ''
        return res
        
    def description(self):
        if self._description.has_key(PAGE.lang):
            res = self._description[PAGE.lang]
        else:
            res = ''
        return res

    def read_catalog(self, dirname):
        """read translated info about the image from language catalogs"""
        for lang in LANGUAGES:
            try:
                lines = codecs.open('%s/catalog.%s' % (dirname, lang[0]), 'r', 'utf-8').readlines()
            except IOError:
                break
            for line in lines:
                if line.startswith(self.name):
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
        return '<img src="%s" title="%s" alt="%s" />' % (self.url(), self.title(), self.alt())

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
    """Basic Page object"""
    def __init__(self, filename):
        self.filename = filename
        self.lines = codecs.open(filename, "r", "utf-8").readlines()
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
                data = line.split(":")
                # end of header
                if len(data) == 1:
                    is_header = False
                    self.md += line + ' '
                    continue
                # add attribute to this object
                attr = data[0]
                data = line[len(attr)+1:].strip()
                if data != 'main':
                    try:
                        # to eval a string is cool! (maths are welcome)
                        value = eval(data)
                    except:
                        value = data
                else:
                    value = data
                setattr(self, attr, value)
        self.get_html() 


def dyn(items, page):
    items_pre = {}
    pre = page.pre
    for k,v in items.items():
        items_pre[k] = '%s/%s' % (pre, v)
    return items_pre


def main(project_path):
    # main function
    #CACHE = get_cache('.cache')
    
    # initial constants
    PROJECT_DIR = project_path
    RESOURCES_DIR = os.path.join(PROJECT_DIR, 'resources/')
    RESOURCES_IMG_DIR = os.path.join(RESOURCES_DIR, 'img')
    STATIC_DIR = os.path.join(PROJECT_DIR, 'static/')
    TEMPLATES_DIR = os.path.join(PROJECT_DIR, 'templates/')
    TEMPLATE_DEFAULT = 'main.html'
    #DEFAULT_LANGUAGE = 'ca'
    #templates = {}

    exec("import %s as s" % PROJECT_DIR)
    globals()['LANGUAGES'] = s.LANGUAGES

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
        print "Warning! There isn't information about Google services"

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
    for file in os.listdir(RESOURCES_IMG_DIR):
        ext = file.split('.')[-1]
        if ext.lower() in IMG_EXTENSION:
            res_obj.addfile(file, os.path.join(RESOURCES_IMG_DIR, file), "", "")
    
    # process page files
    pages = {} #TODO: Page class?
    for lang in s.LANGUAGES:
        pages[lang[0]] = {}
        for root, dirs, files in os.walk(os.path.join(RESOURCES_DIR, lang[0])):
            # only scan dirs with a page.md file
            if 'page.md' in files:
                m = Box(os.path.join(root, 'page.md'))
                xelements = root.split("/")[3:]
                xdir = "/".join(xelements)
                m.root = root
                #TODO: unify url and surl
                if xelements[-1] != 'index':
                    m.name  = 'index'
                    m.path = os.path.join(lang[0], xdir, '%s.html' % m.name)
                    m.dir = os.path.join(lang[0], xdir)
                    m.name  = 'index'
                    m.url = '%s/%s/%s.html' % (lang[0], xdir, m.name)
                    m.surl = '../%s/%s/%s.html' % (lang[0], xdir, m.name)
                    m.pre = '../' * (len(xelements) + 1) + 'static'
                else:
                    m.name = root.split('/')[-1]
                    m.path = os.path.join(lang[0], '%s.html' % m.name)
                    m.dir = os.path.join(lang[0])
                    m.url = '%s/%s.html' % (lang[0], m.name)
                    m.surl = '../%s/%s.html' % (lang[0], m.name)
                    m.pre = '../static'
                m.lang = lang[0]
                m.slang = lang[1]     
                pages[lang[0]][xdir] = m

    resources_img = Item(os.path.join(RESOURCES_DIR, 'img'))

    # process markdown resources for each language
    for l, p in pages.items():
        for m in p.values():
            globals()['PAGE'] = m # current page goes to global 'page' var
            t = '%s.html' % m.template #template
            for root, dirs, files in os.walk(m.root):
                boxes = {}
                for file in files:
                    #TODO: check extension (markdown, html, etc.)
                    box = Box(join(root, file))
                    key = file.split('.')[0]
                    boxes[key] = box
                
                # get each page with same name
                lang_pages = []
                for k, v in pages.items():
                    try:
                        lang_pages.append(v[m.name])
                    except KeyError:
                        print "Warning: missing info for '%s' language." % m.dir
                        
                # write output file
                boxes['current_language'] = m.lang
                boxes['builtins'] = builtins
                boxes['resource'] = res_obj
                boxes['page'] = m #TODO: better not in boxes?
                boxes['gallery'] = {}
                boxes['image'] = resources_img
                boxes['lang_pages'] = lang_pages
            
                # gallery items
                for key, value in galleries.items():
                    boxes['gallery'][key] = value 
            
                template = env.get_template('%s' % t)
                
                # dynamically build resources url
                css = dyn(res.css, m)
                js = dyn(res.js, m)
                img = dyn(res.img, m)
                ico = dyn(res.ico, m)
                
                try:
                    output_md = template.render(css=css, js=js, img=img, ico=ico, **boxes)
                except jinja2.exceptions.UndefinedError:
                    print "Warning, slot empty at %s" % m.name
                    output_md = SLOT_EMPTY
                # second pass to use template engine within markdown output
                env_md = Environment()
                env_md.filters['thumbnail'] = thumbnail
                template_md = env_md.from_string(output_md)
                
                output = template_md.render(css=css, js=js, img=img, ico=ico, **boxes)
                
                try:
                    os.makedirs(os.path.join(BUILD_DIR, m.dir))
                    print "directory %s created." % os.path.join(BUILD_DIR, m.dir)
                except:
                    pass
                codecs.open(os.path.join(BUILD_DIR, m.path), 'w', 'utf-8').write(output)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: %s path/to/project' % sys.argv[0])
    main(sys.argv[1])