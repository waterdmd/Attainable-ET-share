var arizona = ee.FeatureCollection("TIGER/2018/States")
  .filter(ee.Filter.eq("NAME", "Arizona"));
var geometry = arizona.geometry();
Map.centerObject(geometry, 6);

var year = 2024;
var startDate = ee.Date.fromYMD(year, 1, 1);
var endDate = startDate.advance(1, 'year');

var precipitation = ee.ImageCollection('OREGONSTATE/PRISM/AN81m')
  .filterDate(startDate, endDate)
  .select('ppt');

var annualPrecipitation = precipitation.sum().clip(geometry);

Export.image.toDrive({
  image: annualPrecipitation,
  description: 'AZ_Total_Annual_Precipitation_mm_' + year,
  folder: 'Arizona_Climate_Data',
  fileNamePrefix: 'AZ_Total_Annual_Precipitation_mm_' + year,
  region: geometry,
  // scale: 800,
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});