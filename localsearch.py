# Copyright 2008 Google Inc. All Rights Reserved.

"""A static map implementation of Google Maps that provides savepoints.

This program is a completely non-JavaScript implementation of Google Maps.  It
uses Google's AJAX LocalSearch API (http://code.google.com/apis/ajaxsearch/
documentation/reference.html#_fonje_local) to allow users to search for points
on the map.  It also uses Google's App Engine to store users' saved locations.
"""

__author__ = 'lisbakke@google.com (Ben Lisbakken)'


import os
import math
import cgi
from django.utils import simplejson
import wsgiref.handlers

from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import urllib


class SavedMapPoint(db.Model):
  """This is the data store class that is used to save map points.
  
  This class is used to save a point on the map.  It saves information so that 
  the point can be completely recreated on a map with the information here, 
  including the information about the point such as the street address, city, 
  phone number, etc.  This point is associated with a user, so that each user 
  can have their own saved points.  

  Attributes:
    user: A UserProperty to associate the record with a user.  Optional --
      There are two times to use SavedMapPoints.  One is when the user searched   
      for a point and decided to click "save" on it.  The other is when the 
      application saves a LastPoint (the last point the user was looking at).  
      In this case, we create a SavedMapPoint that the LastPoint has a 
      reference to.  In case one (user clicks save) we assign a user, in case 2 
      (SavedMapPoint is from LastPoint) we don't assign a user.  That way when 
      we pull a user's "saved points" we don't accidentally grab their "last 
      point" because the user didn't choose to save it so we shouldn't display 
      it as their "saved point".
    lat: String of the latitude of the point.
    lng: String of the longitude of the point.
    title: String of the title of the point.
    url: String of the url of the point.
    street_address: String of the street address of the point.
    region: String of the region of the point.
    city: String of the city of the point.
    date: DateTime the point was saved at.  Optional, defaults to Now.
    zoom_level: String of the zoom level of the point.
    phone: String of the phone number of the point.
  """
  user = db.UserProperty()
  lat = db.StringProperty()
  lng = db.StringProperty()
  title = db.StringProperty()
  url = db.StringProperty()
  street_address = db.StringProperty()
  region = db.StringProperty()
  city = db.StringProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  zoom_level = db.StringProperty()
  phone = db.StringProperty()


class LastPosition(db.Model):
  """This is the data store class that is used to save the last position.

  This class is used to save the last map view that the user was looking at.  
  If the user was last looking at a single point then the saved_map_key will be 
  used to reference the SavedMapPoint that they were looking at.  If the user 
  was last looking at a query containing multiple search results, then we 
  simply store the last query that they ran and the zoom level that they were 
  on.  With this information, we can recreate their last view.  The 
  LastPosition is only grabbed in MainPage (aka when the user navigates to the 
  base directory of the application).  MainPage is also redirected to from the 
  delete and save functions because when they complete they won't want to 
  change the map from what it was when the user clicked delete/save.

  Attributes:
    q: String of the query ran.  This is optional -- if the LastPosition had
      multiple search results, use this.
    saved_map_key: String of the key for the associated SavedMapPoint.  This 
      is optional -- if the LastPosition had one result, use this.
    user: A UserProperty to associate the record with a user.
    zoom_level: String of the zoom level of the last position saved.
  """
  q = db.StringProperty()
  saved_map_key = db.StringProperty()
  user = db.UserProperty()
  zoom_level = db.StringProperty()


# Specifies the size of the map (in pixels).
MAP_SIZE = [256,256]
    
# This is the Maps API key for running on localhost:8080
MAP_KEY = 'ABQIAAAA1XbMiDxx_BTCY2_FkPh06RR20YmIEbERyaW5EQEiVNF0mpNGfBSRb' \
    '_rzgcy5bqzSaTV8cyi2Bgsx3g'

class Point():
  """Stores a simple (x,y) point.  It is used for storing x/y pixels.

  Attributes:
    x: An int for a x value.
    y: An int for a y value.
  """
  def __init__(self, x, y):
    self.x = x
    self.y = y
    
  def ToString(self):
    return '(%s, %s)' % (self.x, self.y)
    
  def Equals(self, other):
    if other is None :
      return false
    else:
      return (other.x == self.x and other.y == self.y)


