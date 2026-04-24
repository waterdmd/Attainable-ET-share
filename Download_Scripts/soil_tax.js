var arizona = ee.FeatureCollection("TIGER/2018/States")
  .filter(ee.Filter.eq("NAME", "Arizona"));
var geometry = arizona.geometry();
Map.centerObject(geometry, 6);

var soilGreatGroup = ee.Image('OpenLandMap/SOL/SOL_GRTGROUP_USDA-SOILTAX_C/v01')
  .select('grtgroup') // Select the correct band for "Great Group".
  .clip(geometry);

Export.image.toDrive({
  image: soilGreatGroup,
  description: 'AZ_Soil_OpenLandMap_Great_Group',
  folder: 'Arizona_Soil_Data',
  fileNamePrefix: 'AZ_Soil_OpenLandMap_Great_Group',
  region: geometry,
  scale: 250,
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});