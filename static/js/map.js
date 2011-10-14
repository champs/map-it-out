    function initialize() {
    var latlng = new google.maps.LatLng(13.83808,100.546875);
    var myOptions = {
      zoom: 6,
      center: latlng,
      mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    var map = new google.maps.Map(document.getElementById("map_canvas"),
        myOptions);
    }

    function codeAddress() {
var address = query;
geocoder.geocode( { 'address': address}, function(results, status) {
  if (status == google.maps.GeocoderStatus.OK) {
    map.setCenter(results[0].geometry.location);
    var marker = new google.maps.Marker({
        map: map, 
        position: results[0].geometry.location
    });
  } else {
    alert("Geocode was not successful for the following reason: " + status);
  }
});
}
