// Define Arizona boundary
var arizona = ee.FeatureCollection("TIGER/2018/States")
  .filter(ee.Filter.eq("NAME", "Arizona"));
var geometry = arizona.geometry();

// Load the OpenET dataset (30m resolution)
var etCollection = ee.ImageCollection("OpenET/ENSEMBLE/CONUS/GRIDMET/MONTHLY/v2_0")
  .select('et_ensemble_mad');
  
// Define time range
var startYear = 2019;
var endYear = 2019;

// Function to calculate and export annual ET
function exportAnnualET(year) {
  var startDate = ee.Date.fromYMD(year, 1, 1);
  var endDate = startDate.advance(1, 'year');
  var annualET = etCollection
    .filterDate(startDate, endDate)
    .sum()
    .toDouble()  // Convert image to double precision floating point
    .rename('et_annual')
    .clip(geometry);
  Export.image.toDrive({
    image: annualET,
    description: 'ET_' + year,
    folder: 'Arizona_ET',
    fileNamePrefix: 'AZ_ET_' + year,
    region: geometry,
    scale: 30,
    maxPixels: 1e13,
    crs: 'EPSG:4326',
    fileFormat: 'GeoTIFF'
  });
}

// Export all years
var years = ee.List.sequence(startYear, endYear);
years.evaluate(function(yearsList) {
  yearsList.forEach(function(year) {
    exportAnnualET(year);
  });
});