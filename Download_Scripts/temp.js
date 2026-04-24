var arizona = ee.FeatureCollection("TIGER/2018/States")
  .filter(ee.Filter.eq("NAME", "Arizona"));
var geometry = arizona.geometry();
Map.centerObject(geometry, 6);

var year = 2023; 
var startDate = ee.Date.fromYMD(year, 1, 1);
var endDate = startDate.advance(1, 'year');

var temperature = ee.ImageCollection('OREGONSTATE/PRISM/AN81m')
  .filterDate(startDate, endDate)
  .select('tmean');

var annualMeanTemp = temperature.mean().clip(geometry);

Export.image.toDrive({
  image: annualMeanTemp,
  description: 'AZ_Mean_Annual_Temp_Celsius_' + year,
  folder: 'Arizona_Climate_Data',
  fileNamePrefix: 'AZ_Mean_Annual_Temp_Celsius_' + year,
  region: geometry,
  maxPixels: 1e13,
  // scale: 800,
  fileFormat: 'GeoTIFF'
});