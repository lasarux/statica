#!/usr/bin/env python

__author__ = "Pedro Gracia"
__copyright__ = "Copyright 2012, Impulzia S.L."
__credits__ = ["Pedro Gracia"]
__license__ = "BSD"
__version__ = "0.17"
__maintainer__ = "Pedro Gracia"
__email__ = "pedro.gracia@impulzia.com"
__status__ = "Development"

import os
import sys
import re
import codecs
import pickle
import md5
from datetime import date
from os.path import join, getsize

import yaml
import shutil
import markdown

from PIL import Image, ImageOps
import jinja2.exceptions
from jinja2 import Environment, FileSystemLoader, Template
from jinja2 import evalcontextfilter, contextfilter, Markup, escape

#IMG_EXTENSION = ['jpg', 'jpeg', 'png', 'gif']
STATIC_EXTENSIONS= {
    'image': ['jpg', 'jpeg', 'png', 'gif'],
    'icon': ['ico'],
    'javascript': ['js'],
    'style': ['css'], 
    'media': ['mp3', 'mp4', 'ogg', 'ogv'],
    'document': ['pdf', 'doc', 'xls', 'odt', 'ods', 'txt', 'csv', 'md'],
    'archive': ['zip', 'rar', 'gz', 'tgz', 'bz'],
    'installers': ['deb', 'rpm', 'apk', 'dmg', 'exe', 'msi'],
    'others': ['xcf', 'svg']
}
SLOT_EMPTY = 'SLOT EMPTY - PLEASE FILL IN'
PAGE = None
LANGUAGES = None
GALLERY = {}
BUILD_DIR = None
ENV = None

# initialize makdown object
md = markdown.Markdown(safe_mode=False, extensions=['tables']) #, 'superscript'])

def clean_line(line):
    """clean data line before process it"""
    if line.endswith('/n'):
        line = line[:-1]
    return line

def get_type(filename):
    """get type for a filename with its extension"""
    
    #forbidden types
    if filename.startswith('.') or filename.startswith('catalog.'):
        return 'forbidden', filename
    
    ext = filename.split('.')[-1]
    t = None
    basename = None
    # search type of extension
    for key, values in STATIC_EXTENSIONS.items():
        if ext.lower() in values:
            t = key
            basename = filename[:-(len(ext)+1)]
            break
    return t, basename

def normalize(name):
    """convert name with spaces, minus or dots to name with underscores"""
    return name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')

# TODO: remove this
def value_or_empty(value):
    # PAGE is a global variable
    if value.has_key(PAGE.lang):
        res = value[PAGE.lang]
    else:
        res = ''
    return res

@contextfilter
def thumbnail(context, object, width, height, style=""):
    """thumbnail filter for jinja2"""
    thumb = ImageOps.fit(object.image, (width, height), Image.ANTIALIAS)
    new_filename = '%s_%s' % (PAGE.lang, object.filename) #TODO: use md5sum
    path = os.path.join(BUILD_DIR, 'static', 'img', 'thumbnail', new_filename)
    url = '%s/static/img/thumbnail/%s' % ('../' * (PAGE.level + 1), new_filename)

    try:
        os.makedirs(os.path.join(BUILD_DIR, 'static', 'img', 'thumbnail'))
    except:
        pass
    thumb.save(path)

    if style:
        result = '<img class="%s" src="%s" title="%s" alt="%s" width="%i" height="%i" />' % (style, url, object.title, object.alt, width, height)
        #result += '<p><strong>%s</strong></p>' % value.description() #FIXME: description goes out of here
    else:
        result = '<img src="%s" title="%s" alt="%s" width="%i" height="%i" />' % (url, object.title, object.alt, width, height)

    if context.eval_ctx.autoescape:
        result = Markup(result)
    return result

@contextfilter
def template(context, object, template):
    """template filter for jinja2"""
    template = ENV.get_template(template)
    result = template.render(page=PAGE, object=object)
    if context.eval_ctx.autoescape:
        result = Markup(result)
    return result
    