class MercatorProjection():
  """Calculates map zoom levels based on bounds or map points.

  This class contains functions that are required for calculating the zoom  
  level for a point or a group of points on a static map.  Usually the Maps API 
  does the zoom for you when you specify a point, but not on static maps.

  Attributes:
    pixels_per_lon_degree: A list for the number of pixels per longitude 
      degree for each zoom.
    pixels_per_lon_radian: A list for the number of pixels per longitude
      radian for each zoom.
    pixel_origo: List of number of x,y pixels per zoom.
    pixel_range: The range of pixels per zoom.
    pixels: Number of pixels per zoom.
    zoom_levels: A list of numbers representing each zoom level to test.
  """
  def __init__(self, zoom_levels=18):
    self.pixels_per_lon_degree = []
    self.pixels_per_lon_radian = []
    self.pixel_origo = []
    self.pixel_range = []
    self.pixels = 256
    zoom_levels = range(0, zoom_levels)
    for z in zoom_levels:
      origin = self.pixels / 2
      self.pixels_per_lon_degree.append(self.pixels / 360)
      self.pixels_per_lon_radian.append(self.pixels / (2 * math.pi))
      self.pixel_origo.append(Point(origin, origin))
      self.pixel_range.append(self.pixels)
      self.pixels = self.pixels * 2
    
  def CalcWrapWidth(self, zoom):
    return self.pixel_range[zoom]
    
  def FromLatLngToPixel(self, lat_lng, zoom):
    """Given lat/lng and a zoom level, returns a Point instance.

    This method takes in a lat/lng and a _test_ zoom level and based on that it 
    calculates at what pixel this lat/lng would be on the map given the zoom 
    level.  This method is used by CalculateBoundsZoomLevel to see if this 
    _test_ zoom level will allow us to fit these bounds in our given map size.

    Args:
      lat_lng: A list of a lat/lng point [lat, lng]
      zoom: A list containing the width/height in pixels of the map.

    Returns:
      A Point instance in pixels.
    """
    o = self.pixel_origo[zoom]
    x = round(o.x + lat_lng[1] * self.pixels_per_lon_degree[zoom])
    siny = Bound(math.sin(DegreesToRadians(lat_lng[0])), 
        -0.9999, 0.9999)
    y = round(o.y + 0.5 * math.log((1 + siny) / 
        (1 - siny)) * -self.pixels_per_lon_radian[zoom])
    return Point(x, y)

  def CalculateBoundsZoomLevel(self, bounds, view_size):
    """Given lat/lng bounds, returns map zoom level.

    This method is used to take in a bounding box (southwest and northeast 
    bounds of the map view we want) and a map size and it will return us a zoom 
    level for our map.  We use this because if we take the bottom left and 
    upper right on the map we want to show, and calculate what pixels they 
    would be on the map for a given zoom level, then we can see how many pixels 
    it will take to display the map at this zoom level.  If our map size is 
    within this many pixels, then we have the right zoom level.

    Args:
      bounds: A list of length 2, each holding a list of length 2. It holds
        the southwest and northeast lat/lng bounds of a map.  It should look 
        like this: [[southwestLat, southwestLat], [northeastLat, northeastLng]]
      view_size: A list containing the width/height in pixels of the map.

    Returns:
      An int zoom level.
    """
    zmax = 18
    zmin = 0
    bottom_left = bounds[0]
    top_right = bounds[1]
    backwards_range = range(zmin, zmax)
    backwards_range.reverse()
    for z in backwards_range:
      bottom_left_pixel = self.FromLatLngToPixel(bottom_left, z)
      top_right_pixel = self.FromLatLngToPixel(top_right, z)
      if bottom_left_pixel.x > top_right_pixel.x :
        bottom_left_pixel.x -= self.CalcWrapWidth(z)
      if abs(top_right_pixel.x - bottom_left_pixel.x) <= view_size[0] \
          and abs(top_right_pixel.y - bottom_left_pixel.y) <= view_size[1] :
        return z
    return 0

    
