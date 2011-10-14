from google.appengine.api import users  
from google.appengine.ext import db


class Report(db.Model):

    title = db.StringProperty()
    lat = db.FloatProperty()
    lng = db.FloatProperty()  
    ## google
    area = db.StringProperty()
    city = db.StringProperty()
    ## form input
    name = db.StringProperty()
    water = db.IntegerProperty()
    road = db.BooleanProperty()
    text  =db.StringProperty(multiline=True,)
    date = db.DateTimeProperty(auto_now_add=True)

    def __repr__(self):
        return '%i,%s\t%s. %s, %s, %s'%(self.key().id,self.title, self.name , str(self.urgent), self.text, str(self.date))