// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,it,expect,vi} from "vitest";
import {SaturationScenarioPanel} from "./SaturationScenarioPanel";
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
it("updates scenarios, rejects blanks and resets the example",()=>{
 render(<SaturationScenarioPanel/>);expect(screen.getByRole("status").textContent).toContain("50.00%");
 fireEvent.change(screen.getByLabelText("Water resistivity Rw (ohm.m)"),{target:{value:"1"}});expect(screen.getByText(/Calculated Sw exceeds/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Porosity (fraction)"),{target:{value:""}});expect(screen.queryByRole("status")).toBeNull();expect((screen.getByRole("button",{name:"Download scenario JSON"}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole("button",{name:"Reset example"}));expect(screen.getByRole("status").textContent).toContain("50.00%");
});

it("exports inputs, assumptions and raw values in a downloadable JSON file",async()=>{
 let captured:Blob|undefined;let filename="";
 const create=vi.fn((blob:Blob)=>{captured=blob;return "blob:scenario"});
 vi.stubGlobal("URL",{createObjectURL:create,revokeObjectURL:vi.fn()});
 vi.spyOn(HTMLAnchorElement.prototype,"click").mockImplementation(function(this:HTMLAnchorElement){filename=this.download});
 render(<SaturationScenarioPanel/>);
 fireEvent.change(screen.getByLabelText("Rw temperature context"),{target:{value:"Assumed 80 C"}});
 fireEvent.click(screen.getByRole("button",{name:"Download scenario JSON"}));
 expect(filename).toBe("petroedge-archie-scenario.json");expect(captured).toBeTruthy();
 const text=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(captured!)});
 const payload=JSON.parse(text);expect(payload.trained_model).toBe(false);expect(payload.raw_water_fraction).toBeCloseTo(.5);expect(payload.rw_temperature_context).toBe("Assumed 80 C");expect(payload.oil_gas_split_available).toBe(false);
});
