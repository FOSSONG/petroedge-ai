import {describe,it,expect} from "vitest";
import {archieScenario} from "./archieScenario";
const p={phi:.2,rt:10,rw:.1,a:1,m:2,n:2};
describe("Archie scenario",()=>{
 it("reproduces a known calculation and Rw sensitivity",()=>{expect(archieScenario(p).raw).toBeCloseTo(.5);expect(archieScenario({...p,rw:.4}).raw).toBeCloseTo(1)});
 it("retains and flags out-of-range physical results",()=>{const r=archieScenario({...p,rw:1});expect(r.raw).toBeGreaterThan(1);expect(r.bounded).toBe(1);expect(r.aboveOne).toBe(true)});
 it("rejects missing, invalid and overflowing inputs",()=>{for(const q of [{phi:0},{rt:-1},{rw:NaN},{phi:1.1},{n:0},{m:1e308}])expect(()=>archieScenario({...p,...q})).toThrow()});
});