class Static:
    """Basic Object for css, js and images resources"""
    def __init__(self, path, type):
        self.path = path
        self.type = type
        self._url = '/'.join(path.split(os.path.sep)[2:])

    def __repr__(self):
        if self.type == 'style':
            res = '<link href="%s" rel="stylesheet" type="text/css">' % self.url()
        elif self.type == 'icon':
            res = '<link rel="shortcut icon" href="%s">' % self.url()
        elif self.type == 'javascript':
            res = '<script src="%s"></script>' % self.url()
        else:
            res = self.url()
        return res

    def url(self):
        """returns a valid relative url"""
        global PAGE
        res = '../' * (PAGE.level + 1) + self._url
        return res
        


class Item:
    """Item has become the most important class into statica. It have got a tree structure"""
    def __init__(self, root, lang=None, parent=None, only_children=False, level=0):
        self.parent = parent
        self.root = root
        self.only_children = only_children
        self.type = None
        self._index = []
        self.children = []
        self.level = level
        self.lang = lang
        self._url = '/'.join(root.split(os.path.sep)[-level:])

        #check if root exists
        if os.path.exists(root):
            self.parse_page()
            self.discover()
        else:
            print 'Warning: %s doesn\'t exists.' % root


    def __unicode__(self):
        return self.url()

    def url(self):
        global PAGE
        if self.type == 'page':
            res = '../' * PAGE.level + self._url + '/index.html'
        #TODO: fix this
        elif self.type in ['javascript', 'style']:
            res = "TEST"
        else:
            res = self._url
        return res
        
    def __repr__(self):
        #TODO: remove this check if it's possible
        if hasattr('GLOBALS', 'PAGE'):
            return self.url()
        else:
            return '<%s: %s - %s>' % (self.type, self.root, self.lang)

    def lang_url(self):
        """returns page url with lang"""
        global PAGE
        result = '../' * (PAGE.level + 1) + '%s/%s' % (self.lang, self._url)
        return result

    def add_value(self, name, item):
        """add an attribute (name) with a value (item)"""
        if not self.only_children:
            setattr(self, normalize(name), item)

    def add_child(self, name, item):
        """help to build an ordered menu directly from directory structure"""
        self.add_value(name, item)
        item.parent = self # add parent (self) to item
        l = len(self._index)
        if hasattr(item, 'id'):
            id = item.id
        elif self.type == 'page':
            print "Item without id:  %s" % item
            id = 'zzzz'
        else:
            id = None
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
        """read params from page.md -> key: value"""
        # TODO: use item for images too?
        if os.path.exists('%s/page.md' % self.root):
            self.type = 'page'
            self.box = Box('%s/page.md' % self.root)
            lines = codecs.open('%s/page.md' % self.root, 'r', 'utf-8').readlines()
            for line in lines:
                data = clean_line(line).split(':')
                key = data[0]
                value = ''.join(data[1:]).strip('\r\n').strip() # drop '\n'
                if value == '':
                    break
                elif value[0] == '!': #if value starts with ! then eval expression
                    value = eval(value[1:])
                setattr(self, key, value)
        else:
            self.type = 'dir'

    def discover(self):
        """recursively discover items in directory object (self.root) and subdirectories"""
        global LANGUAGES, GALLERY
        items = os.listdir(self.root)
        for item in items:
            path = os.path.join(self.root, item)
            if os.path.isdir(path):
                self.add_child(item, Item(path, lang=self.lang, parent=self, level=self.level + 1))
            else:
                t, basename = get_type(item)
                if not self.type:
                    self.type = t
                if t == 'image':
                    img = Img(item, path)
                    self.add_value(basename, img)
                    for lang in LANGUAGES:
                        gallery = getattr(img, '_gallery_%s' % lang) or None
                        if gallery:
                            if GALLERY[lang].has_key(gallery):
                                GALLERY[lang][gallery].append(img)
                            else:
                                GALLERY[lang][gallery] = [img]
                else:
                    self.add_value(basename, Static(path, t)) #TODO: use an object too
        return self


