#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from model import Report
import os
import urllib
from datetime import date, datetime, time, timedelta
from google.appengine.ext.db import djangoforms
import simplejson
import pprint

title = 'WaterReport'

days = 3

def get_startDay():
    deltaDays = timedelta(days)
    endDate = datetime.now()
    startDate = endDate - deltaDays          
    return startDate

class ThaiFloodReport(webapp.RequestHandler):
    def get(self):
        error = urllib.unquote(self.request.get('error'))
        startDate = get_startDay()
        reports = Report().all().filter('title', title)
        reports.order('-date')
        reports.filter('date >' ,startDate)
        template_values = {
                'title' : title,
				'e_msg':error,
                'reports': simplejson.dumps([r.to_dict() for r in reports]),
                'startDate':startDate
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


    def post(self): 
        request = self.request
        report = Report()
       #try:
        name = urllib.unquote(self.request.get('name')) 
        water = urllib.unquote(self.request.get('water')) 
        road = urllib.unquote(self.request.get('road')) 
        text = urllib.unquote(self.request.get('text')) 
        lat = urllib.unquote(self.request.get('lat')) 
        lng = urllib.unquote(self.request.get('lng')) 
        
        report.title = title
        report.name = name
        report.lat = float(lat)
        report.lng = float(lng)
        report.water = int(water)
        report.text = text
        report.road = bool(road)
        report.put()

#        except Exception, e:
            #self.redirect('/ThaiFlood2011/?error=Error, %s'%e)
        error = urllib.unquote(self.request.get('error'))
        startDate = get_startDay()
        
        reports = Report().all().filter('title', title)
        reports.order('-date')
        reports.filter('date >' ,startDate)
            
        template_values = {
                'title' : title,
				'e_msg':error,
                'reports': simplejson.dumps([r.to_dict() for r in reports]),
                'startDate':startDate

        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values)) 

class jsonHandler(webapp.RequestHandler):
    def get(self,title):
        startDate = get_startDay()
        reports = Report().all()
        reports.filter('title', title)
        reports.order('-date')
        reports.filter('date >' ,startDate)
        json = simplejson.dumps([r.to_dict() for r in reports]) 
        self.response.headers.add_header('content-type', 'application/json', charset='utf-8')
        self.response.out.write(json)
 

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.redirect('/WaterReport/')



def main():
    application = webapp.WSGIApplication([('/WaterReport/', ThaiFloodReport),
                                        ('/', MainHandler),
                                        (r'/(.*)/json', jsonHandler)
                                        ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
