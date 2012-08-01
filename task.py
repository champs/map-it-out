from google.appengine.ext import blobstore
import urllib2
import simplejson
from feedparser import FeedFMSParser
from google.appengine.ext import webapp
import logging
from model import Feed
## Download every hour

class FeedReload(webapp.RequestHandler):
        
    def get(self):
        feed = FeedFMSParser()
        final_report = feed.store_items()
        json = simplejson.dumps(final_report)
        self.response.headers.add_header('content-type', 'application/json', charset='utf-8')
        self.response.out.write(json)