class Img:
    def __init__(self, filename, path):
        global BUILD_DIR
        self.filename = filename
        self.name = '.'.join(filename.split('.')[:-1]).lower()
        self.image = Image.open(path)
        self._url = 'static/img/%s' % self.filename
        self.build_path = os.path.join(BUILD_DIR, 'static', 'img', self.filename)
        dirname = os.path.dirname(path)

        self.read_catalog(dirname)
        self.save()

    def url(self):
        # here we use the current page defined into main loop (it's a global variable)
        global PAGE
        result = '../' * (PAGE.level + 1) + self._url
        return result

    def read_catalog(self, dirname):
        """read translated info about the image from language catalogs"""
        global LANGUAGES
        for lang in LANGUAGES:
            try:
                lines = codecs.open('%s/catalog.%s' % (dirname, lang), 'r', 'utf-8').readlines()
            except IOError:
                break
            for line in lines:
                if line.startswith('%s.' % self.name):
                    key = line.split(':')[0].split('.')[1].strip() # format line: name.key:value
                    value = ''.join(line.split(':')[1])[:-1].strip() # remove \n with a function
                    setattr(self, '_%s_%s' % (key, lang), value) 

    def save(self):
        # save to build/static/img
        global BUILD_DIR
        try:
            os.makedirs(os.path.join(BUILD_DIR, 'static', 'img'))
        except:
            pass
        self.image.save(self.build_path)
        
    def get(self, cl='', id=''):
        res = '<img '
        if cl:
            res += 'class="%s" ' % cl
        if id:
            res += 'id="%s" '% id
        res += 'src="%s" title="%s" alt="%s"/>' % (self.url(), self.title, self.alt)
        return res

    def __str__(self):
        return self.get()
        #return '<img src="%s" title="%s" alt="%s" />' % (self.url(), self.title(), self.alt())
        
    def __unicode__(self):
        return self.get()
        
    def __repr__(self):
        return self.get()

    def __getattr__(self, field):
        """ return values from object using page language """
        global PAGE
        try:
            result = self.__dict__['_%s_%s' % (field, PAGE.lang)]
        except:
            result = ''
        return result

#TODO: remove this class and use Item class too
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
        self.html = md.convert(self.md)

        # insert newline after header tags
        #for i in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        #    self.html = self.html.replace('</%s>' % i, '</%s><br>' % i)

        # add bootstrap styles to tables
        self.html = self.html.replace('<table>', '<table class="table table-striped">')

    def parse(self):
        """Parse a page object in order to set attributes from its header"""
        # read attributes until empty line or not key-value pair
        is_header = True
        for line in self.lines:
            # add line to markdown if it isn't header
            if not is_header:
                self.md += line + '\n'
            else:
                # empty line to split header from body
                if is_header and line == "":
                    self.md += '\n'
                    continue
                data = clean_line(line).split(":")

                # end of header
                if len(data) == 1:
                    is_header = False
                    self.md += line + ' '
                    continue
                # add attribute to this object
                attr = data[0]
                value = data[1].strip('\r\n')
                # TODO: use symbol '#' to mark expresions to evaluate
                #try:
                    # to eval a string is cool! (maths are welcome)
                    #value = eval(data)
                #except:
                #value = data
                #    if t: print "+++", attr, value
                setattr(self, attr, value)
        self.get_html()

def walk(item, items):
    """return a dictionary with children from item"""
    items = items
    for i in item.children:
        items[i.id] = i
        if i.children:
            walk(i, items)
    return items


