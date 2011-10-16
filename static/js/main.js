//Useful links:
// http://code.google.com/apis/maps/documentation/javascript/reference.html#Marker
// http://code.google.com/apis/maps/documentation/javascript/services.html#Geocoding
// http://jqueryui.com/demos/autocomplete/#remote-with-cache
// http://tech.cibul.net/geocode-with-google-maps-api-v3/      
var geocoder;
var map;
var marker;
var currentZoom = 12;    

// INIT the map on load
function initialize(){
//MAP
  var latlng = new google.maps.LatLng(13.83808,100.546875);
  var options = {
    zoom: currentZoom,
    center: latlng,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
        
  map = new google.maps.Map(document.getElementById("map_canvas"), options);
        
  //GEOCODER
  geocoder = new google.maps.Geocoder();
        
  marker = new google.maps.Marker({
    map: map,
    draggable: true
  });
}

// Auto complete text box for address search
$(document).ready(function() { 
  initialize();
  $(function() {
    $("#address").autocomplete({
      //This bit uses the geocoder to fetch address values
      source: function(request, response) {
        geocoder.geocode( {'address': request.term + ', TH'  }, function(results, status) {
          response($.map(results, function(item) {
            return {
              label: item.formatted_address,
              value: item.formatted_address,
              latitude: item.geometry.location.lat(),
              longitude: item.geometry.location.lng()
			 
            }
          }));
        })
      },
      //This bit is executed upon selection of an address
      select: function(event, ui) {
        $("#lat").val(ui.item.latitude);
        $("#lng").val(ui.item.longitude);
        var location = new google.maps.LatLng(ui.item.latitude, ui.item.longitude);
        marker.setPosition(location);
        map.setCenter(location);
        currentZoom = 16;
        map.setZoom(16);
      }
    });
  });
	
  //Add listener to marker for reverse geocoding
  google.maps.event.addListener(marker, 'drag', function() {
    geocoder.geocode({'latLng': marker.getPosition()}, function(results, status) {
      if (status == google.maps.GeocoderStatus.OK) {
        if (results[0]) {
          $('#address').val(results[0].formatted_address);
          $('#lat').val(marker.getPosition().lat());
          $('#lng').val(marker.getPosition().lng());
        }
      }
    });
  });
  
});
      // A function to create the circle and set up the event window

// Create Marker  
    var reportCircle;  
      function createMarker(point,name,html) {
        var marker = new google.maps.Marker(point);
        GEvent.addListener(marker, "click", function() {
          marker.openInfoWindowHtml(html);
        });
        // save the info we need to use later for the side_bar
        gmarkers[i] = marker;
        htmls[i] = html;
        // add a line to the side_bar html
        side_bar_html += '<a href="javascript:myclick(' + i + ')">' + name + '<\/a><br>';
        i++;
        return marker;
    }

    function colorPicker(water){
        colorOptions = {
        0:"#00FF00",               
        1:"#33FF00",
        2:"#77FF00", 
        3:"#AAFF00", 
        4:"#FFFF00", 
        5:"#FFAA00", 
        6:"#FF7700", 
        7:"#FF3300", 
        8:"#FF0000", 
        }
        return colorOptions[water];
    }
        // A function to parse json and call createMarker
      process_it = function(doc) {
        // === Parse the JSON document === 
        var jsonData = eval('(' + doc + ')');
        
        // === Plot the markers ===
        for (var i=0; i<jsonData.length; i++) {
            var center = new google.maps.LatLng(jsonData[i].lat, jsonData[i].lng);
            var circleOptions = {
                strokeColor: colorPicker(jsonData[i].water),
                strokeOpacity: 0.8,
                strokeWeight: 1,
                fillColor: colorPicker(jsonData[i].water),
                fillOpacity: 0.35,
                map: map,
                center: center,
                radius: 800
            };
        reportCircle = new google.maps.Circle(circleOptions);
         
        }
      }          

      
      // ================================================================
      // === Fetch the JSON data file ====    
      microAjax("json", process_it);
      // ================================================================





// -- sharing stuff
    (function() {
            var po = document.createElement('script'); po.type = 'text/javascript'; po.async = true;
            po.src = 'https://apis.google.com/js/plusone.js';
            var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(po, s);
        })(); 


// google analytics
     var _gaq = _gaq || [];
      _gaq.push(['_setAccount', 'UA-26347281-1']);
      _gaq.push(['_trackPageview']);
      (function() {
        var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
        ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
        var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
      })();                              