def DegreesToRadians(deg):
  return deg * (math.pi / 180)

    
def CalcCenterFromBounds(bounds):
  """Calculates the center point given southwest/northeast lat/lng pairs.

  Given southwest and northeast bounds, this method will return the center  
  point.  We use this method when we have done a search for points on the map, 
  and we get multiple results.  In the results we don't get anything to 
  calculate the center point of the map so this method calculates it for us.

  Args:
    bounds: A list of length 2, each holding a list of length 2. It holds
      the southwest and northeast lat/lng bounds of a map.  It should look 
      like this: [[southwestLat, southwestLat], [northeastLat, northeastLng]]

  Returns:
    An dict containing keys lat and lng for the center point.
  """
  north = bounds[1][0]
  south = bounds[0][0]
  east = bounds[1][1]
  west = bounds[0][1]
  center = {}
  center['lat'] = north - float((north - south) / 2)
  center['lng'] = east - float((east - west) / 2)
  return center
    
        
def Bound(value, opt_min, opt_max):
  """Returns value if in min/max, otherwise returns the min/max.

  Args:
    value: The value in question.
    opt_min: The minimum the value can be.
    opt_max: The maximum the value can be.

  Returns:
    An int that is either the value passed in or the min or the max.
  """
  if opt_min is not None:
    value = max(value, opt_min)
  if opt_max is not None:
    value = min(value, opt_max)
  return value


def CalcBoundsFromPoints(lats, lngs):
  """Calculates the max/min lat/lng in the lists.

  This method takes in a list of lats and a list of lngs, and outputs the 
  southwest and northeast bounds for these points.  We use this method when we 
  have done a search for points on the map, and we get multiple results.  In 
  the results we don't get a bounding box so this method calculates it for us.

  Args:
    lats: List of latitudes
    lngs: List of longitudes

  Returns:
    A list of length 2, each holding a list of length 2.  It holds 
    the southwest and northeast lat/lng bounds of a map.  It should look 
    like this: [[southwestLat, southwestLat], [northeastLat, northeastLng]]
  """
  lats = [float(x) for x in lats]
  lngs = [float(x) for x in lngs]
  flats = map(float,lats)
  flngs = map(float,lngs)
  west = min(flngs)
  east = max(flngs)
  north = max(flats)
  south = min(flats)
  return [[south, west], [north, east]]
      

