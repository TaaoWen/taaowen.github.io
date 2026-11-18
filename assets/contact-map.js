"use strict";

const contactMap = document.querySelector("#contact-map");
const point = [Number(contactMap.dataset.latitude), Number(contactMap.dataset.longitude)];
const streetMap = L.map(contactMap, { scrollWheelZoom: false }).setView(point, 16);
streetMap.attributionControl.setPrefix(false);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(streetMap);
L.circleMarker(point, {
  radius: 7,
  color: "#fff",
  weight: 2,
  fillColor: "#1c5683",
  fillOpacity: 1,
}).addTo(streetMap).bindTooltip(contactMap.dataset.place, {
  permanent: true,
  direction: "top",
  offset: [0, -10],
});
