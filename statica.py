#!/usr/bin/env python

__author__ = "Pedro Gracia"
__copyright__ = "Copyright 2012, Impulzia S.L."
__credits__ = ["Pedro Gracia"]
__license__ = "BSD"
__version__ = "0.4"
__maintainer__ = "Pedro Gracia"
__email__ = "pedro.gracia@impulzia.com"
__status__ = "Development"

import os
import codecs
from os.path import join, getsize
import shutil
import markdown
from jinja2 import Environment, FileSystemLoader, Template


# initial constants
RESOURCES_DIR = 'resources/'
STATIC_DIR = 'static/'
TEMPLATES_DIR = 'templates/'
TEMPLATE_DEFAULT = 'main.html'
BUILD_DIR = 'build/'
LANGUAGES = ['ca', 'es']
#DEFAULT_LANGUAGE = 'ca'

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

# initialize makdown object
md = markdown.Markdown(safe_mode=False, extensions=['tables', 'superscript'])
# initialize jinja2 objects
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
template = env.get_template(TEMPLATE_DEFAULT)

class Static:
    """Basic Object for css, js and images resources"""
    def __init__(self):
        self.css = {}
        self.js = {}
        self.img = {}
        self.ico = {}
        self.include('css')
        self.include('js')
        self.include('img')
        self.include('ico')
        
    def include(self, t):
        """walk throught static dirs to get files"""
        for root, dirs, files in os.walk(os.path.join(STATIC_DIR, t)):
            for file in files:
                key_split = file.split('.')
                key = '.'.join(key_split[:-1])
                r = getattr(self, t)
                key = key.replace('-', '_').replace('.', '_')
                r[key] = '../static/%s/%s' % (t, file)


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
    # main function
    res = Static()
    builtins = {}
    
    # built-ins
    try:
        import settings as s
        builtins['google_analytics'] = google_analytics.render(analytics_id=s.analytics_id)
        builtins['google_maps'] = google_maps.render(zoom=s.map_zoom, lat=s.map_lat, lon=s.map_lon, title=s.map_title)
    except:
        print "Error"
           
    for root, dirs, files in os.walk(RESOURCES_DIR):
        if root == RESOURCES_DIR:
            # process resources for each languages
            for lang in dirs:
                for root, dirs, files in os.walk(os.path.join(RESOURCES_DIR, lang)):
                    boxes = {}
                    for file in files:
                        #TODO: check extension (markdown, html, etc.)
                        box = Box(join(root, file))
                        key = file.split('.')[0]
                        boxes[key] = box.parse()

                    # write output file
                    boxes['current_language'] = lang
                    boxes['builtins'] = builtins
                    output = template.render(css=res.css, js=res.js, img=res.img, ico=res.ico, **boxes)
                    codecs.open(os.path.join(BUILD_DIR, lang, 'index.html'), 'w', 'utf-8').write(output)
    
    try:
        shutil.rmtree(os.path.join(BUILD_DIR, 'static/'))
    except:
        pass
    shutil.copytree('static/', os.path.join(BUILD_DIR, 'static/'))

if __name__ == '__main__':
    main()