def DoSearch(query, MAP_SIZE):
  """Uses AJAX LocalSearch API to search Google Maps for a query.

  Given a query and map size, this method starts a search for us.  It will use 
  the AJAX LocalSearch API to do the search.  It will return all information 
  needed to create a static map with the results of the search as points on the 
  map.  This method is used whenever a user enters a query.

  Args:
    query: The query that will be used for the search.
    MAP_SIZE: The size of the map that the points will be displayed on.

  Returns:
    A dict containing results information necessary to put the point on the map
    and display it's information in the results section.  Here is an example 
    return dict:

    {
      'zoom': 10,
      'lat': 34.0002,
      'lng': -112.2345,
      'markers': '34.0002,-112.2345,midreda|',
      'display_results': [{
        'letter':'http://www.google.com/mapfiles/gadget/letters/markera.png' ,
        'street_address': '666 Spear St',
        'title': 'Pizza Place',
        'region': 'CA',
        'city': 'San Francisco',
        'lat': 34.0002,
        'lng': -112.2345,
        'url': 'http://path.to/business_review',
        'phone': (206) 999-9999
      }]
    }
    
    Note that display_results is a list and can have multiple dict entries, 
    each representing a search result from the LocalSearch query.
  """
  query = urllib.urlencode({'q' : query})
  url = 'http://ajax.googleapis.com/ajax/services/search/local?' \
      'key=%s&v=1.0&%s&rsz=large' % (MAP_KEY, query)
  local_search_points = urlfetch.fetch(url)
  json = simplejson.loads(local_search_points.content)
  points = json['responseData']['results']
  markers = ''
  index = 0
  display_results = []
  lats = []
  lngs = []
  for i in points:
    lats.append(i['lat'])
    lngs.append(i['lng'])
    letter = ord('a')
    letter = unichr(letter + index)
    markers +=  '%s,%s,midred%s|' % (i['lat'], i['lng'], str(letter))
    phone_number = ''
    if i.has_key('phoneNumbers'):
      phone_number = i['phoneNumbers'][0]['number']
      
    display_results.append({
      'letter':'http://www.google.com/mapfiles/gadget/letters/marker%s.png' %
          letter.upper(),
      'street_address':i['streetAddress'],
      'title':i['titleNoFormatting'],
      'region': i['region'],
      'city':i['city'],
      'lat':i['lat'],
      'lng':i['lng'],
      'url':'%s&reviews=1' % i['url'],
      'phone':phone_number
    })
    index += 1
  markers = urllib.urlencode({'markers':markers})
  if len(points) == 0:
    return None
  if len(points) == 1:
    viewport = json['responseData']['viewport']
    mercator_projection = MercatorProjection(18)
    southwest = [float(viewport['sw']['lat']),float(viewport['sw']['lng'])]
    northeast = [float(viewport['ne']['lat']),float(viewport['ne']['lng'])]
    bounds = [southwest, northeast]
    zoom_level = mercator_projection.CalculateBoundsZoomLevel(bounds, MAP_SIZE)
    return_obj = {
      'zoom': zoom_level,
      'lat': points[0]['lat'],
      'lng': points[0]['lng'],
      'markers': markers,
      'display_results': display_results
    }
  else:
    mercator_projection = MercatorProjection(18)
    bounds = CalcBoundsFromPoints(lats, lngs)
    center_point = CalcCenterFromBounds(bounds)
    zoom_level = mercator_projection.CalculateBoundsZoomLevel(bounds, MAP_SIZE)
    
    
    lat = center_point['lat']
    lng = center_point['lng']
    return_obj = {
      'zoom': zoom_level,
      'lat': lat,
      'lng': lng,
      'markers': markers,
      'display_results': display_results
    }
  return return_obj
  
  
def SetGreeting(redirector):
  """Sets greeting string, redirects them if they aren't logged in.

  This method gets called for every HTTP request.  We want to make sure that 
  the user is logged in, and when they are we give them a nice greeting message 
  and a link to let them sign out.

  Args:
    redirector: An instance of the class calling this method, so that it can 
      use the redirector.redirect(url) if the user isn't logged in.

  Returns:
    The greeting string.
  """
  user = users.get_current_user()
  if user:
    greeting = ('Welcome, %s! (<a href=\'%s\'>sign out)</a>.<br/>' %
        (user.nickname(), users.create_logout_url('/')))
    return greeting
  else:
    redirector.redirect(users.create_login_url('/'))
    return 0


def SaveLastSinglePoint(lat, lng, title, url, street_address, region, city, 
                        zoom_level, phone):
  """Saves last map view in datastore so last view can be restored.

  This method is used when we want to save the last single point that a user 
  was looking at (we use a different method if they were looking at multiple 
  points).  This method will update the LastPosition for the user, and if the 
  LastPosition points to a SavedMapPoint then this method will update/delete it 
  as necessary.

  Args:
    lat: Latitude of point to save.
    lng: Longitude of point to save.
    title: Title of point to save.
    url: Url of point to save.
    street_address: The street address of point to save.
    region: The region of the point to save.
    city: The city of the point to save.
    zoom_level: The zoom level that was used when saving.
    phone: The phone number of the point to save.
    
  Returns:
    Nothing
  """
  last_point = RetrieveLastPoint()
  if last_point is None:
    last_point = LastPosition()
  if last_point.saved_map_key:
    saved_map_point = db.get(db.Key(str(last_point.saved_map_key)))
  else:
    saved_map_point = SavedMapPoint()

  saved_map_point.lat = lat
  saved_map_point.lng = lng
  saved_map_point.title = title
  saved_map_point.url = url
  saved_map_point.street_address = street_address
  saved_map_point.region = region
  saved_map_point.city = city
  saved_map_point.zoom_level = zoom_level
  saved_map_point.phone = phone

  key = saved_map_point.put()

  last_point.saved_map_key = str(key)
  last_point.user = users.get_current_user()
  last_point.put()


