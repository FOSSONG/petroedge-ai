// @vitest-environment jsdom
import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,it,expect,vi} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {ExperimentalModelsPanel} from "./ExperimentalModelsPanel";
vi.mock("../../api/http",()=>({apiRequest:vi.fn(async()=>({configured:true,design:"Development only",datasets:[{dataset_id:"d",name:"Porosity",training_rows:20,validation_rows:5,test_rows_excluded:5,error_unit:"porosity fraction",variants:[{name:"without_neutron",missing_curve:"NPHI",required_features:["GR","RHOB","RT"],validation_mae:.03,mae_change_vs_full_percent:20}]}]}))}));
afterEach(cleanup);
it("shows experimental limits and required inputs without deployment controls",async()=>{
 render(<QueryClientProvider client={new QueryClient()}><ExperimentalModelsPanel/></QueryClientProvider>);
 expect(await screen.findByText("GR, RHOB, RT")).toBeTruthy();
 expect(screen.getByText("20.0%")).toBeTruthy();
 expect(screen.queryByRole("button",{name:/deploy/i})).toBeNull();
 expect(screen.getByText(/not deployed/)).toBeTruthy();
});
