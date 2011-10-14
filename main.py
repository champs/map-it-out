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


title = 'ThaiFlood2011'

class ThaiFloodReport(webapp.RequestHandler):
    def get(self):

        error = urllib.unquote(self.request.get('error'))
        #reports = Report().all().filter('title', title).latest()
        reports = Report().all().filter('title', title)
        reports.order('-date')
        
        template_values = {
                'title' : title,
				'e_msg':error,
                'reports': reports,
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


    def post(self): 
        request = self.request
        report = Report()
        
        try:
            name = urllib.unquote(self.request.get('name')) 
            water = urllib.unquote(self.request.get('water')) 
            urgent = urllib.unquote(self.request.get('urgent')) 
            text = urllib.unquote(self.request.get('text')) 
            
            report.title = title
            report.name = name
            report.water = float(water)
            report.urgent = urgent
            report.text = text
            report.lat = 0.0
            report.lng = 0.0
            report.put()

        except Exception, e:
            self.redirect('/ThaiFlood2011/?error=Error, %s'%e)
        self.redirect('/ThaiFlood2011/')

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.redirect('/ThaiFlood2011/')



def main():
    application = webapp.WSGIApplication([('/ThaiFlood2011/', ThaiFloodReport),
                                        ('/', MainHandler)
                                        
                                        ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