def SaveLastSearch(q, zoom_level):
  """Saves last map search in datastore so last view can be restored.

  This method is used when we want to save the last map view if there were 
  multiple search results (if there was only one search result, then use 
  SaveLastSinglePoint).  This method will simply change the logged in user's 
  LastPosition entry, and delete their SavedMapPoint associated with it.

  Args:
  q: The query.
  zoom_level: The zoom level that the search was saved at.

  Returns:
    Nothing.
  """
  last_point = RetrieveLastPoint()
  if last_point is None:
    last_point = LastPosition()
  if last_point.saved_map_key:
    DeleteByKey(last_point.saved_map_key)
    last_point.saved_map_key = None
  last_point.q = q
  last_point.zoom_level = str(zoom_level)
  last_point.user = users.get_current_user()
  last_point.put()


def RetrieveLastPoint():
  """Returns the data for the last map view accessed.

  Args:
    None
  Returns:
    An instance of LastPosition.
  """
  last_point = db.GqlQuery('SELECT * FROM LastPosition WHERE user = :1',
                           users.get_current_user())
  last_point = last_point.fetch(1)
  if len(last_point) > 0:
    return last_point[0]
  else:
    return None


def SetDefaultTemplateValues(self, MAP_SIZE, MAP_KEY, greeting, q, 
                             savedPoints):
  """Sets default values for the template.

  Args:
    MAP_SIZE: A list of the size of the map in pixels.
    MAP_KEY: The key sent with the AJAX Search API request.
    greeting: The greeting string.
    q: The query being done.
    savedPoints: A result object containing all SavedMapPoint 
      instances associated with the current user.
    
  Returns:
    Nothing.
  """
  self.template_values['q'] = q
  self.template_values['MAP_KEY'] = MAP_KEY
  self.template_values['MAP_SIZE'] = '%sx%s' % (str(MAP_SIZE[0]),   
      str(MAP_SIZE[1]))
  self.template_values['greeting'] = greeting
  self.template_values['savedPoints'] = savedPoints


def SetupSinglePoint(lat, lng, zoom_level, street_address, title, region, city, 
                     url, phone):
  """Sets the template values for a single point search.

  There are template values that must be set that are specific to viewing a 
  single point on the map.  This method sets those up.

  Args:
    lat: Latitude of point to save.
    lng: Longitude of point to save.
    title: Title of point to save.
    url: Url of point to save.
    street_address: The street address of point to save.
    region: The region of the point to save.
    city: The city of the point to save.
    zoom_level: The zoom level that was used when saving.
    phone: The phone number of the point to save.

  Returns:
    A dict that looks like this:
    
    {
      'letter_img' :
        'http://www.google.com/mapfiles/gadget/letters/markerA.png',
      'zoom_level' : 10,
      'lat' : 34.0001,
      'lng' : -112.2341,
      'markers': '34.0001,-112.2341,midredA|',
      'display_one' : true,
      'search_results' : {
        'letter':'http://www.google.com/mapfiles/gadget/letters/markera.png' ,
        'street_address': '666 Spear St',
        'title': 'Pizza Place',
        'region': 'CA',
        'city': 'San Francisco',
        'lat': 34.0002,
        'lng': -112.2345,
        'url': 'http://path.to/business_review',
        'phone': (206) 999-9999
      }
    }
  """
  letter_img = 'http://www.google.com/mapfiles/gadget/letters/markerA.png'
  return_obj = {}
  return_obj['letter_img'] = letter_img
  return_obj['zoom_level'] = str(zoom_level)
  return_obj['lat'] = lat
  return_obj['lng'] = lng
  display_results = [{
    'letter' : letter_img,
    'street_address' : street_address,
    'title' : title,
    'region' : region,
    'city' : city,
    'lat' : lat,
    'lng' : lng,
    'url' : url,
    'phone' : phone
  }]
  return_obj['markers'] = 'markers=%s,%s,midreda' % (lat, lng)
  return_obj['search_results'] = display_results
  return_obj['display_one'] = 'true'

  return return_obj


