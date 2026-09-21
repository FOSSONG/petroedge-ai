import {it,expect} from "vitest";
import {researchPlotSamples} from "./researchPlotSamples";
it("bounds only the plot and retains both endpoints without mutating full results",()=>{const rows=Array.from({length:18373},(_,source_row)=>({source_row}));const plot=researchPlotSamples(rows);expect(plot).toHaveLength(2000);expect(plot[0].source_row).toBe(0);expect(plot[plot.length-1].source_row).toBe(18372);expect(new Set(plot.map(r=>r.source_row)).size).toBe(2000);expect(rows).toHaveLength(18373)});
it("retains small outputs including withheld rows",()=>{const rows=[{prediction:null},{prediction:.2}];expect(researchPlotSamples(rows)).toBe(rows)});
