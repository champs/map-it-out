import urllib
from xml.dom import minidom
import simplejson as json

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)      

class Item():

    def __init__(self,obj):
        self.obj = obj
        self.title = self.extractData('title')
        self.desc = self.extractData('desc') 
        self.canpass = self.extractData('canpass')  
        self.date = self.extractData('date') 
        self.lat = self.extractData('lat') 
        self.lng = self.extractData('lon') 
    
    def road(self):
        if self.canpass == 't':
            return True
        else:
            return False

    def extractData(self,field):
        try:
            return getText(self.obj.getElementsByTagName(field)[0].childNodes)
        except:
            return ''
    def text(self):
        try:
            text =  '%s\n%s'%(self.title,self.desc)
            return text
        except:
            return ''

    def water(self):
        try:
            ## feed return level in cm unit // i have to change it to [0-8]
            text_array = self.title.split(' ')         
            level = float(text_array[4])
            my_level = level/15
            if my_level > 8:
                return 8
            return int(my_level)


        except:
            return 0
    def to_dict(self):
        return { 'lat': self.lat,
                'lng': self.lng,
                #'text': self.text(),
                #'road': self.road(),
                'water': self.water()
                }

    def __repr__(self):
        return json.dumps(self.to_dict)
    
class FeedFMSParser():
    def __init__(self):
        #self.feed_url = "http://fms2.drr.go.th/feed"
        #self.dom = minidom.parse(urllib.urlopen(self.feed_url))
        document = open('feed.xml').read()
        self.dom = minidom.parseString(document)
    
    def list_items(self):
        items = []
        for i in self.dom.getElementsByTagName('item'):
            item = Item(i)
            if item.water == 0 or item.lat == "" or item.lng == "":
                pass
            else:
                items.append(item.to_dict())

        return items