def FindSavedPointFromLastPoint(key_name):
  """Returns the SavedMapPoint associated with a LastPosition's saved_map_key.

  Args:
    key_name: The key for the SavedMapPoint.
    
  Returns:
    An instance of LastPosition.
  """
  return db.get(db.Key(str(key_name)))


def FindAllSavedPoints():
  """Returns all SavedMapPoint's for the current user.

  Args:
    None.
    
  Returns:
    All SavedMapPoint instances for the current user.
  """
  if users.get_current_user():
    q = SavedMapPoint.all()
    q.order('title')
    q.filter('user = ', users.get_current_user())
    points = q.fetch(100)
    return points
  else:
    return None


def DeleteByKey(key_name):
  """Delete a data store entry by the key.

  Args:
    key_name: The key to the entry to delete.
    
  Returns:
    Nothing
  """
  entry = db.get(db.Key(str(key_name)))
  db.delete(entry)


class Delete(webapp.RequestHandler):
  """Deletes a saved map point from the data store.

  This class handles when a user clicks the delete button on a point they had 
  saved.  It will call the function DeleteByKey to do the deletion from the 
  data store.  Then, it will redirect to the MainPage class which will restore 
  the last map view the user was on when they hit delete..

  Attributes:
    None.
  """
  def post(self):
    """Handles an HTTP Post to /delete (deletes map location).

    Args:
      key_name: The key to the entry to delete.

    Returns:
      Redirects to MainPage.
    """
    SetGreeting(self)
    key_name = self.request.get('key_name')
    DeleteByKey(key_name)
    self.redirect('/')
    
    
class Save(webapp.RequestHandler):
  """Saves a map point to the data store.

  Attributes:
    None.
  """
  def post(self):
    """Handles an HTTP Post to /save (saves map location).

    Args:
      lat: CGI Arg Latitude of point to save.
      lng: CGI Arg Longitude of point to save.
      zoom_level: CGI Arg The zoom level that was used when saving.
      street_address: CGI Arg The street address of point to save.
      title: CGI Arg Title of point to save.
      region: CGI Arg The region of the point to save.
      city: CGI Arg The city of the point to save.
      url: CGI Arg Url of point to save.
      phone: CGI Arg The phone number of the point to save.

    Returns:
      Redirects to MainPage.
    """
    SetGreeting(self)
    lat = self.request.get('lat')
    lng = self.request.get('lng')
    zoom_level = self.request.get('zoom_level')
    street_address = self.request.get('street_address')
    title = self.request.get('title')
    region = self.request.get('region')
    city = self.request.get('city')
    url = self.request.get('url')
    phone = self.request.get('phone')
    
    query = db.GqlQuery("SELECT * FROM SavedMapPoint WHERE user = :1 "
                        "AND lat = :2 "
                        "AND lng = :3 "
                        "AND title = :4 "
                        "AND url = :5 "
                        "AND street_address = :6 "
                        "AND region = :7 "
                        "AND city = :8 "
                        "AND phone = :9",
                        users.get_current_user(), lat, lng, 
                        title, url, street_address,
                        region, city, phone)
    result = query.fetch(1)
    if(len(result) == 0):
      result = SavedMapPoint()
    else:
      result = result[0]
    result.user = users.get_current_user()
    result.lat = lat
    result.lng = lng
    result.title = title
    result.url = url
    result.street_address = street_address
    result.region = region
    result.city = city
    result.zoom_level = str(zoom_level)
    result.phone = phone
    result.put()    
    self.redirect('/')