def build(project_path):
    """build project (main loop)"""
    global LANGUAGES, BUILD_DIR, GALLERY, ENV

    # initial constants
    PROJECT_DIR = project_path
    BUILD_DIR = os.path.join(PROJECT_DIR, 'build')
    RESOURCES_DIR = os.path.join(PROJECT_DIR, 'resources')
    STATIC_DIR = os.path.join(RESOURCES_DIR, 'static')
    TEMPLATES_DIR = os.path.join(PROJECT_DIR, 'templates')
    TEMPLATE_DEFAULT = 'main.html'

    # initialize jinja2 objects
    ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    ENV.filters['thumbnail'] = thumbnail
    ENV.filters['template'] = template

    # read settings file (yaml format) - config.yml
    try:
        config = open('%s/config.yml' % PROJECT_DIR)
    except:
        print "Error: create a config.yml file with project settings. __init__.py is deprecated."
        sys.exit(2)
    s = yaml.load(config)
    config.close()
    
    # assing data from settings to LANGUAGE and I18N
    LANGUAGES = s['LANGUAGES']
    I18N = s['I18N']

    # init an empty GALLERY object with language keys
    for lang in LANGUAGES:
        GALLERY[lang] = {}

    #TODO: use external template for google_analytics
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

    #TODO: use external template for google maps
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

    #TODO: use external template for sitemap
    sitemap_template = Template("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  {% for url in urls %}
  <url>
    <loc>{{ url }}</loc>
    <lastmod>{{ today }}</lastmod>
    {% if page.changefreq %}
    <changefreq>{{ page.changefreq }}</changefreq>
    {% endif %}
    {% if page.prority %}
    <priority>{{ page.priority }}</priority>
    {% endif %}
  </url>
  {% endfor %}
</urlset> """)
    
    builtins = {}

    # built-ins
    try:
        builtins['google_analytics'] = google_analytics.render(analytics_id=s.analytics_id)
        builtins['google_maps'] = google_maps.render(zoom=s.map_zoom, lat=s.map_lat, lon=s.map_lon, title=s.map_title)
    except:
        print "Warning! There aren't information to setup Google services."

    # copy full static/ to build/static
    try:
        shutil.rmtree(os.path.join(BUILD_DIR, 'static'))
    except:
        pass
    shutil.copytree(STATIC_DIR, os.path.join(BUILD_DIR, 'static'))


    # get pages and menu
    pages = {} #TODO: Page class?
    menu = {}
    for lang in LANGUAGES:
        #TODO: join menus and pages ??
        menu[lang] = Item(os.path.join(RESOURCES_DIR, lang), lang=lang, level=0)
        pages[lang] = walk(Item(os.path.join(RESOURCES_DIR, lang), lang=lang, level=0), items={})

    static = Item(STATIC_DIR)
    
    # process pages in each language
    urls = []
    for lang in LANGUAGES:
        for n, m in pages[lang].items():
            urls.append('%s/%s' % (s['DOMAIN'], m._url))

            globals()['PAGE'] = m # current page goes to global 'page' var
                        
            try:
                t = '%s.html' % m.template.strip() #template
            except AttributeError:
                print "Warning: Using default template for %s." % m
                t = '%s.html' % s.DEFAULT_TEMPLATE
            t = ENV.get_template(t)

            for root, dirs, files in os.walk(m.root):
                boxes = {}
                for file in files:
                    #TODO: check extension (markdown, html, etc.)
                    #process files except hiddens
                    if not file.startswith('.'):
                        box = Box(join(root, file))
                        key = file.split('.')[0]
                        boxes[key] = box

                lang_pages = {}
                for l in LANGUAGES:
                    try:
                        lang_pages[l] = pages[l][m.id]
                    except KeyError:
                        print "Warning: missing info for '%s' language." % l

                # write output file
                boxes['current_language'] = m.lang
                boxes['builtins'] = builtins
                boxes['page'] = m #TODO: better not in boxes?
                boxes['lang_pages'] = lang_pages
                menu_lang = menu[lang].children

                # render templates twice in order to use jinja2 into markdown files
                output_md = t.render(css=static.css, js=static.js, img=static.img, ico=static.ico, menu=menu_lang, gallery=GALLERY[lang], i18n=I18N[lang], **boxes)
                t_md = ENV.from_string(output_md)
                output = t_md.render(css=static.css, js=static.js, img=static.img, ico=static.ico, menu=menu_lang, gallery=GALLERY[lang], i18n=I18N[lang], **boxes)

                # save html file
                try:
                    os.makedirs(os.path.join(BUILD_DIR, os.path.join(*m.root.split(os.path.sep)[-m.level-1:])))
                    print "directory %s created." % os.path.join(BUILD_DIR, m.lang, os.path.join(m.root.split(os.path.sep)[-m.level-1:]))
                except:
                    pass
                codecs.open(os.path.join(BUILD_DIR, m.lang, os.path.join(*m.root.split(os.path.sep)[-m.level:]), 'index.html'), 'w', 'utf-8').write(output)

    # write sitemap xml file
    # jinja2 can't do {{ spaceless }} :-(
    sitemap_lines = sitemap_template.render(urls=urls, today=date.today().strftime('%Y-%M-%d'), page=m).split('\n')
    xml = '\n'.join([x for x in sitemap_lines if x.strip()])
    open('%s/sitemap.xml' % BUILD_DIR, 'w').write(xml)

if __name__ == '__main__':
    len_argv = len(sys.argv)
    if len_argv == 1:
        project_path = os.path.curdir
    if len_argv != 2:
        sys.exit('Usage: %s path/to/project' % sys.argv[0])

    project_path = sys.argv[1].endswith(os.path.sep) and sys.argv[1][:-1] or sys.argv[1] #nice line!!! :-)
    build(project_path)
