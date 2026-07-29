# PetroEdge RC2: Blank-page elimination and fluid distinction

## Root causes addressed

1. Reservoir Intelligence calculated depth limits with `Math.min(...largeArray)` and `Math.max(...largeArray)`. Large well-log datasets can exceed the JavaScript argument limit and throw a `RangeError` before the page renders.
2. The Plotly React wrapper was dynamically imported but its expected Plotly peer runtime was not installed as `plotly.js`. The project carries `plotly.js-dist-min`, so the chart loader now uses that runtime directly.
3. Model Evaluation assumed that the experiment endpoint always returned a bare array and that every metrics property was a valid object. The panel now normalises common response envelopes and validates metric records defensively.
4. Very large interpretation arrays could freeze the browser. Interactive plots now downsample to at most 5,000 representative points while calculations and tables retain the complete backend interpretation.

## Combined implementation

- Reservoir Intelligence remains fully interactive and displays water, oil, gas and residual-hydrocarbon probabilities.
- Dominant fluid and confidence are shown by depth.
- Fluid interpretation by pay interval remains available.
- X-axis numeric tick labels remain limited to one decimal place.
- Model Evaluation renders loading, API error, empty and successful states without producing a white page.
- Plotly loading and rendering failures are displayed inside the chart area.
- Both panels remain protected by the dashboard error boundary.

## Validation

The revised files were statically reviewed and the backend was unchanged. A complete frontend build could not be completed in the packaging environment because the internal npm registry returned HTTP 503 while installing dependencies. Run the normal clean install and build on the target Windows machine.