class Focus(webapp.RequestHandler):
  """Focuses the map on a single point.

  If a user clicks on a point, then the map will center on that point.  This 
  class handles that functionality.

  Attributes:
    None.
  """
  def post(self):
    """Handles an HTTP Post to /focus (focuses map on single point).

    Args:
      lat: CGI Arg Latitude of point to save.
      lng: CGI Arg Longitude of point to save.
      zoom_level: CGI Arg The zoom level that was used when saving.
      street_address: CGI Arg The street address of point to save.
      title: CGI Arg Title of point to save.
      region: CGI Arg The region of the point to save.
      city: CGI Arg The city of the point to save.
      url: CGI Arg Url of point to save.
      phone: CGI Arg The phone number of the point to save.

    Returns:
      Renders template view for focusing on a single point.
    """
    greeting = SetGreeting(self)
    self.template_values = {}
    lat = self.request.get('lat')
    lng = self.request.get('lng')
    zoom_level = self.request.get('zoom_level')
    street_address = self.request.get('street_address')
    title = self.request.get('title')
    region = self.request.get('region')
    city = self.request.get('city')
    url = self.request.get('url')
    phone = self.request.get('phone')
    
    self.template_values = SetupSinglePoint(lat, lng, zoom_level, 
        street_address, title, region, city, url, phone)
    SaveLastSinglePoint(lat, lng, title, url, street_address, region, city,
                        zoom_level, phone)
    
    SetDefaultTemplateValues(self, MAP_SIZE, MAP_KEY, greeting, '',
        FindAllSavedPoints())

    path = os.path.join(os.path.dirname(__file__), 'local.html')
    self.response.out.write(template.render(path, self.template_values))
    
    
class Zoom(webapp.RequestHandler):
  """Zooms the map in/out.

  If a user clicks a button to zoom in or out, thiss class handles the 
  functionality of it.

  Attributes:
    None.
  """
  def post(self):
    """Handles an HTTP Post to /zoom (zooms the map in/out).

    Args:
      q: CGI Arg The query that was last run.
      lat: CGI Arg Latitude of point to save.
      lng: CGI Arg Longitude of point to save.
      zoom_level: CGI Arg The zoom level that was used when saving.
      street_address: CGI Arg The street address of point to save.
      title: CGI Arg Title of point to save.
      region: CGI Arg The region of the point to save.
      city: CGI Arg The city of the point to save.
      url: CGI Arg Url of point to save.
      phone: CGI Arg The phone number of the point to save.
      zoomOut: CGI Arg saying if we are zooming out.
      zoomIn: CGI Arg saying if we are zooming in.
      zoomTo: CGI Arg saying if we are zooming to a specific zoom level.

    Returns:
      Renders template view for focusing on a single point.
    """
    greeting = SetGreeting(self)
    display_one = self.request.get('display_one')
    q = self.request.get('q')
    zoom_level = self.request.get('zoom_level')

    if self.request.get('zoomOut') != '':
      zoom_level = int(zoom_level) - 1
    if self.request.get('zoomIn') != '':
      zoom_level = int(zoom_level) + 1
    zoom_level = str(zoom_level)
    self.template_values = {}
    
    # Get display setup
    if display_one:
      lat = self.request.get('lat')
      lng = self.request.get('lng')
      title = self.request.get('title')
      city = self.request.get('city')
      region = self.request.get('region')
      street_address = self.request.get('street_address')
      url = self.request.get('url')
      phone = self.request.get('phone')
      self.template_values = SetupSinglePoint(lat, lng, zoom_level,
                                              street_address, title, region,
                                              city, url, phone)
      SaveLastSinglePoint(lat, lng, title, url, street_address, region, city,
                          zoom_level, phone)
    else:
      rs = DoSearch(q, MAP_SIZE)
      if rs is None:
        path = os.path.join(os.path.dirname(__file__), 'bad_search.html')
        self.response.out.write(template.render(path, self.template_values))
        return
      self.template_values['lat'] = rs['lat']
      self.template_values['lng'] = rs['lng']
      self.template_values['markers'] = rs['markers']
      self.template_values['search_results'] = rs['display_results']
      SaveLastSearch(q, zoom_level)
      
      

    self.template_values['zoom_level'] = str(zoom_level)
    
    SetDefaultTemplateValues(self, MAP_SIZE, MAP_KEY, greeting, q, 
        FindAllSavedPoints())
    
    path = os.path.join(os.path.dirname(__file__), 'local.html')
    self.response.out.write(template.render(path, self.template_values))


