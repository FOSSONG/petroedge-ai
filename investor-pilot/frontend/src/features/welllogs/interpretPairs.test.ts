import {describe,it,expect} from "vitest";
import {interpretPairs} from "./interpretPairs";
describe("dataset-driven crossplot interpretations",()=>{
 it("identifies relative low gamma/high resistivity samples and includes their depths",()=>{
  const rows=Array.from({length:20},(_,i)=>({gamma_ray_api:i*5,resistivity_ohmm:100-i*4,depth_m:1000+i}));
  const result=interpretPairs(rows,"gamma_ray_api","resistivity_ohmm",false,true);
  expect(result.highlight.length).toBeGreaterThan(0);
  expect(result.highlight.every(r=>r.gamma_ray_api!<=20)).toBe(true);
  expect(result.text).toContain((1000).toLocaleString());
  expect(result.text).toContain("inverse");
  expect(result.meaning).toContain("neither hydrocarbon phase nor pay");
  expect(interpretPairs(rows.map(r=>({...r,resistivity_ohmm:10})),"gamma_ray_api","resistivity_ohmm").highlight).toHaveLength(0);
 });
 it("handles constant and absent pairs without invented associations",()=>{
  expect(interpretPairs([],"x","y").highlight).toHaveLength(0);
  expect(interpretPairs([{x:1,y:2},{x:1,y:2}],"x","y").text).toContain("too few varying");
 });
 it("caps circles while retaining the full interest count",()=>{
  const rows=Array.from({length:10000},(_,i)=>({x:i<9900?1:100,y:1}));
  expect(interpretPairs(rows,"x","y").highlight.length).toBeLessThanOrEqual(100);
 });
});
