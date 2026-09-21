// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {LasWizardPanel} from "./LasWizardPanel";
vi.mock("./platformApi",()=>({fetchDatasets:vi.fn(async()=>[{dataset_id:"d",name:"LAS"}]),fetchLasWizard:vi.fn(async()=>({mnemonic_mapping:{},qc:{row_count:25,missing_cells:0,duplicate_rows:0},missing_recommended_curves:[]})),prepareDataset:vi.fn()}));
vi.mock("./CurveMappingCopyPanel",()=>({CurveMappingCopyPanel:()=>null}));
vi.mock("./DataPreparationStudio",()=>({DataPreparationStudio:()=> <div>Spreadsheet editor</div>}));
afterEach(cleanup);
it("identifies LAS Wizard and mounts its shared editor only when requested",async()=>{
 render(<QueryClientProvider client={new QueryClient()}><LasWizardPanel/></QueryClientProvider>);
 expect(screen.getByRole("heading",{name:"LAS Wizard"})).toBeTruthy();
 const open=await screen.findByRole("button",{name:"Open preparation editor"});
 expect(screen.queryByText("Spreadsheet editor")).toBeNull();
 fireEvent.click(open);expect(screen.getByText("Spreadsheet editor")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Close preparation editor"}));
 expect(screen.queryByText("Spreadsheet editor")).toBeNull();
});