class Search(webapp.RequestHandler):
  """Searches with the AJAX LocalSearch API for a query.

  If the user performs a search, this class handles the logic for it.

  Attributes:
    None.
  """
  def post(self):
    """Handles an HTTP Post to /search (does a LocalSearch for the query).

    Args:
      q: CGI Arg The query that was last run.

    Returns:
      Renders template view for a search.
    """
    greeting = SetGreeting(self)
    q = self.request.get('q')
    self.template_values = {}
    rs = DoSearch(q, MAP_SIZE)
    if rs is None:
      path = os.path.join(os.path.dirname(__file__), 'bad_search.html')
      self.response.out.write(template.render(path, self.template_values))
      return
    self.template_values['q'] = q
    self.template_values['zoom_level'] = rs['zoom']
    self.template_values['lat'] = rs['lat']
    self.template_values['lng'] = rs['lng']
    self.template_values['markers'] = rs['markers']
    self.template_values['search_results'] = rs['display_results']
        
    SetDefaultTemplateValues(self, MAP_SIZE, MAP_KEY, greeting, q, 
        FindAllSavedPoints())
    
    SaveLastSearch(q, rs['zoom'])
    path = os.path.join(os.path.dirname(__file__), 'local.html')
    self.response.out.write(template.render(path, self.template_values))


class MainPage(webapp.RequestHandler):
  """Displays the last visited map view.

  When the user navigates to this application, or the user clicks save or 
  delete, this class will handle the logic to reconstruct the last map that 
  they were viewing.

  Attributes:
    None.
  """
  def get(self):
    """Handles an HTTP Post to / (renders the last map view).

    Args:
      None.

    Returns:
      Renders template view for the last saved map view.
    """
    greeting = SetGreeting(self)
    q = ''
    self.template_values = {}
    last_point = RetrieveLastPoint()
    if last_point:
      if last_point.saved_map_key:
        last_point = FindSavedPointFromLastPoint(last_point.saved_map_key)
        lat = last_point.lat
        lng = last_point.lng
        zoom_level = last_point.zoom_level
        street_address = last_point.street_address
        title = last_point.title
        region = last_point.region
        city = last_point.city
        url = last_point.url
        phone = last_point.phone
        self.template_values = SetupSinglePoint(lat, lng, zoom_level,
                                                street_address, title, region,
                                                city, url, phone)
      else:
        q = last_point.q
        rs = DoSearch(q, MAP_SIZE)
        if rs is None:
          path = os.path.join(os.path.dirname(__file__), 'bad_search.html')
          self.response.out.write(template.render(path, self.template_values))
          return
        self.template_values['zoom_level'] = last_point.zoom_level
        self.template_values['lat'] = rs['lat']
        self.template_values['lng'] = rs['lng']
        self.template_values['markers'] = rs['markers']
        self.template_values['search_results'] = rs['display_results']
        
    else:
      q = 'los angeles'
      rs = DoSearch(q, MAP_SIZE)
      if rs is None:
        path = os.path.join(os.path.dirname(__file__), 'bad_search.html')
        self.response.out.write(template.render(path, self.template_values))
        return
      self.template_values['zoom_level'] = rs['zoom']
      self.template_values['lat'] = rs['lat']
      self.template_values['lng'] = rs['lng']
      self.template_values['markers'] = rs['markers']
      self.template_values['search_results'] = rs['display_results']
      
    
    SetDefaultTemplateValues(self, MAP_SIZE, MAP_KEY, greeting, q, 
        FindAllSavedPoints())
    
    path = os.path.join(os.path.dirname(__file__), 'local.html')
    self.response.out.write(template.render(path, self.template_values))


def main():
  """Handles all requests and routes them to the correct code.

  Args:
    None.
  Returns:
    None.
  """
  application = webapp.WSGIApplication(
      [('/', MainPage),
      ('/search', Search),
      ('/zoom', Zoom),
      ('/focus', Focus),
      ('/save', Save),
      ('/delete', Delete)],
      debug=True)
  wsgiref.handlers.CGIHandler().run(application)
  
if __name__ == '__main__':
  main()
